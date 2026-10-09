import random
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class SyntheticSample:
    sample_id: str
    category: str
    text: str
    entities: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_ocr: bool = False


class SyntheticDatasetGenerator:
    """
    Deterministic, reproducible synthetic ground-truth dataset generator.
    Produces controlled test cases covering 16 enterprise PII types,
    algorithmic edge cases, masked formats, and negative false-positive controls.
    """
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_dataset(self) -> List[SyntheticSample]:
        self.rng.seed(self.seed)
        samples: List[SyntheticSample] = []

        # =====================================================================
        # 1. Normal Prose PII (Personnel, Contact & National IDs)
        # =====================================================================
        s1_text = "Senior Director Desmond Achterberg can be contacted at desmond.achterberg@cadence.com or +1-555-019-2834. Born on 1982-05-14 in Chicago, his SSN is 219-45-7821."
        samples.append(SyntheticSample(
            sample_id="synth_001",
            category="normal_prose",
            text=s1_text,
            entities=[
                {"type": "PERSON", "text": "Desmond Achterberg", "start": s1_text.find("Desmond Achterberg"), "end": s1_text.find("Desmond Achterberg") + len("Desmond Achterberg")},
                {"type": "EMAIL", "text": "desmond.achterberg@cadence.com", "start": s1_text.find("desmond.achterberg@cadence.com"), "end": s1_text.find("desmond.achterberg@cadence.com") + len("desmond.achterberg@cadence.com")},
                {"type": "PHONE", "text": "+1-555-019-2834", "start": s1_text.find("+1-555-019-2834"), "end": s1_text.find("+1-555-019-2834") + len("+1-555-019-2834")},
                {"type": "DATE_OF_BIRTH", "text": "1982-05-14", "start": s1_text.find("1982-05-14"), "end": s1_text.find("1982-05-14") + len("1982-05-14")},
                {"type": "ADDRESS", "text": "Chicago", "start": s1_text.find("Chicago"), "end": s1_text.find("Chicago") + len("Chicago")},
                {"type": "SSN", "text": "219-45-7821", "start": s1_text.find("219-45-7821"), "end": s1_text.find("219-45-7821") + len("219-45-7821")}
            ]
        ))

        s2_text = "Compliance reviewer Tobias Lindqvist verified employee Employee ID: EMP-10492 residing in Stockholm."
        samples.append(SyntheticSample(
            sample_id="synth_002",
            category="normal_prose",
            text=s2_text,
            entities=[
                {"type": "PERSON", "text": "Tobias Lindqvist", "start": s2_text.find("Tobias Lindqvist"), "end": s2_text.find("Tobias Lindqvist") + len("Tobias Lindqvist")},
                {"type": "EMPLOYEE_ID", "text": "EMP-10492", "start": s2_text.find("EMP-10492"), "end": s2_text.find("EMP-10492") + len("EMP-10492")},
                {"type": "ADDRESS", "text": "Stockholm", "start": s2_text.find("Stockholm"), "end": s2_text.find("Stockholm") + len("Stockholm")}
            ]
        ))

        s3_text = "Executive Sarah Connor submitted Passport No: Z9182341 for international travel verification."
        samples.append(SyntheticSample(
            sample_id="synth_003",
            category="normal_prose",
            text=s3_text,
            entities=[
                {"type": "PERSON", "text": "Sarah Connor", "start": s3_text.find("Sarah Connor"), "end": s3_text.find("Sarah Connor") + len("Sarah Connor")},
                {"type": "PASSPORT", "text": "Z9182341", "start": s3_text.find("Z9182341"), "end": s3_text.find("Z9182341") + len("Z9182341")}
            ]
        ))

        # =====================================================================
        # 2. Financial & Banking Identifiers
        # =====================================================================
        s4_text = "Remit payment to IFSC: HDFC0001234, checking Account No: 987654321098, billing credit card 4532-0150-1234-5678."
        samples.append(SyntheticSample(
            sample_id="synth_004",
            category="financial_banking",
            text=s4_text,
            entities=[
                {"type": "IFSC", "text": "HDFC0001234", "start": s4_text.find("HDFC0001234"), "end": s4_text.find("HDFC0001234") + len("HDFC0001234")},
                {"type": "BANK_ACCOUNT", "text": "987654321098", "start": s4_text.find("987654321098"), "end": s4_text.find("987654321098") + len("987654321098")},
                {"type": "CREDIT_CARD", "text": "4532-0150-1234-5678", "start": s4_text.find("4532-0150-1234-5678"), "end": s4_text.find("4532-0150-1234-5678") + len("4532-0150-1234-5678")}
            ]
        ))

        # =====================================================================
        # 3. National Tax & Identity Cards (PAN, PESEL)
        # =====================================================================
        s5_text = "Indian tax Permanent Account Number: ABCPE1234K (Individual) and Corporate PAN: AAACC9981M."
        samples.append(SyntheticSample(
            sample_id="synth_005",
            category="national_ids",
            text=s5_text,
            entities=[
                {"type": "PAN", "text": "ABCPE1234K", "start": s5_text.find("ABCPE1234K"), "end": s5_text.find("ABCPE1234K") + len("ABCPE1234K")},
                {"type": "PAN", "text": "AAACC9981M", "start": s5_text.find("AAACC9981M"), "end": s5_text.find("AAACC9981M") + len("AAACC9981M")}
            ]
        ))

        s6_text = "Polish resident citizen with national id PESEL: 90010112363 cleared for Warsaw residency."
        samples.append(SyntheticSample(
            sample_id="synth_006",
            category="national_ids",
            text=s6_text,
            entities=[
                {"type": "PESEL", "text": "90010112363", "start": s6_text.find("90010112363"), "end": s6_text.find("90010112363") + len("90010112363")},
                {"type": "ADDRESS", "text": "Warsaw", "start": s6_text.find("Warsaw"), "end": s6_text.find("Warsaw") + len("Warsaw")}
            ]
        ))

        # =====================================================================
        # 4. Corporate Governance & Third-Party Identifiers
        # =====================================================================
        s7_text = "Board DIN: 08451234 approved agreement with Vendor ID: VEND-99421 and Customer ID: CUST-8812."
        samples.append(SyntheticSample(
            sample_id="synth_007",
            category="corporate_ids",
            text=s7_text,
            entities=[
                {"type": "DIRECTOR_ID", "text": "08451234", "start": s7_text.find("08451234"), "end": s7_text.find("08451234") + len("08451234")},
                {"type": "VENDOR_ID", "text": "VEND-99421", "start": s7_text.find("VEND-99421"), "end": s7_text.find("VEND-99421") + len("VEND-99421")},
                {"type": "CUSTOMER_ID", "text": "CUST-8812", "start": s7_text.find("CUST-8812"), "end": s7_text.find("CUST-8812") + len("CUST-8812")}
            ]
        ))

        s8_text = "Payment gateway routing merchant transaction to MID: MERCH-4412 for settlement."
        samples.append(SyntheticSample(
            sample_id="synth_008",
            category="corporate_ids",
            text=s8_text,
            entities=[
                {"type": "MERCHANT_ID", "text": "MERCH-4412", "start": s8_text.find("MERCH-4412"), "end": s8_text.find("MERCH-4412") + len("MERCH-4412")}
            ]
        ))

        # =====================================================================
        # 5. High-Entropy Secrets & API Keys
        # =====================================================================
        s9_text = 'Production config: api_key = "a8f9c2d1e0b4a7c9d3e5f1b2" and client_secret="k92mB7xL01pQvR4wE8zT3yU6".'
        samples.append(SyntheticSample(
            sample_id="synth_009",
            category="secrets_tokens",
            text=s9_text,
            entities=[
                {"type": "SECRET", "text": "a8f9c2d1e0b4a7c9d3e5f1b2", "start": s9_text.find("a8f9c2d1e0b4a7c9d3e5f1b2"), "end": s9_text.find("a8f9c2d1e0b4a7c9d3e5f1b2") + len("a8f9c2d1e0b4a7c9d3e5f1b2")},
                {"type": "SECRET", "text": "k92mB7xL01pQvR4wE8zT3yU6", "start": s9_text.find("k92mB7xL01pQvR4wE8zT3yU6"), "end": s9_text.find("k92mB7xL01pQvR4wE8zT3yU6") + len("k92mB7xL01pQvR4wE8zT3yU6")}
            ]
        ))

        # =====================================================================
        # 6. Masked PII
        # =====================================================================
        s10_text = "Applicant SSN on record: XXX-XX-4421, secondary card: **** **** **** 8821."
        samples.append(SyntheticSample(
            sample_id="synth_010",
            category="masked_pii",
            text=s10_text,
            entities=[
                {"type": "SSN", "text": "XXX-XX-4421", "start": s10_text.find("XXX-XX-4421"), "end": s10_text.find("XXX-XX-4421") + len("XXX-XX-4421")},
                {"type": "CREDIT_CARD", "text": "**** **** **** 8821", "start": s10_text.find("**** **** **** 8821"), "end": s10_text.find("**** **** **** 8821") + len("**** **** **** 8821")}
            ]
        ))

        # =====================================================================
        # 7. OCR-Corrupted Identifiers (Targeted Normalization)
        # =====================================================================
        s11_text = "Tax PAN recorded on scanned voucher: ABCPEI234K."
        samples.append(SyntheticSample(
            sample_id="synth_011",
            category="ocr_corrupted",
            text=s11_text,
            is_ocr=True,
            entities=[
                {"type": "PAN", "text": "ABCPEI234K", "start": s11_text.find("ABCPEI234K"), "end": s11_text.find("ABCPEI234K") + len("ABCPEI234K")}
            ]
        ))

        # =====================================================================
        # 8. Negative Controls & False Positive Rejections (ZERO entities)
        # =====================================================================
        # Invalid SSN area code 000, 666, 900
        s12_text = "Testing invalid SSN area codes: 000-45-6789, 666-12-3456, 900-33-8821 should be ignored."
        samples.append(SyntheticSample(
            sample_id="synth_012",
            category="negative_controls",
            text=s12_text,
            entities=[]  # Must NOT detect invalid SSNs
        ))

        # Invalid PAN 4th letter 'X'
        s13_text = "Random code ABCXE1234K is not a valid tax entity and must not trigger tax PAN alerts."
        samples.append(SyntheticSample(
            sample_id="synth_013",
            category="negative_controls",
            text=s13_text,
            entities=[]
        ))

        # Invalid Luhn Credit Card (Metadata timestamp)
        s14_text = "Document revision metadata timestamp: 20260917142154 is not a financial card number."
        samples.append(SyntheticSample(
            sample_id="synth_014",
            category="negative_controls",
            text=s14_text,
            entities=[]
        ))

        # Sample secret placeholder and UUID
        s15_text = 'Sample config: api_key = "SAMPLE_API_KEY_123456789" with auth_token="12345678-1234-1234-1234-123456789abc".'
        samples.append(SyntheticSample(
            sample_id="synth_015",
            category="negative_controls",
            text=s15_text,
            entities=[]
        ))

        # Corporate stop words (Optiv, TPRM, Cadence, Workflow)
        s16_text = "The Optiv TPRM Cadence Workflow Policy framework establishes governance and audit standards."
        samples.append(SyntheticSample(
            sample_id="synth_016",
            category="negative_controls",
            text=s16_text,
            entities=[]
        ))

        # Redaction semantic tokens (must NEVER trigger as PII)
        s17_text = "Approved by [PERSON_001] via [EMAIL_001] with SSN [SSN_001] and DIN [DIRECTOR_ID_001]."
        samples.append(SyntheticSample(
            sample_id="synth_017",
            category="negative_controls",
            text=s17_text,
            entities=[]
        ))

        # Invalid PESEL checksum
        s18_text = "Invalid Polish check digit: Citizen id PESEL 90010112364 does not pass modulus 10."
        samples.append(SyntheticSample(
            sample_id="synth_018",
            category="negative_controls",
            text=s18_text,
            entities=[]
        ))

        # =====================================================================
        # 9. Tabular & Grid Business Evidence (Dense Records)
        # =====================================================================
        s19_text = "Row 1 | Marguerite Vossberg | mvossberg@cadence.com | Employee ID: EMP-30421 | Acct: 102938475612"
        samples.append(SyntheticSample(
            sample_id="synth_019",
            category="tabular_evidence",
            text=s19_text,
            entities=[
                {"type": "PERSON", "text": "Marguerite Vossberg", "start": s19_text.find("Marguerite Vossberg"), "end": s19_text.find("Marguerite Vossberg") + len("Marguerite Vossberg")},
                {"type": "EMAIL", "text": "mvossberg@cadence.com", "start": s19_text.find("mvossberg@cadence.com"), "end": s19_text.find("mvossberg@cadence.com") + len("mvossberg@cadence.com")},
                {"type": "EMPLOYEE_ID", "text": "EMP-30421", "start": s19_text.find("EMP-30421"), "end": s19_text.find("EMP-30421") + len("EMP-30421")},
                {"type": "BANK_ACCOUNT", "text": "102938475612", "start": s19_text.find("102938475612"), "end": s19_text.find("102938475612") + len("102938475612")}
            ]
        ))

        s20_text = "Row 2 | Arvind Kumar | arvind.k@cadence.com | PAN: BZCPK8892L | IFSC: SBIN0004521"
        samples.append(SyntheticSample(
            sample_id="synth_020",
            category="tabular_evidence",
            text=s20_text,
            entities=[
                {"type": "PERSON", "text": "Arvind Kumar", "start": s20_text.find("Arvind Kumar"), "end": s20_text.find("Arvind Kumar") + len("Arvind Kumar")},
                {"type": "EMAIL", "text": "arvind.k@cadence.com", "start": s20_text.find("arvind.k@cadence.com"), "end": s20_text.find("arvind.k@cadence.com") + len("arvind.k@cadence.com")},
                {"type": "PAN", "text": "BZCPK8892L", "start": s20_text.find("BZCPK8892L"), "end": s20_text.find("BZCPK8892L") + len("BZCPK8892L")},
                {"type": "IFSC", "text": "SBIN0004521", "start": s20_text.find("SBIN0004521"), "end": s20_text.find("SBIN0004521") + len("SBIN0004521")}
            ]
        ))

        # =====================================================================
        # 10. Multi-Entity Edge Cases & Disambiguation
        # =====================================================================
        s21_text = "Auditor John Smith (Employee ID: EMP-101) interviewed Engineer John Smith (Employee ID: EMP-102)."
        samples.append(SyntheticSample(
            sample_id="synth_021",
            category="entity_resolution_edge_case",
            text=s21_text,
            entities=[
                {"type": "PERSON", "text": "John Smith", "start": 8, "end": 18},
                {"type": "EMPLOYEE_ID", "text": "EMP-101", "start": s21_text.find("EMP-101"), "end": s21_text.find("EMP-101") + len("EMP-101")},
                {"type": "PERSON", "text": "John Smith", "start": s21_text.rfind("John Smith"), "end": s21_text.rfind("John Smith") + len("John Smith")},
                {"type": "EMPLOYEE_ID", "text": "EMP-102", "start": s21_text.find("EMP-102"), "end": s21_text.find("EMP-102") + len("EMP-102")}
            ]
        ))

        s22_text = "Vendor TPRM contact: Supplier ID: VEND-11092 located in Dallas, phone (214) 555-8901."
        samples.append(SyntheticSample(
            sample_id="synth_022",
            category="corporate_ids",
            text=s22_text,
            entities=[
                {"type": "VENDOR_ID", "text": "VEND-11092", "start": s22_text.find("VEND-11092"), "end": s22_text.find("VEND-11092") + len("VEND-11092")},
                {"type": "ADDRESS", "text": "Dallas", "start": s22_text.find("Dallas"), "end": s22_text.find("Dallas") + len("Dallas")},
                {"type": "PHONE", "text": "(214) 555-8901", "start": s22_text.find("(214) 555-8901"), "end": s22_text.find("(214) 555-8901") + len("(214) 555-8901")}
            ]
        ))

        s23_text = "Director identification DIN: 09124418 verified for tax reporting year 2026."
        samples.append(SyntheticSample(
            sample_id="synth_023",
            category="corporate_ids",
            text=s23_text,
            entities=[
                {"type": "DIRECTOR_ID", "text": "09124418", "start": s23_text.find("09124418"), "end": s23_text.find("09124418") + len("09124418")}
            ]
        ))

        s24_text = "Secondary client record: Cust ID: CUST-9021 confirmed transfer of checking acct # 4410982312."
        samples.append(SyntheticSample(
            sample_id="synth_024",
            category="corporate_ids",
            text=s24_text,
            entities=[
                {"type": "CUSTOMER_ID", "text": "CUST-9021", "start": s24_text.find("CUST-9021"), "end": s24_text.find("CUST-9021") + len("CUST-9021")},
                {"type": "BANK_ACCOUNT", "text": "4410982312", "start": s24_text.find("4410982312"), "end": s24_text.find("4410982312") + len("4410982312")}
            ]
        ))

        s25_text = "Authorized token: bearer=d9e8f7a6b5c4d3e2f1a0b9c8 authorized for secure gateway access."
        samples.append(SyntheticSample(
            sample_id="synth_025",
            category="secrets_tokens",
            text=s25_text,
            entities=[
                {"type": "SECRET", "text": "d9e8f7a6b5c4d3e2f1a0b9c8", "start": s25_text.find("d9e8f7a6b5c4d3e2f1a0b9c8"), "end": s25_text.find("d9e8f7a6b5c4d3e2f1a0b9c8") + len("d9e8f7a6b5c4d3e2f1a0b9c8")}
            ]
        ))

        return samples


default_dataset_generator = SyntheticDatasetGenerator(seed=42)
