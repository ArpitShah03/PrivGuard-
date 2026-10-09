import pytest
import os
from extractors.txt_extractor import extract_txt

def test_extract_txt(tmp_path):
    # Create a temporary txt file
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello World\n\nThis is a test paragraph.")
    
    blocks = extract_txt(str(file_path), "doc_1", "test.txt")
    
    assert len(blocks) == 2
    assert blocks[0].text == "Hello World"
    assert blocks[0].location == "paragraph_1"
    
    assert blocks[1].text == "This is a test paragraph."
    assert blocks[1].location == "paragraph_2"
    
# We would add similar tests for PDF, DOCX, and PPTX here, using synthetic test files.
