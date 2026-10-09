import pytest
from models.schemas import DocumentBlock
from detection.enterprise_patterns import detect_enterprise_patterns
from detection.algorithmic_validators import (
    validate_ssn,
    validate_pan,
    validate_pesel,
    calculate_shannon_entropy
)
from detection.masked_detector import detect_masked_pii
from detection.ocr_normalizer import detect_ocr_repaired_pii
from detection.pii_engine import detect_pii_in_block


# ====================================================================
# 1. National & Government ID Tests
# ====================================================================

def test_ssn_valid_and_invalid_bounds():
    """Verify SSN structural bounds: area, group, and serial validation."""
    # Valid SSN
    assert validate_ssn("123-45-6789") is True

    # Invalid area codes
    assert validate_ssn("000-45-6789") is False
    assert validate_ssn("666-45-6789") is False
    assert validate_ssn("900-45-6789") is False
    assert validate_ssn("999-45-6789") is False

    # Invalid group or serial
    assert validate_ssn("123-00-6789") is False
    assert validate_ssn("123-45-0000") is False

    # In-text detection
    text = "The applicant SSN is 219-45-7821 for tax records."
    findings = detect_enterprise_patterns(text)
    ssn_findings = [f for f in findings if f["pii_type"] == "SSN"]
    assert len(ssn_findings) == 1
    assert ssn_findings[0]["text"] == "219-45-7821"
    assert ssn_findings[0]["confidence"] >= 0.95


def test_pan_tax_entity_types():
    """Verify Indian PAN syntax and 4th character tax entity validation."""
    # Valid Individual PAN (4th char = 'P')
    valid, entity = validate_pan("ABCPE1234K")
    assert valid is True
    assert entity == "Individual"

    # Valid Company PAN (4th char = 'C')
    valid, entity = validate_pan("AAACC9981M")
    assert valid is True
    assert entity == "Company"

    # Invalid 4th character ('X' is not a tax entity)
    valid, entity = validate_pan("ABCXE1234K")
    assert valid is False

    # In-text detection
    text = "Permanent Account Number: BZCPK8892L."
    findings = detect_enterprise_patterns(text)
    pan_findings = [f for f in findings if f["pii_type"] == "PAN"]
    assert len(pan_findings) == 1
    assert pan_findings[0]["text"] == "BZCPK8892L"
    assert pan_findings[0]["severity"] == "CRITICAL"


def test_pesel_checksum_validation():
    """Verify Polish PESEL 11-digit modulus 10 checksum."""
    # Algorithmically valid PESEL: 44051401358
    # Weights: 1, 3, 7, 9, 1, 3, 7, 9, 1, 3
    # Check digit computation:
    # 4*1 + 4*3 + 0*7 + 5*9 + 1*1 + 4*3 + 0*7 + 1*9 + 3*1 + 5*3 = 4+12+0+45+1+12+0+9+3+15 = 101 % 10 = 1 -> (10-1)%10 = 9.
    # Let's verify with an exact calculated PESEL:
    # 9001011236 -> sum: 9*1 + 0 + 0 + 1*9 + 0 + 1*3 + 1*7 + 2*9 + 3*1 + 6*3 = 9+9+3+7+18+3+18 = 67 % 10 = 7 -> (10-7)=3
    valid_pesel = "90010112363"
    assert validate_pesel(valid_pesel) is True

    # Alter check digit -> must fail
    invalid_pesel = "90010112364"
    assert validate_pesel(invalid_pesel) is False

    # In-text detection with context
    text = "Citizen PESEL number: 90010112363."
    findings = detect_enterprise_patterns(text)
    pesel_findings = [f for f in findings if f["pii_type"] == "PESEL"]
    assert len(pesel_findings) == 1
    assert pesel_findings[0]["text"] == "90010112363"


# ====================================================================
# 2. Financial, Corporate & Secret Tests
# ====================================================================

def test_financial_ifsc_and_bank_account():
    """Verify IFSC format and contextual Bank Account detection."""
    text = "Transfer NEFT to IFSC: HDFC0001234, Account No: 987654321098."
    findings = detect_enterprise_patterns(text)

    ifsc = next(f for f in findings if f["pii_type"] == "IFSC")
    assert ifsc["text"] == "HDFC0001234"
    assert ifsc["confidence"] >= 0.95

    acct = next(f for f in findings if f["pii_type"] == "BANK_ACCOUNT")
    assert acct["text"] == "987654321098"
    assert acct["severity"] == "HIGH"


def test_corporate_director_and_vendor_id():
    """Verify DIN (Director ID) and Vendor ID detection."""
    text = "Board DIN: 08451234 approved contract with Vendor ID: VEND-99421."
    findings = detect_enterprise_patterns(text)

    din = next(f for f in findings if f["pii_type"] == "DIRECTOR_ID")
    assert din["text"] == "08451234"

    vendor = next(f for f in findings if f["pii_type"] == "VENDOR_ID")
    assert vendor["text"] == "VEND-99421"


def test_high_entropy_secret_detection():
    """Verify high-entropy API key/secret detection while ignoring low-entropy text."""
    high_entropy_key = "a8f9c2d1e0b4a7c9d3e5f1b2"
    assert calculate_shannon_entropy(high_entropy_key) >= 3.2

    low_entropy = "aaaaaaaaaaaaaaaaaaaa"
    assert calculate_shannon_entropy(low_entropy) < 1.0

    text = f'Config setting: api_key = "{high_entropy_key}"'
    findings = detect_enterprise_patterns(text)
    secret_findings = [f for f in findings if f["pii_type"] == "SECRET"]
    assert len(secret_findings) == 1
    assert secret_findings[0]["text"] == high_entropy_key


# ====================================================================
# 3. Masked PII & OCR Normalization Tests
# ====================================================================

def test_masked_ssn_and_credit_card():
    """Verify partially masked SSN and Credit Card detection."""
    text = "SSN on file is XXX-XX-4421 and credit card is **** **** **** 8821."
    findings = detect_masked_pii(text)

    ssn_masked = next(f for f in findings if f["pii_type"] == "SSN")
    assert ssn_masked["text"] == "XXX-XX-4421"
    assert ssn_masked["is_masked"] is True

    cc_masked = next(f for f in findings if f["pii_type"] == "CREDIT_CARD")
    assert cc_masked["text"] == "**** **** **** 8821"
    assert cc_masked["is_masked"] is True


def test_ocr_corrupted_pan_repair():
    """Verify targeted OCR character repair on candidate PAN."""
    # PAN with OCR character 'I' in place of '1': ABCPEI234K -> repaired to ABCPE1234K
    text = "Tax PAN: ABCPEI234K"
    findings = detect_ocr_repaired_pii(text)
    assert len(findings) == 1
    assert findings[0]["text"] == "ABCPEI234K"
    assert findings[0]["normalized_text"] == "ABCPE1234K"
    assert findings[0]["pii_type"] == "PAN"


def test_block_level_multi_stage_integration():
    """Verify end-to-end detection on a DocumentBlock with precedence merging."""
    block = DocumentBlock(
        document_id="d1",
        file_name="test.txt",
        file_type="txt",
        location="para_1",
        block_type="text",
        text="Employee ID: EMP-10492, PAN: ABCPE1234K, SSN: 219-45-7821.",
        order=0
    )
    findings = detect_pii_in_block(block)
    types = [f.pii_type for f in findings]
    assert "EMPLOYEE_ID" in types
    assert "PAN" in types
    assert "SSN" in types


def test_conservative_secret_rejection():
    """
    CRITICAL SECURITY CONSTRAINT:
    Entropy alone must not flag strings as secrets.
    Placeholders, sample secrets, UUIDs, and random hashes without prefix MUST NOT be flagged.
    """
    # 1. Sample placeholder
    placeholder_text = 'Config: api_key = "SAMPLE_API_KEY_123456789"'
    findings = detect_enterprise_patterns(placeholder_text)
    assert not any(f["pii_type"] == "SECRET" for f in findings)

    # 2. Standard UUID
    uuid_text = 'Auth: access_token = "12345678-1234-1234-1234-123456789abc"'
    findings = detect_enterprise_patterns(uuid_text)
    assert not any(f["pii_type"] == "SECRET" for f in findings)

    # 3. High-entropy random hash without secret context prefix
    hash_text = "Commit sha: 4f9b8c2d1e0b4a7c9d3e5f1b2a9e8d7c6b5a4321"
    findings = detect_enterprise_patterns(hash_text)
    assert not any(f["pii_type"] == "SECRET" for f in findings)

