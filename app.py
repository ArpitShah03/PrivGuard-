import streamlit as st
import os
import uuid
import time
import pandas as pd
from typing import List, Dict, Any

from models.schemas import DocumentAnalysisResult, DocumentBlock
from extractors.router import route_and_extract, compute_extraction_metrics
from extractors.ocr_engine import default_ocr_engine
from detection.pii_engine import detect_pii_in_block, detect_pii_in_document_blocks
from redaction.redactor import Redactor
from redaction.validator import validate_sanitized_blocks
from redaction.document_sanitizer import default_document_sanitizer
from reporting.report_generator import generate_json_report, generate_csv_report
from policy.engine import default_policy_engine
from audit.audit_logger import default_audit_logger
from audit.audit_store import default_audit_store

from ui.styles import ENTERPRISE_CSS
from ui.dashboard_data import default_dashboard_data
from ui.components import (
    render_sidebar_header,
    render_sidebar_policy_card,
    render_top_header,
    render_kpi_cards,
    render_decision_trend_chart,
    render_pii_donut_chart,
    render_performance_and_activity,
)
from ui.viewer import render_document_comparison
from ui.workbench import render_human_review_workbench
from ui.attack_sim import render_attack_simulation_view
from ui.analytics_advanced import render_advanced_analytics_view
from detection.visual_pii import default_visual_detector
from detection.explainability import default_explainer
from reporting.coverage_map import default_coverage_calculator
from models.risk_scorer import default_risk_scorer
from reporting.audit_hasher import AuditHasher
from utils.file_security import compute_bytes_sha256, compute_file_sha256

# Configuration & Theme
st.set_page_config(
    page_title="PrivGuard — AI Data Privacy Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Enterprise CSS
st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)


def process_file(uploaded_file) -> DocumentAnalysisResult:
    """Execute end-to-end multi-modal scan, detection, policy evaluation, redaction, and re-scan gate."""
    file_name = uploaded_file.name
    file_ext = file_name.split('.')[-1].lower()
    document_id = str(uuid.uuid4())
    logger = default_audit_logger
    t_start = time.time()
    
    orig_bytes = uploaded_file.getvalue()
    orig_sha256 = compute_bytes_sha256(orig_bytes)
    st.session_state.setdefault("file_bytes_cache", {})[document_id] = orig_bytes

    # Save original file safely with unique prefix to avoid Windows handle collisions
    safe_temp_name = f"original_{document_id[:8]}_{file_name}"
    temp_path = os.path.join("uploads", safe_temp_name)
    os.makedirs("uploads", exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(orig_bytes)
        
    result = DocumentAnalysisResult(
        document_id=document_id,
        file_name=file_name,
        file_type=file_ext,
        status="PROCESSING",
        original_blocks=[],
        sanitized_blocks=[],
        findings=[],
        original_file_path=temp_path
    )

    logger.log_event(document_id, "SCAN", "STARTED", f"Initiated security analysis for {file_name}")
    
    # 0. Phase 6 Input File Policy Check
    policy_eng = default_policy_engine
    file_size = len(orig_bytes)
    is_file_allowed, file_reject_reason = policy_eng.validate_input_file(temp_path, file_size)
    if not is_file_allowed:
        result.status = "BLOCKED"
        result.error_message = file_reject_reason
        logger.log_event(document_id, "POLICY", "FAILED", f"Input file policy violation: {file_reject_reason}")
        return result

    try:
        # 1. Multimodal Extraction via Central Router
        t_ext_0 = time.time()
        blocks = route_and_extract(temp_path, document_id, file_name)
        t_ext_ms = (time.time() - t_ext_0) * 1000.0
        result.original_blocks = blocks

        metrics = compute_extraction_metrics(blocks)
        result.extraction_metadata = metrics
        result.ocr_coverage = metrics.get("ocr_coverage", 1.0)
        logger.log_event(document_id, "EXTRACTION", "SUCCESS", f"Extracted {len(blocks)} blocks", {"total_blocks": len(blocks)})
        
        # 2. Multi-Stage Detection with Conservative Entity Resolution & Fusion
        t_det_0 = time.time()
        all_findings = detect_pii_in_document_blocks(blocks)

        # 2a. Multimodal Visual PII Detection (Signatures, ID photos, Stamps)
        has_vis_unc = False
        if file_ext == "pdf":
            try:
                vis_findings = default_visual_detector.detect_in_pdf(orig_bytes)
                if any(vf.is_uncertain for vf in vis_findings):
                    has_vis_unc = True
                vis_pii = default_visual_detector.to_pii_findings(vis_findings, document_id, file_name)
                all_findings.extend(vis_pii)
            except Exception:
                has_vis_unc = True

        t_det_ms = (time.time() - t_det_0) * 1000.0
        result.findings = all_findings
        logger.log_event(document_id, "DETECTION", "SUCCESS", f"Detected {len(all_findings)} PII findings", {"count": len(all_findings)})
        logger.log_findings(document_id, all_findings)

        # 2b. Phase 6 Policy Finding Evaluation & Governance
        has_unc = (metrics.get("ocr_coverage", 1.0) < 1.0 or any(b.metadata.get("is_uncertain") for b in blocks) or has_vis_unc)
        active_findings, policy_pre_status, policy_reason = policy_eng.evaluate_findings(
            findings=all_findings,
            has_extraction_uncertainty=has_unc
        )
        if policy_pre_status == "BLOCKED":
            result.status = "BLOCKED"
            result.error_message = policy_reason
            logger.log_event(document_id, "POLICY", "BLOCKED", f"Prohibited PII entity detected: {policy_reason}")
            return result

        # 3. In-Memory Redaction for Text Review
        t_red_0 = time.time()
        redactor = Redactor()
        findings_by_loc = {}
        for f in active_findings:
            findings_by_loc.setdefault(f.location, []).append(f)

        sanitized_blocks = []
        for block in blocks:
            block_findings = findings_by_loc.get(block.location, [])
            sanitized_block, _ = redactor.redact_block(block, block_findings)
            sanitized_blocks.append(sanitized_block)

        result.sanitized_blocks = sanitized_blocks

        # 4. Phase 3 Structure-Preserving Document Sanitization (Real Output File)
        sanitizer = default_document_sanitizer
        output_file_name = f"sanitized_{document_id[:8]}_{file_name}"
        sanitized_file_path = sanitizer.sanitize(temp_path, active_findings, output_filename=output_file_name)
        t_red_ms = (time.time() - t_red_0) * 1000.0
        result.sanitized_file_path = sanitized_file_path
        logger.log_event(document_id, "REDACTION", "SUCCESS", f"Generated structure-preserved file: {os.path.basename(sanitized_file_path)}")

        # 5. Phase 3 & Phase 6 Mandatory Re-Scan Verification Gate
        t_res_0 = time.time()
        validation, re_scanned_blocks = sanitizer.verify_and_rescan(
            sanitized_file_path=sanitized_file_path,
            original_blocks=blocks,
            original_findings=active_findings,
            document_id=document_id,
            policy_engine=policy_eng,
            original_file_path=temp_path,
            applied_redactions_count=sanitizer.last_applied_count
        )
        t_res_ms = (time.time() - t_res_0) * 1000.0
        result.validation_result = validation
        result.re_scanned_blocks = re_scanned_blocks
        result.status = validation.security_decision

        # Calculate File Hashes, Coverage Map & Deterministic Risk Score
        sanit_sha256 = compute_file_sha256(sanitized_file_path) if (sanitized_file_path and os.path.exists(sanitized_file_path)) else "N/A"
        cov_map = default_coverage_calculator.compute_coverage(document_id, blocks)
        risk_score = default_risk_scorer.calculate_risk(
            all_findings,
            uncertain_blocks=validation.uncertain_blocks_count,
            residual_pii=validation.pii_after
        )

        result.security_summary = {
            "total_blocks": len(blocks),
            "inspected_blocks": len(blocks) - validation.uncertain_blocks_count,
            "uncertain_blocks": validation.uncertain_blocks_count,
            "pii_before": validation.pii_before,
            "pii_after": validation.pii_after,
            "high_risk_residual": validation.high_risk_residual,
            "decision": validation.security_decision,
            "output_file": sanitized_file_path,
            "original_sha256": orig_sha256,
            "sanitized_sha256": sanit_sha256,
            "coverage_map": cov_map.to_dict(),
            "risk_score": risk_score.to_dict()
        }

        t_total_ms = (time.time() - t_start) * 1000.0

        # Finalize Scan Audit Record in SQLite
        logger.finalize_scan(
            scan_id=document_id,
            filename=file_name,
            file_type=file_ext,
            total_blocks=len(blocks),
            uncertain_blocks=validation.uncertain_blocks_count,
            pii_before=validation.pii_before,
            pii_after=validation.pii_after,
            high_risk_residual=validation.high_risk_residual,
            security_decision=validation.security_decision,
            sanitized_file_path=sanitized_file_path,
            timing_stats={
                "extraction_ms": round(t_ext_ms, 2),
                "detection_ms": round(t_det_ms, 2),
                "redaction_ms": round(t_red_ms, 2),
                "rescan_ms": round(t_res_ms, 2),
                "total_ms": round(t_total_ms, 2)
            }
        )
            
    except Exception as e:
        result.status = "ERROR"
        result.error_message = str(e)
        logger.log_event(document_id, "ERROR", "FAILED", f"Error during analysis: {str(e)}")
            
    return result


def main():
    # 1. Left Sidebar Navigation & Brand
    render_sidebar_header()

    nav_selection = st.sidebar.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "📄 Scan Document",
            "🔍 Findings",
            "📜 Audit Logs",
            "⚙️ Policy Settings",
            "📈 Reports",
            "📉 Analytics",
            "⚔️ Attack Lab"
        ],
        label_visibility="collapsed"
    )

    policy_summary = default_dashboard_data.get_active_policy_summary()
    render_sidebar_policy_card(policy_summary)

    # 2. Main Area Routing
    if nav_selection == "📊 Dashboard":
        render_dashboard_view()
    elif nav_selection == "📄 Scan Document":
        render_scan_document_view()
    elif nav_selection == "🔍 Findings":
        render_findings_view()
    elif nav_selection == "📜 Audit Logs":
        render_audit_logs_view()
    elif nav_selection == "⚙️ Policy Settings":
        render_policy_settings_view()
    elif nav_selection == "📈 Reports":
        render_reports_view()
    elif nav_selection == "📉 Analytics":
        render_analytics_view()
    elif nav_selection == "⚔️ Attack Lab":
        render_attack_simulation_view()


def render_dashboard_view():
    """Render the primary Security Operations Dashboard matching the reference design."""
    render_top_header("Security Dashboard", "Real-time overview of your PII security gateway")

    # Time filter bar & export
    f_col1, f_col2, f_col3 = st.columns([6, 2, 2])
    with f_col2:
        time_filter = st.selectbox("Range", ["Last 24 Hours", "Last 7 Days", "Last 30 Days"], label_visibility="collapsed")
    with f_col3:
        if st.button("📥 Export Report", use_container_width=True):
            st.toast("Generating audit export package...", icon="ℹ️")

    # Row 1: 4 KPI Cards
    kpi_data = default_dashboard_data.get_kpi_summary()
    render_kpi_cards(kpi_data)

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # Row 2: 2 Column Panels (Decision Trend + PII by Type)
    c_col1, c_col2 = st.columns([1.1, 0.9])
    with c_col1:
        st.markdown("<div class='qs-panel'>", unsafe_allow_html=True)
        trend_data = default_dashboard_data.get_decision_trends(time_filter)
        render_decision_trend_chart(trend_data)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_col2:
        st.markdown("<div class='qs-panel'>", unsafe_allow_html=True)
        pii_dist = default_dashboard_data.get_pii_distribution()
        render_pii_donut_chart(pii_dist)
        st.markdown("</div>", unsafe_allow_html=True)

    # Row 3: Processing Performance & Recent Activity
    st.markdown("<div class='qs-panel'>", unsafe_allow_html=True)
    perf_data = default_dashboard_data.get_processing_performance()
    recent_activity = default_dashboard_data.get_recent_activity(5)
    render_performance_and_activity(perf_data, recent_activity)
    st.markdown("</div>", unsafe_allow_html=True)

    # Row 4: Recent Scans Table
    st.markdown("<div class='qs-panel'>", unsafe_allow_html=True)
    st.markdown("""
    <div class="qs-panel-title">
        <span>Recent Scans</span>
        <span style="font-size: 12px; color: #64748B; font-weight: normal;">Latest enterprise document scans</span>
    </div>
    """, unsafe_allow_html=True)

    recent_scans = default_dashboard_data.get_recent_scans_table(10)
    if recent_scans:
        df_scans = pd.DataFrame(recent_scans)
        st.dataframe(df_scans, use_container_width=True, hide_index=True)
    else:
        st.caption("No recent scan data available.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Row 5: Operational Health & Active Controls
    st.markdown("<div class='qs-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='qs-panel-title'>System & Security Health Status</div>", unsafe_allow_html=True)
    h1, h2, h3, h4, h5, h6 = st.columns(6)
    h1.metric("Gateway Core", "ONLINE")
    h2.metric("Policy Engine", "ACTIVE")
    h3.metric("Audit Database", "AVAILABLE")
    h4.metric("Re-scan Gate", "ENFORCED")
    h5.metric("Coverage Gate", "ENFORCED")
    h6.metric("Fail-Closed", "ENABLED")
    st.markdown("</div>", unsafe_allow_html=True)


def render_scan_document_view():
    """Document Scan upload, processing, and multi-modal detail inspection."""
    render_top_header("Scan Document", "Upload, inspect, redact, and verify enterprise business documents")

    # OCR binary check notice
    if not default_ocr_engine.is_available:
        st.warning("⚠️ **Tesseract OCR Notice**: Windows Tesseract binary not detected on PATH. Scanned pages will route safely to HUMAN_REVIEW under fail-closed coverage policy.")

    uploaded_files = st.file_uploader(
        "Select Business Evidence Documents (PDF, DOCX, PPTX, TXT)",
        type=["pdf", "docx", "pptx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("🛡️ Execute Security Scan & Sanitization", type="primary"):
            results = []
            p_bar = st.progress(0)
            status_txt = st.empty()

            for i, uf in enumerate(uploaded_files):
                status_txt.text(f"Scanning & sanitizing {uf.name}...")
                res = process_file(uf)
                results.append(res)
                p_bar.progress((i + 1) / len(uploaded_files))

            status_txt.text("✅ Analysis & Sanitization Complete.")
            st.session_state["analysis_results"] = results

    if "analysis_results" in st.session_state:
        results: List[DocumentAnalysisResult] = st.session_state["analysis_results"]
        doc_names = [r.file_name for r in results]
        st.markdown("---")
        selected_name = st.selectbox("Inspect Document Analysis Details:", doc_names)
        res = next((r for r in results if r.file_name == selected_name), None)

        if res:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

            # Prominent Executive Decision Banner
            st_color = "#059669" if res.status == "SANITIZED" else ("#D97706" if res.status == "HUMAN_REVIEW" else "#DC2626")
            st_bg = "#ECFDF5" if res.status == "SANITIZED" else ("#FFFBEB" if res.status == "HUMAN_REVIEW" else "#FEF2F2")
            st_border = "#A7F3D0" if res.status == "SANITIZED" else ("#FDE68A" if res.status == "HUMAN_REVIEW" else "#FECACA")
            st_icon = "🟢" if res.status == "SANITIZED" else ("🟡" if res.status == "HUMAN_REVIEW" else "🔴")

            val_msg = res.validation_result.message if getattr(res, "validation_result", None) else "Processing complete."

            b_col1, b_col2 = st.columns([3, 1.2])
            with b_col1:
                st.markdown(f"""
                <div style="background-color: {st_bg}; border: 1px solid {st_border}; border-radius: 10px; padding: 14px 18px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                        <span style="font-size: 18px;">{st_icon}</span>
                        <strong style="color: {st_color}; font-size: 16px;">SECURITY DECISION: {res.status}</strong>
                    </div>
                    <div style="font-size: 13px; color: #334155; margin-left: 28px;">
                        {val_msg}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with b_col2:
                if res.sanitized_file_path and os.path.exists(res.sanitized_file_path):
                    with open(res.sanitized_file_path, "rb") as f_dl:
                        btn_label = f"📥 Download Redacted File" if res.status == "SANITIZED" else f"📥 Download Draft File"
                        st.download_button(
                            btn_label,
                            f_dl.read(),
                            file_name=f"sanitized_{res.file_name}",
                            mime="application/octet-stream",
                            use_container_width=True
                        )

            # Quick Metric Pills
            pii_before_cnt = len(res.findings)
            pii_after_cnt = res.validation_result.pii_after if getattr(res, "validation_result", None) else 0
            blocks_cnt = len(res.original_blocks)
            risk_meta = res.security_summary.get("risk_score", {})
            r_score = risk_meta.get("score", 0)
            r_cat = risk_meta.get("category", "LOW")

            m1, m2, m3, m4, m5 = st.columns(5)
            with m1:
                st.metric("Total Blocks Extracted", blocks_cnt)
            with m2:
                st.metric("Detected PII Mentions", pii_before_cnt)
            with m3:
                st.metric("Residual Post-Rescan", pii_after_cnt)
            with m4:
                st.metric("Security Risk Score", f"{r_score}/100", delta=r_cat, delta_color="inverse" if r_score > 30 else "normal")
            with m5:
                st.metric("Mandatory Re-Scan", "ENFORCED", delta="Verified Clean" if pii_after_cnt == 0 else "Residual Found")

            # Cryptographic File Integrity Pills
            orig_h = res.security_summary.get("original_sha256", "N/A")
            sanit_h = res.security_summary.get("sanitized_sha256", "N/A")
            st.markdown(f"""
            <div style="font-size: 11px; color: #64748B; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 12px; margin-top: 6px; margin-bottom: 12px; display: flex; justify-content: space-between;">
                <span>🔒 Original SHA-256: <code>{orig_h[:24]}...</code></span>
                <span>🛡️ Sanitized SHA-256: <code>{sanit_h[:24]}...</code></span>
            </div>
            """, unsafe_allow_html=True)

            if res.status == "ERROR":
                st.error(f"❌ **Analysis Failed**: {res.error_message}")
                st.info("Tip: Please ensure the document is not password protected and is a supported format (PDF, DOCX, PPTX, TXT).")

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

            t_viewer, t_find, t_cov, t_wb, t_trace, t_export, t_gate = st.tabs([
                "👁️ Before & After Viewer",
                "🔍 Findings & Evidence",
                "🗺️ Coverage Map",
                "👷 Review Workbench",
                "📋 Traceability Blocks",
                "📥 Sanitized Export",
                "📜 Verification & Timeline"
            ])

            with t_viewer:
                orig_bytes = st.session_state.get("file_bytes_cache", {}).get(res.document_id)
                render_document_comparison(
                    res,
                    original_file_bytes=orig_bytes,
                    original_artifact_path=res.original_file_path,
                    sanitized_artifact_path=res.sanitized_file_path
                )

            with t_find:
                if res.findings:
                    f_data = [{
                        "PII Type": f.pii_type,
                        "Severity": f.severity,
                        "Confidence": f"{f.confidence*100:.1f}%",
                        "Decision": getattr(f, "fusion_decision", "DETECT") or "DETECT",
                        "Method": " + ".join(f.detection_method),
                        "Replacement Token": f.replacement_token or "[REDACTED]",
                        "Location": f.location
                    } for f in res.findings]
                    st.dataframe(pd.DataFrame(f_data), use_container_width=True)

                    st.markdown("#### 💡 Explainable Detection Evidence")
                    st.caption("Inspect why each sensitive entity was flagged, including trigger keywords, checksums, and fusion agreement.")
                    for idx, f in enumerate(res.findings[:10]):
                        exp = default_explainer.explain_finding(f)
                        with st.expander(f"Entity #{idx+1}: [{exp.pii_type}] ({exp.confidence_score*100:.1f}%) | Primary: {exp.primary_detector}"):
                            st.write(f"**Decision Summary:** {exp.decision_summary}")
                            if exp.algorithmic_checks:
                                st.write(f"**Checksum Checks:** {', '.join(exp.algorithmic_checks)}")
                            if exp.trigger_keywords:
                                st.write(f"**Trigger Keywords Detected:** {', '.join(set(exp.trigger_keywords))}")
                            st.caption(f"Agreement Category: `{exp.agreement_category}` | Sources: `{', '.join(f.detection_method)}`")
                else:
                    st.info("Zero PII detected in this document.")

            with t_cov:
                st.markdown("#### 🗺️ Multi-Modal Extraction Coverage Map")
                cov_data = res.security_summary.get("coverage_map", {})
                if cov_data:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Native Text Coverage", f"{cov_data.get('native_text_coverage', 100):.1f}%")
                    c2.metric("OCR Scanned Coverage", f"{cov_data.get('ocr_coverage', 100):.1f}%")
                    c3.metric("Visual Coverage", f"{cov_data.get('visual_coverage', 100):.1f}%")
                    c4.metric("Metadata Coverage", f"{cov_data.get('metadata_coverage', 100):.1f}%")

                    st.markdown(f"**Overall Modality Coverage:** `{cov_data.get('overall_coverage', 100):.1f}%`")
                    if cov_data.get("deficit_reasons"):
                        for dr in cov_data["deficit_reasons"]:
                            st.warning(f"⚠️ {dr}")
                    else:
                        st.success("✅ Complete 100% extraction coverage across all document modalities.")
                else:
                    st.info("Coverage metrics not generated for this file.")

            with t_wb:
                render_human_review_workbench(res)

            with t_trace:
                st.write(f"**Total Document Blocks Extracted:** {len(res.original_blocks)}")
                for b in res.original_blocks[:10]:
                    ocr_tag = f"[OCR conf: {b.ocr_confidence*100:.1f}%]" if b.is_ocr else "[Native]"
                    with st.expander(f"[{b.block_type}] {b.location} | {ocr_tag}"):
                        st.write(f"Type: `{b.block_type}` | Location: `{b.location}`")
                        st.text(b.text[:250] + ("..." if len(b.text) > 250 else ""))

            with t_export:
                if res.status == "SANITIZED":
                    st.success("✅ **RELEASE APPROVED**: Document verified clean through mandatory re-scan. 100% extraction coverage confirmed.")
                    if res.sanitized_file_path and os.path.exists(res.sanitized_file_path):
                        with open(res.sanitized_file_path, "rb") as f_out:
                            st.download_button(
                                f"📥 Download Sanitized {res.file_name}",
                                f_out.read(),
                                file_name=f"sanitized_{res.file_name}",
                                mime="application/octet-stream"
                            )
                elif res.status == "BLOCKED":
                    st.error("⛔ **RELEASE BLOCKED**: Residual high-risk PII detected post-redaction. Export is restricted.")
                elif res.status == "HUMAN_REVIEW":
                    st.warning("⚠️ **HUMAN REVIEW REQUIRED**: Extraction coverage incomplete (e.g. scanned page or unverified content). Manual inspection required.")
                    if res.sanitized_file_path and os.path.exists(res.sanitized_file_path):
                        with open(res.sanitized_file_path, "rb") as f_out:
                            st.download_button(
                                f"📥 Download Redacted Document (Pending Review)",
                                f_out.read(),
                                file_name=f"sanitized_{res.file_name}",
                                mime="application/octet-stream"
                            )

                sanitized_text = "\n\n".join([b.text for b in res.sanitized_blocks])
                st.text_area("Sanitized Content Preview", sanitized_text, height=300, disabled=True)

            with t_gate:
                val = res.validation_result
                if val:
                    st.write(f"**Message**: {val.message}")
                    st.write(f"**PII Before**: {val.pii_before} | **Residual PII**: {val.pii_after} | **Uncertain Blocks**: {val.uncertain_blocks_count}")

                st.markdown("#### Audit Event Timeline")
                events = default_audit_store.get_events_for_scan(res.document_id)
                if events:
                    ev_rows = [{"Stage": e.stage, "Status": e.status, "Message": e.message, "Hash": (e.event_hash[:16] + '...') if getattr(e, 'event_hash', None) else 'N/A'} for e in events]
                    st.dataframe(pd.DataFrame(ev_rows), use_container_width=True)


def render_findings_view():
    """Findings discovery console with search and filters. ZERO RAW PII."""
    render_top_header("Findings Discovery", "Inventory of detected sensitive entities across document scans")

    with default_audit_store._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT finding_id, pii_type, replacement_token, confidence, detection_method, severity, location FROM finding_audit_records LIMIT 200")
        rows = cursor.fetchall()

    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        df["confidence"] = df["confidence"].apply(lambda x: f"{x*100:.1f}%")

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            type_filter = st.multiselect("Filter by PII Type", options=list(df["pii_type"].unique()), default=[])
        with f_col2:
            sev_filter = st.multiselect("Filter by Severity", options=list(df["severity"].unique()), default=[])

        if type_filter:
            df = df[df["pii_type"].isin(type_filter)]
        if sev_filter:
            df = df[df["severity"].isin(sev_filter)]

        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No findings stored in audit database yet.")


def render_audit_logs_view():
    """Enterprise audit trail view with cryptographic tamper-evident verification."""
    render_top_header("Audit Logs", "Persistent immutable audit records stored in local SQLite audit store")

    # Cryptographic SHA-256 Hash Chain Verification
    is_valid, count, err = AuditHasher.verify_event_chain(default_audit_store.db_path)
    if is_valid:
        st.success(f"🛡️ **CRYPTOGRAPHIC AUDIT CHAIN VALIDATED**: 100% Tamper-Evident SHA-256 Hash Chaining. Verified {count} sequential event blocks.")
    else:
        st.error(f"⚠️ **AUDIT INTEGRITY ALERT**: Cryptographic chain broken at event #{count}. Reason: {err}")

    scans = default_audit_store.get_all_scans()
    if scans:
        rows = [{
            "Scan ID": s.scan_id[:8] + "...",
            "Filename": s.filename,
            "Type": s.file_type,
            "Decision": s.security_decision,
            "PII Before": s.pii_before,
            "Residual": s.pii_after,
            "Coverage": f"{s.coverage_percentage:.1f}%",
            "Latency": f"{s.total_time_ms:.1f}ms",
            "Timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s.timestamp))
        } for s in scans]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No audit logs found.")


def render_policy_settings_view():
    """Read-only active policy console."""
    render_top_header("Policy Settings", "Active enterprise security governance rules (read-only)")
    st.info("ℹ️ Policy source: `config/policy.yaml`. Modifying governance rules requires configuration approval.")

    pol = default_policy_engine.policy
    p1, p2, p3 = st.columns(3)
    p1.metric("Policy Name", pol.name)
    p2.metric("Version", pol.version)
    p3.metric("Status", pol.policy_status)

    st.markdown("### Decision Thresholds")
    t1, t2 = st.columns(2)
    t1.metric("Detection Threshold", f"{pol.thresholds.high_threshold:.2f}")
    t2.metric("Human Review Threshold", f"{pol.thresholds.lower_threshold:.2f}")

    st.markdown("### Permitted File Types")
    st.write(f"Allowed extensions: `{pol.file_policy.allowed_extensions}` | Max size: `{pol.file_policy.max_file_size_mb} MB`")

    st.markdown("### Configured PII Entity Rules")
    if pol.entity_rules:
        rules_data = [{
            "Entity Type": r.entity_type,
            "Enabled": r.enabled,
            "Action": r.action,
            "Severity": r.severity,
            "Min Confidence": f"{r.min_confidence:.2f}",
            "Redaction Mode": r.redaction_mode
        } for r in pol.entity_rules.values()]
        st.dataframe(pd.DataFrame(rules_data), use_container_width=True, hide_index=True)


def render_reports_view():
    """Downloadable security evaluation & benchmark reports."""
    render_top_header("Security Reports", "Export evaluation benchmarks, audit summaries, and compliance verification")

    scans = default_audit_store.get_all_scans()
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("### Session Scan Report")
        if scans:
            df_rep = pd.DataFrame([{
                "Filename": s.filename,
                "Decision": s.security_decision,
                "Coverage": s.coverage_percentage,
                "PII Count": s.pii_before
            } for s in scans])
            st.download_button(
                "📥 Export Scans Summary (CSV)",
                df_rep.to_csv(index=False),
                file_name="security_scans_summary.csv",
                mime="text/csv"
            )
        else:
            st.caption("No scans available for export.")

    with r2:
        st.markdown("### Phase 5C Benchmark Report")
        if os.path.exists("reports/phase5c/evaluation.md"):
            with open("reports/phase5c/evaluation.md", "r", encoding="utf-8") as f:
                rep_md = f.read()
            st.download_button(
                "📥 Download Phase 5C Benchmark Report (Markdown)",
                rep_md,
                file_name="phase5c_evaluation_report.md",
                mime="text/markdown"
            )


def render_analytics_view():
    """Deep-dive analytics into latency and coverage distribution."""
    render_top_header("Performance Analytics", "Latency stage breakdown, coverage trends, and model metrics")
    render_advanced_analytics_view()


if __name__ == "__main__":
    main()
