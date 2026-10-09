import pytest
from detection.regex_detector import detect_regex
from detection.context_rules import detect_context

def test_regex_email():
    text = "Contact me at admin@example.com."
    findings = detect_regex(text)
    
    assert len(findings) == 1
    assert findings[0]["pii_type"] == "EMAIL"
    assert findings[0]["text"] == "admin@example.com"
    
def test_regex_phone():
    text = "Call me maybe: +1 800 555 1234"
    findings = detect_regex(text)
    
    assert len(findings) == 1
    assert findings[0]["pii_type"] == "PHONE"
    assert findings[0]["text"] == "+1 800 555 1234"

def test_context_employee_id():
    text = "Employee Number: E99112"
    findings = detect_context(text)
    
    assert len(findings) == 1
    assert findings[0]["pii_type"] == "EMPLOYEE_ID"
    assert findings[0]["text"] == "E99112"
