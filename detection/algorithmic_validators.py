import math
from typing import Tuple, Optional


def validate_luhn(number_str: str) -> bool:
    """
    Validate numeric string using the standard ISO/IEC 7812 Luhn algorithm.
    Used for credit cards (Visa, Mastercard, Amex, Discover, etc.).
    """
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            val = d * 2
            checksum += (val - 9) if val > 9 else val
        else:
            checksum += d
    return checksum % 10 == 0


def validate_ssn(ssn_str: str) -> bool:
    """
    Validate US Social Security Number structural rules:
    - 9 digits (AAA-GG-SSSS or AAAGGSSSS)
    - Area (AAA): cannot be 000, 666, or 900-999
    - Group (GG): cannot be 00
    - Serial (SSSS): cannot be 0000
    """
    clean = "".join(c for c in ssn_str if c.isdigit())
    if len(clean) != 9:
        return False

    area = int(clean[:3])
    group = int(clean[3:5])
    serial = int(clean[5:9])

    if area == 0 or area == 666 or area >= 900:
        return False
    if group == 0:
        return False
    if serial == 0:
        return False

    return True


PAN_ENTITY_TYPES = {
    'P': 'Individual',
    'C': 'Company',
    'H': 'HUF (Hindu Undivided Family)',
    'F': 'Firm / Partnership',
    'A': 'Association of Persons (AOP)',
    'T': 'Trust',
    'B': 'Body of Individuals (BOI)',
    'L': 'Local Authority',
    'J': 'Artificial Juridical Person',
    'G': 'Government Agency'
}


def validate_pan(pan_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Indian Permanent Account Number (PAN):
    - 10 alphanumeric characters: 5 letters + 4 digits + 1 letter (e.g. ABCPE1234K)
    - 4th character denotes tax entity type (P, C, H, F, A, T, B, L, J, G)
    - 5th character is typically first letter of surname/entity name
    """
    clean = pan_str.strip().upper()
    if len(clean) != 10:
        return False, None

    if not clean[:3].isalpha():
        return False, None

    entity_char = clean[3]
    if entity_char not in PAN_ENTITY_TYPES:
        return False, None

    if not clean[4].isalpha():
        return False, None

    if not clean[5:9].isdigit():
        return False, None

    if not clean[9].isalpha():
        return False, None

    return True, PAN_ENTITY_TYPES[entity_char]


PESEL_WEIGHTS = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]


def validate_pesel(pesel_str: str) -> bool:
    """
    Validate Polish PESEL identification number:
    - Exactly 11 digits
    - Modulus 10 checksum algorithm with weights [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    """
    clean = pesel_str.strip()
    if len(clean) != 11 or not clean.isdigit():
        return False

    digits = [int(c) for c in clean]
    weighted_sum = sum(d * w for d, w in zip(digits[:10], PESEL_WEIGHTS))
    check_digit = (10 - (weighted_sum % 10)) % 10

    return check_digit == digits[10]


def calculate_shannon_entropy(s: str) -> float:
    """
    Calculate the Shannon entropy of a string:
    H(X) = - sum(p(x) * log2(p(x)))
    Higher entropy (> 3.5 for keys >= 20 chars) indicates cryptographic keys/secrets.
    """
    if not s:
        return 0.0
    prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
    return -sum(p * math.log2(p) for p in prob)
