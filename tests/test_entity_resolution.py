import pytest
from models.schemas import DocumentBlock, PIIFinding
from detection.entity_resolver import EntityRegistry, EntityResolver
from detection.pii_engine import detect_pii_in_document_blocks
from redaction.redactor import Redactor


def test_entity_merge_with_corroborating_email():
    """
    CRITICAL SECURITY TEST:
    'T. Lindqvist' and 'Tobias Lindqvist' must merge ONLY because they share
    corroborating evidence (email: tlindqvist@cadence.com). Both must receive
    the exact same replacement token.
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock(
        document_id="doc1",
        file_name="org_pack.pptx",
        file_type="pptx",
        location="slide_1_shape_1",
        block_type="text",
        text="Tobias Lindqvist (Email: tlindqvist@cadence.com)",
        order=0
    )
    block2 = DocumentBlock(
        document_id="doc1",
        file_name="org_pack.pptx",
        file_type="pptx",
        location="slide_2_shape_3",
        block_type="text",
        text="Reviewed by T. Lindqvist, Risk Director",
        order=1
    )

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)

    person_findings = [f for f in findings if f.pii_type == "PERSON"]
    assert len(person_findings) == 2

    f1 = person_findings[0]
    f2 = person_findings[1]

    # Must be resolved to the same entity_id and replacement_token
    assert f1.entity_id == f2.entity_id
    assert f1.replacement_token == f2.replacement_token
    assert f2.replacement_token.startswith("[PERSON_")


def test_anti_merge_similar_names_without_evidence():
    """
    CRITICAL SECURITY TEST:
    'John Smith' and 'John Smyth' are similar names but MUST NOT be merged
    without corroborating evidence. They must receive different tokens.
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock(
        document_id="doc2",
        file_name="staff.docx",
        file_type="docx",
        location="table_1_row_1",
        block_type="text",
        text="Auditor: John Smith",
        order=0
    )
    block2 = DocumentBlock(
        document_id="doc2",
        file_name="staff.docx",
        file_type="docx",
        location="table_1_row_2",
        block_type="text",
        text="Analyst: John Smyth",
        order=1
    )

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)
    person_findings = [f for f in findings if f.pii_type == "PERSON"]

    assert len(person_findings) == 2
    f_smith = next(f for f in person_findings if "Smith" in f.text)
    f_smyth = next(f for f in person_findings if "Smyth" in f.text)

    # Must NOT be merged
    assert f_smith.entity_id != f_smyth.entity_id
    assert f_smith.replacement_token != f_smyth.replacement_token
    assert f_smith.replacement_token == "[PERSON_001]"
    assert f_smyth.replacement_token == "[PERSON_002]"


def test_batch_scoped_cross_document_token_consistency():
    """
    Verify that across two documents in the same batch, the same entity
    consistently receives the identical semantic token.
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    # Document A (Org Pack PPTX)
    doc_a_blocks = [
        DocumentBlock("doc_a", "org.pptx", "pptx", "slide_1", "text", "Sarah Connor - sarah.connor@cadence.com", 0)
    ]
    findings_a = detect_pii_in_document_blocks(doc_a_blocks, resolver=resolver)
    sarah_a = next(f for f in findings_a if f.pii_type == "PERSON")

    # Document B (TPRM DOCX)
    doc_b_blocks = [
        DocumentBlock("doc_b", "tprm.docx", "docx", "para_1", "text", "Signed off by S. Connor (sarah.connor@cadence.com)", 0)
    ]
    findings_b = detect_pii_in_document_blocks(doc_b_blocks, resolver=resolver)
    sarah_b = next(f for f in findings_b if f.pii_type == "PERSON")

    # Must share same replacement token across both documents
    assert sarah_a.replacement_token == sarah_b.replacement_token


def test_redactor_applies_resolved_tokens():
    """
    Verify that Redactor.redact_block properly replaces text with the resolved
    replacement_token assigned by EntityResolver.
    """
    block = DocumentBlock("doc3", "policy.txt", "txt", "p1", "text", "Approved by Tobias Lindqvist.", 0)
    finding = PIIFinding(
        finding_id="1", document_id="doc3", file_name="policy.txt", location="p1",
        start=12, end=28, text="Tobias Lindqvist", pii_type="PERSON", confidence=0.95,
        detection_method=["NER"], severity="HIGH", replacement_token="[PERSON_017]"
    )

    redactor = Redactor()
    sanitized_block, _ = redactor.redact_block(block, [finding])

    assert "[PERSON_017]" in sanitized_block.text
    assert "Tobias Lindqvist" not in sanitized_block.text


def test_anti_merge_same_name_with_conflicting_employee_id():
    """
    CRITICAL SECURITY CONSTRAINT:
    Exact same name 'John Smith' MUST NOT be merged if they have conflicting
    employee IDs (EMP-101 vs EMP-102).
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock("doc4", "staff.docx", "docx", "p1", "text", "Auditor: John Smith (Employee ID: EMP-101)", 0)
    block2 = DocumentBlock("doc4", "staff.docx", "docx", "p2", "text", "Engineer: John Smith (Employee ID: EMP-102)", 1)

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)
    persons = [f for f in findings if f.pii_type == "PERSON"]

    assert len(persons) == 2
    assert persons[0].entity_id != persons[1].entity_id
    assert persons[0].replacement_token != persons[1].replacement_token


def test_anti_merge_same_name_with_conflicting_email():
    """
    CRITICAL SECURITY CONSTRAINT:
    Exact same name 'Alice Brown' MUST NOT be merged if they have conflicting
    email addresses (alice.b@cadence.com vs alice.brown@external.org).
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock("doc5", "staff.docx", "docx", "p1", "text", "Alice Brown (alice.b@cadence.com)", 0)
    block2 = DocumentBlock("doc5", "staff.docx", "docx", "p2", "text", "Alice Brown (alice.brown@external.org)", 1)

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)
    persons = [f for f in findings if f.pii_type == "PERSON"]

    assert len(persons) == 2
    assert persons[0].entity_id != persons[1].entity_id
    assert persons[0].replacement_token != persons[1].replacement_token


def test_anti_merge_common_surname_without_corroborating_evidence():
    """
    CRITICAL SECURITY CONSTRAINT:
    Common surnames (e.g. 'Smith') without corroborating attributes MUST NOT be merged,
    even if the names are identical, because false merges are dangerous.
    """
    registry = EntityRegistry()
    resolver = EntityResolver(registry)

    block1 = DocumentBlock("doc6", "notes.txt", "txt", "p1", "text", "Consultant: David Smith", 0)
    block2 = DocumentBlock("doc6", "notes.txt", "txt", "p2", "text", "Manager: David Smith", 1)

    findings = detect_pii_in_document_blocks([block1, block2], resolver=resolver)
    persons = [f for f in findings if f.pii_type == "PERSON"]

    assert len(persons) == 2
    assert persons[0].entity_id != persons[1].entity_id
    assert persons[0].replacement_token != persons[1].replacement_token

