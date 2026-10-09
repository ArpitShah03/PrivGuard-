import os
from typing import List
from models.schemas import DocumentBlock

ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def read_file_with_fallback(file_path: str) -> tuple[str, str]:
    """Read text file attempting multiple standard encodings."""
    for enc in ENCODINGS_TO_TRY:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    # Final fallback with replacement characters
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(), "utf-8 (replace)"


def extract_txt(file_path: str, document_id: str, original_file_name: str) -> List[DocumentBlock]:
    """
    Normalized TXT extractor with encoding resilience and paragraph metadata.
    Preserves exact backward-compatible location names ('paragraph_1', 'paragraph_2').
    """
    blocks = []
    try:
        content, encoding_used = read_file_with_fallback(file_path)

        # Split by double newlines to retain paragraph separation
        paragraphs = content.split('\n\n')
        order = 0
        for i, para in enumerate(paragraphs):
            para_clean = para.strip()
            if para_clean:
                blocks.append(DocumentBlock(
                    document_id=document_id,
                    file_name=original_file_name,
                    file_type="txt",
                    location=f"paragraph_{i+1}",
                    block_type="text",
                    text=para_clean,
                    order=order,
                    is_ocr=False,
                    ocr_confidence=1.0,
                    metadata={
                        "paragraph_index": i + 1,
                        "source_type": "text_paragraph",
                        "encoding": encoding_used
                    }
                ))
                order += 1
    except Exception as e:
        raise Exception(f"Failed to read TXT file: {str(e)}")

    return blocks
