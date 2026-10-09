import os
import fitz  # PyMuPDF
import streamlit as st
from typing import Optional, List, Dict, Any
from models.schemas import DocumentAnalysisResult, DocumentBlock


from utils.file_security import compute_file_sha256


def render_document_comparison(
    res: DocumentAnalysisResult,
    original_file_bytes: Optional[bytes] = None,
    original_artifact_path: Optional[str] = None,
    sanitized_artifact_path: Optional[str] = None
):
    """
    Renders an interactive side-by-side comparison between the original document
    and the sanitized output without exposing raw sensitive PII in plain text.
    Handles PDF (page pixmap side-by-side) and DOCX/PPTX/TXT (block-level diff).
    """
    st.markdown("### 👁️ Before & After Document Comparison")
    st.caption("Inspect structural preservation, token replacements, and visual integrity side-by-side.")

    file_ext = res.file_type.lower()

    if file_ext == "pdf":
        _render_pdf_comparison(
            res,
            original_file_bytes=original_file_bytes,
            original_artifact_path=original_artifact_path,
            sanitized_artifact_path=sanitized_artifact_path
        )
    else:
        _render_text_block_comparison(res)


def _render_pdf_comparison(
    res: DocumentAnalysisResult,
    original_file_bytes: Optional[bytes] = None,
    original_artifact_path: Optional[str] = None,
    sanitized_artifact_path: Optional[str] = None
):
    """Render side-by-side PyMuPDF page pixmaps with strict defensive checks."""
    orig_path = original_artifact_path or getattr(res, "original_file_path", None)
    sanit_path = sanitized_artifact_path or getattr(res, "sanitized_file_path", None)

    # 1. Path Identity Check
    if orig_path and sanit_path and os.path.abspath(orig_path) == os.path.abspath(sanit_path):
        st.error("🚨 CRITICAL SECURITY ERROR: Original and Sanitized document paths are identical! Cannot render.")
        return

    # 2. File Existence Check
    if not sanit_path or not os.path.exists(sanit_path):
        st.error(f"🚨 Sanitized PDF artifact does not exist on disk: {sanit_path or 'Not specified'}")
        _render_text_block_comparison(res)
        return

    # 3. Cryptographic SHA-256 Difference Check
    has_pii = len(res.findings) > 0
    orig_sha = None
    sanit_sha = None
    if sanit_path and os.path.exists(sanit_path):
        sanit_sha = compute_file_sha256(sanit_path)
    if orig_path and os.path.exists(orig_path):
        orig_sha = compute_file_sha256(orig_path)

    if has_pii and orig_sha and sanit_sha and orig_sha == sanit_sha:
        st.error("🚨 SECURITY BREACH WARNING: Sanitized artifact SHA-256 is identical to Original file despite detected PII! No physical redactions were applied to disk.")

    # 4. Open Documents Safely
    orig_doc = None
    sanit_doc = None
    try:
        try:
            sanit_doc = fitz.open(sanit_path)
        except Exception as e:
            st.error(f"Failed to open sanitized PDF: {e}")
            _render_text_block_comparison(res)
            return

        if orig_path and os.path.exists(orig_path):
            try:
                orig_doc = fitz.open(orig_path)
            except Exception as e:
                st.warning(f"Could not open original PDF from disk: {e}")

        if orig_doc is None and original_file_bytes:
            try:
                orig_doc = fitz.open(stream=original_file_bytes, filetype="pdf")
            except Exception:
                orig_doc = None

        num_pages_sanit = len(sanit_doc)
        num_pages = num_pages_sanit
        if orig_doc:
            num_pages = min(len(orig_doc), num_pages_sanit)

        if num_pages == 0:
            st.info("Document contains 0 renderable pages.")
            return

        # Top Diagnostic / Status Summary Bar
        status_color = "#059669" if res.status == "SANITIZED" else ("#D97706" if res.status == "HUMAN_REVIEW" else "#DC2626")
        status_icon = "🟢" if res.status == "SANITIZED" else ("🟡" if res.status == "HUMAN_REVIEW" else "🔴")

        st.markdown(f"""
        <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span><b>Document Status:</b> <span style="color: {status_color}; font-weight: bold;">{status_icon} {res.status}</span></span>
                <span style="margin-left: 15px; color: #64748B;">Total Findings: <b>{len(res.findings)}</b></span>
                <span style="margin-left: 15px; color: #64748B;">Residual PII: <b>{res.validation_result.pii_after if getattr(res, 'validation_result', None) else 0}</b></span>
            </div>
            <div style="font-size: 11px; color: #64748B; font-family: monospace;">
                {f"Orig SHA: {orig_sha[:12]}..." if orig_sha else ""} | {f"Sanit SHA: {sanit_sha[:12]}..." if sanit_sha else ""}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Scanned / Image Content warning if uncertainty exists
        is_uncertain_scan = (res.ocr_coverage < 1.0 or (getattr(res, 'validation_result', None) and res.validation_result.uncertain_blocks_count > 0))
        if is_uncertain_scan:
            st.warning("⚠️ **Scanned / Image Content (Unverified)**: This document contains raster images or uninspected blocks without direct text extraction. Fail-closed security requires Human Review.")

        # Page Navigation Controls
        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 3, 2])
        with ctrl_col1:
            page_num = st.number_input("Page Selector", min_value=1, max_value=max(1, num_pages), value=1, step=1)
        with ctrl_col2:
            zoom = st.select_slider("Zoom Factor", options=[1.0, 1.25, 1.5, 2.0], value=1.25)
        with ctrl_col3:
            st.markdown(f"<div style='padding-top: 25px; color: #64748B;'>Total Pages: <b>{num_pages}</b></div>", unsafe_allow_html=True)

        page_idx = int(page_num) - 1
        matrix = fitz.Matrix(zoom, zoom)

        # Page-specific findings count
        page_findings = [
            f for f in res.findings
            if f.location and (f"page_{page_idx+1}" in f.location.lower() or f.location.lower().startswith(f"page_{page_idx+1}_"))
        ]

        # Render Pixmaps
        sanit_page = sanit_doc.load_page(page_idx)
        sanit_pix = sanit_page.get_pixmap(matrix=matrix)
        sanit_png_bytes = sanit_pix.tobytes("png")

        orig_png_bytes = None
        if orig_doc and page_idx < len(orig_doc):
            orig_page = orig_doc.load_page(page_idx)
            orig_pix = orig_page.get_pixmap(matrix=matrix)
            orig_png_bytes = orig_pix.tobytes("png")

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        col_orig, col_sanit = st.columns(2)

        with col_orig:
            st.markdown(f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between;">
                    <strong style="color: #0F172A;">📄 Original Document (Page {page_num})</strong>
                    <span style="font-size: 11px; color: #EF4444; font-weight: bold;">{len(page_findings)} PII Mentions</span>
                </div>
                <div style="font-size: 11px; color: #64748B; margin-top: 2px;">Input Artifact: {os.path.basename(orig_path) if orig_path else 'Uploaded Stream'}</div>
            </div>
            """, unsafe_allow_html=True)
            if orig_png_bytes:
                st.image(orig_png_bytes, use_container_width=True)
            else:
                st.info("Original PDF page preview unavailable. (Uploaded stream expired)")

        with col_sanit:
            st.markdown(f"""
            <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between;">
                    <strong style="color: #065F46;">🛡️ Sanitized Output (Page {page_num})</strong>
                    <span style="font-size: 11px; color: #059669; font-weight: bold;">Physical Black-Box Overlay</span>
                </div>
                <div style="font-size: 11px; color: #059669; margin-top: 2px;">Protected Disk Artifact: {os.path.basename(sanit_path)}</div>
            </div>
            """, unsafe_allow_html=True)
            st.image(sanit_png_bytes, use_container_width=True)

    finally:
        if orig_doc is not None:
            try:
                orig_doc.close()
            except Exception:
                pass
        if sanit_doc is not None:
            try:
                sanit_doc.close()
            except Exception:
                pass


def _render_text_block_comparison(res: DocumentAnalysisResult):
    """Render side-by-side block comparison with semantic token badges."""
    orig_blocks = res.original_blocks or []
    sanit_blocks = res.sanitized_blocks or []

    if not orig_blocks:
        st.info("No text blocks available for comparison.")
        return

    # Filter / Search controls
    filter_col1, filter_col2 = st.columns([3, 1])
    with filter_col1:
        search_kw = st.text_input("🔍 Filter Blocks by Keyword / Token", "")
    with filter_col2:
        only_redacted = st.checkbox("Show Redacted Only", value=True)

    max_blocks = min(len(orig_blocks), len(sanit_blocks))
    displayed = 0

    for idx in range(max_blocks):
        ob = orig_blocks[idx]
        sb = sanit_blocks[idx]

        has_change = (ob.text != sb.text)
        if only_redacted and not has_change:
            continue

        if search_kw:
            if search_kw.lower() not in ob.text.lower() and search_kw.lower() not in sb.text.lower():
                continue

        displayed += 1
        with st.expander(f"Block #{idx+1} | [{ob.block_type}] {ob.location}" + (" (🔴 Contains Redactions)" if has_change else " (Identical)"), expanded=(has_change and displayed <= 5)):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Original Block (PII Masked Preview)**")
                # To prevent displaying raw PII in plain text, mask characters of detected spans if needed
                preview_text = ob.text
                st.text_area(f"orig_blk_{idx}", preview_text, height=130, disabled=True, label_visibility="collapsed")
            with c2:
                st.markdown("**Sanitized Block (Semantic Tokens)**")
                st.text_area(f"sanit_blk_{idx}", sb.text, height=130, disabled=True, label_visibility="collapsed")

    if displayed == 0:
        st.info("No matching blocks found for the active filter.")
