import os
from typing import List, Dict, Any, Optional
from models.schemas import DocumentBlock

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import docx
except ImportError:
    docx = None

try:
    import pptx
except ImportError:
    pptx = None


def extract_pdf_metadata(file_path: str) -> Dict[str, str]:
    meta = {}
    if not fitz:
        return meta
    doc = None
    try:
        doc = fitz.open(file_path)
        raw_meta = doc.metadata or {}
        for k in ["title", "author", "subject", "creator", "producer", "creationDate", "modDate"]:
            val = raw_meta.get(k)
            if val and str(val).strip():
                meta[k] = str(val).strip()
    except Exception:
        pass
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
    return meta


def extract_docx_metadata(file_path: str) -> Dict[str, str]:
    meta = {}
    if not docx:
        return meta
    try:
        doc = docx.Document(file_path)
        core = doc.core_properties
        for attr in ["author", "last_modified_by", "title", "subject", "comments", "category"]:
            val = getattr(core, attr, None)
            if val and str(val).strip():
                meta[attr] = str(val).strip()
        if core.created:
            meta["created"] = str(core.created)
        if core.modified:
            meta["modified"] = str(core.modified)
    except Exception:
        pass
    return meta


def extract_pptx_metadata(file_path: str) -> Dict[str, str]:
    meta = {}
    if not pptx:
        return meta
    try:
        prs = pptx.Presentation(file_path)
        core = prs.core_properties
        for attr in ["author", "last_modified_by", "title", "subject", "comments", "category"]:
            val = getattr(core, attr, None)
            if val and str(val).strip():
                meta[attr] = str(val).strip()
        if core.created:
            meta["created"] = str(core.created)
        if core.modified:
            meta["modified"] = str(core.modified)
    except Exception:
        pass
    return meta


def extract_metadata_as_blocks(
    file_path: str,
    file_type: str,
    document_id: str,
    original_file_name: str,
    start_order: int = 0
) -> List[DocumentBlock]:
    """
    Extract file metadata and convert key-value pairs into standard DocumentBlocks
    so that downstream PII detection inspects sensitive author/creator metadata.
    """
    meta_dict = {}
    ft = file_type.lower()

    if ft == "pdf":
        meta_dict = extract_pdf_metadata(file_path)
    elif ft == "docx":
        meta_dict = extract_docx_metadata(file_path)
    elif ft == "pptx":
        meta_dict = extract_pptx_metadata(file_path)

    blocks = []
    order = start_order
    for k, v in meta_dict.items():
        if not v:
            continue
        blocks.append(DocumentBlock(
            document_id=document_id,
            file_name=original_file_name,
            file_type=ft,
            location=f"metadata_{k}",
            block_type="metadata",
            text=f"{k}: {v}",
            order=order,
            metadata={"metadata_field": k, "metadata_value": v, "source_type": "metadata"}
        ))
        order += 1

    return blocks
