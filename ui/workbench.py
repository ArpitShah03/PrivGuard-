import time
import uuid
import streamlit as st
from typing import Optional, List
from models.schemas import DocumentAnalysisResult
from audit.audit_store import default_audit_store
from audit.models import HumanReviewRecord


def render_human_review_workbench(res: DocumentAnalysisResult):
    """
    Actionable compliance reviewer workbench for documents requiring human review.
    Enforces fail-closed: overrides cannot approve documents with high-risk residual PII.
    Logs every override cryptographically into audit store.
    """
    st.markdown("### 👷 Compliance Reviewer Workbench")
    st.caption("Inspect flagged extraction uncertainties and record cryptographically signed compliance decisions.")

    is_human_review = (res.status == "HUMAN_REVIEW")
    val_res = getattr(res, "validation_result", None)
    has_high_risk = val_res.high_risk_residual > 0 if val_res else False
    uncertain_cnt = val_res.uncertain_blocks_count if val_res else 0

    # Decision Banner
    if is_human_review:
        st.warning(f"⚠️ **DOCUMENT AWAITING REVIEW**: {uncertain_cnt} blocks flagged for extraction/visual uncertainty.")
    elif res.status == "SANITIZED":
        st.success(f"🟢 **STATUS: SANITIZED** (Ready for downstream LLM dispatch)")
    elif res.status == "BLOCKED":
        st.error(f"🔴 **STATUS: BLOCKED** (Document withheld by security gate)")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # Hard Gate Check
    if has_high_risk:
        st.error("⛔ **INVIOLABLE SECURITY GATE ENFORCED**: High-risk residual PII detected post-rescan. Human approval to 'SANITIZED' is cryptographically prohibited by gateway policy.")

    # Review Action Form
    with st.form(key=f"workbench_form_{res.document_id}"):
        st.markdown("#### Review Decision Entry")
        r_col1, r_col2 = st.columns([1, 2])
        with r_col1:
            reviewer_id = st.text_input("Reviewer Officer ID *", value="compliance-officer-01", placeholder="e.g. sec-ops-104")
            action_choice = st.selectbox(
                "Action Decision",
                ["APPROVE (Release as Sanitized)", "REJECT (Mark Blocked)", "REQUEST_RESCAN (Trigger Enhanced OCR)"]
            )
        with r_col2:
            justification = st.text_area(
                "Mandatory Compliance Justification *",
                placeholder="Explain why the flagged uncertainty is safe to release or reason for rejection...",
                help="Audit logs require at least 10 characters of compliance rationale."
            )

        submitted = st.form_submit_button("✍️ Sign & Commit Compliance Action", type="primary")

    if submitted:
        if not reviewer_id.strip():
            st.error("Reviewer Officer ID is required.")
        elif len(justification.strip()) < 10:
            st.error("Justification rationale must be at least 10 characters long.")
        elif "APPROVE" in action_choice and has_high_risk:
            st.error("Action Prohibited: Cannot approve a document containing residual secrets or PII.")
        else:
            action_code = "APPROVE" if "APPROVE" in action_choice else ("REJECT" if "REJECT" in action_choice else "REQUEST_RESCAN")
            new_decision = "SANITIZED" if action_code == "APPROVE" else ("BLOCKED" if action_code == "REJECT" else "HUMAN_REVIEW")

            review_record = HumanReviewRecord(
                review_id=str(uuid.uuid4()),
                scan_id=res.document_id,
                reviewer_id=reviewer_id.strip(),
                action=action_code,
                justification=justification.strip(),
                timestamp=time.time(),
                previous_decision=res.status,
                new_decision=new_decision
            )

            # Record in SQLite audit store
            default_audit_store.record_review_action(review_record)
            res.status = new_decision
            if getattr(res, "validation_result", None):
                res.validation_result.security_decision = new_decision
                res.validation_result.message = f"Human override by {reviewer_id.strip()}: {justification.strip()}"
            if "decision" in res.security_summary:
                res.security_summary["decision"] = new_decision

            st.success(f"✅ Review decision '{action_code}' successfully committed! Action Hash: `{review_record.action_hash[:16]}...`")
            st.rerun()

    # Previous Human Review History for this Document
    review_history = default_audit_store.get_review_actions(res.document_id)
    if review_history:
        st.markdown("---")
        st.markdown("#### 📜 Reviewer Audit Trail")
        for rh in review_history:
            badge_color = "#059669" if rh.action == "APPROVE" else "#DC2626"
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border-left: 4px solid {badge_color}; padding: 10px 14px; margin-bottom: 8px; border-radius: 4px;">
                <div style="font-weight: 600; color: #0F172A;">Action: {rh.action} by <code>{rh.reviewer_id}</code></div>
                <div style="font-size: 13px; color: #334155; margin-top: 4px;"><b>Rationale:</b> {rh.justification}</div>
                <div style="font-size: 11px; color: #64748B; margin-top: 4px;">
                    Transition: <b>{rh.previous_decision}</b> ➔ <b>{rh.new_decision}</b> |
                    Hash: <code>{rh.action_hash or 'N/A'}</code>
                </div>
            </div>
            """, unsafe_allow_html=True)
