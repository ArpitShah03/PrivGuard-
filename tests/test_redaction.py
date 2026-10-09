import pytest
from redaction.redactor import Redactor
from models.schemas import DocumentBlock, PIIFinding

def test_redactor_consistency():
    redactor = Redactor()
    
    # First occurrence
    finding1 = PIIFinding(
        finding_id="1", document_id="d1", file_name="test.txt", location="L1",
        start=0, end=10, text="John Smith", pii_type="PERSON", confidence=0.9,
        detection_method=["NER"], severity="HIGH"
    )
    
    # Second occurrence
    finding2 = PIIFinding(
        finding_id="2", document_id="d1", file_name="test.txt", location="L2",
        start=0, end=10, text="John Smith", pii_type="PERSON", confidence=0.9,
        detection_method=["NER"], severity="HIGH"
    )
    
    # Another person
    finding3 = PIIFinding(
        finding_id="3", document_id="d1", file_name="test.txt", location="L3",
        start=0, end=8, text="Jane Doe", pii_type="PERSON", confidence=0.9,
        detection_method=["NER"], severity="HIGH"
    )
    
    p1 = redactor.get_placeholder("PERSON", "John Smith")
    p2 = redactor.get_placeholder("PERSON", "John Smith")
    p3 = redactor.get_placeholder("PERSON", "Jane Doe")
    
    assert p1 == "[PERSON_001]"
    assert p2 == "[PERSON_001]" # Should be consistent
    assert p3 == "[PERSON_002]" # Should increment
