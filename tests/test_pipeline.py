import pytest
import os
import uuid
from typing import List

from models.schemas import DocumentBlock, DocumentAnalysisResult
from detection.pii_engine import detect_pii_in_block
from redaction.redactor import Redactor
from redaction.validator import validate_sanitized_blocks

def test_pipeline_text_redaction():
    text = "Contact John Smith at john.smith@example.com or +1 212 555 1234. His Employee ID: EMP12345."
    
    block = DocumentBlock(
        document_id="doc1",
        file_name="test.txt",
        file_type="txt",
        location="paragraph_1",
        block_type="text",
        text=text,
        order=0
    )
    
    # Detect
    findings = detect_pii_in_block(block)
    
    assert len(findings) > 0
    pii_types = [f.pii_type for f in findings]
    
    assert "EMAIL" in pii_types
    assert "PHONE" in pii_types
    assert "EMPLOYEE_ID" in pii_types
    
    # Redact
    redactor = Redactor()
    sanitized_block, placeholder_map = redactor.redact_block(block, findings)
    
    # Validate
    validation = validate_sanitized_blocks("doc1", [sanitized_block])
    
    assert validation.is_safe == True
    assert "john.smith@example.com" not in sanitized_block.text
    assert "[EMAIL_001]" in sanitized_block.text

def test_pipeline_duplicate_merging():
    # Context + NER could both find the same thing
    text = "Employee ID: EMP9999"
    block = DocumentBlock(
        document_id="doc2",
        file_name="test.txt",
        file_type="txt",
        location="paragraph_1",
        block_type="text",
        text=text,
        order=0
    )
    
    findings = detect_pii_in_block(block)
    # The engine should merge and we should only have 1 finding for EMP9999
    
    emp_findings = [f for f in findings if f.pii_type == "EMPLOYEE_ID"]
    assert len(emp_findings) == 1
    assert emp_findings[0].text == "EMP9999"
    
def test_fail_closed_validation():
    # Simulate a redaction failure where PII was missed
    block = DocumentBlock(
        document_id="doc3",
        file_name="test.txt",
        file_type="txt",
        location="paragraph_1",
        block_type="text",
        text="Missed an email: test@example.com",
        order=0
    )
    
    # Validate without redaction
    validation = validate_sanitized_blocks("doc3", [block])
    
    assert validation.is_safe == False
    assert "BLOCKED" in validation.message.upper()
