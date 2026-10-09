import random
from typing import List, Dict, Any
from evaluation.multimodal_dataset.schemas import DatasetSample
from evaluation.multimodal_dataset.scenarios import ScenarioBuilder
from evaluation.multimodal_dataset.validators import validate_dataset


class MultimodalDatasetGenerator:
    """
    Master generator for constructing the deterministic multimodal PII dataset.
    Generates >= 30 samples partitioned into Train (70%), Validation (15%), and Test (15%)
    with guaranteed zero-entity leakage and 20-30% hard negatives.
    """
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_train_samples(self, builder: ScenarioBuilder) -> List[DatasetSample]:
        samples: List[DatasetSample] = []

        # 1. Plain text personnel
        samples.append(builder.build_scenario_a_plain_text(
            person="Vikram Malhotra",
            email="vikram.malhotra@example.com",
            phone="+1-555-019-2041",
            ssn="000-45-7821"
        ))

        # 2. Table PII
        samples.append(builder.build_scenario_b_table_pii(
            rows=[
                {"name": "Kavita Patel", "email": "kavita.patel@example.com", "phone": "+1-555-019-3329", "ifsc": "HDFC0004123"},
                {"name": "Aarav Sen", "email": "aarav.sen@example.com", "phone": "+1-555-019-8812", "ifsc": "ICIC0001928"},
                {"name": "Priya Nair", "email": "priya.nair@example.com", "phone": "+1-555-019-5501", "ifsc": "SBIN0008821"},
            ]
        ))

        # 3. Split across layout (PPTX shapes)
        samples.append(builder.build_scenario_c_split_layout(
            first_name="Marcus",
            last_name="Vance",
            emp_id="EMP-10291",
            dept="Cloud Platform Security"
        ))

        # 4. Org-chart hierarchy (CEO, Manager, Architect)
        samples.append(builder.build_scenario_d_org_chart(
            ceo={"name": "Elena Rostova", "email": "elena.rostova@example.com", "din": "00928341"},
            manager={"name": "Rajesh Khanna", "email": "rkhanna@example.com", "empid": "EMP-77123"},
            engineer={"name": "Arjun Singhania", "empid": "EMP-66102"}
        ))

        # 5. Screenshot OCR
        samples.append(builder.build_scenario_e_screenshot_ocr(
            name="Maya Lin",
            email="maya.lin@example.com",
            phone="+1-555-019-9941",
            emp_id="EMP-55194",
            address="104 Corporate Blvd, Austin, TX"
        ))

        # 6. OCR Noisy
        samples.append(builder.build_scenario_f_ocr_noisy(
            noisy_pan="ABCPEI234K",
            canonical_pan="ABCPE1234K",
            noisy_ssn="000-4S-782I",
            canonical_ssn="000-45-7821"
        ))

        # 7. Masked PII
        samples.append(builder.build_scenario_g_masked_pii(
            masked_ssn="XXX-XX-1234",
            unmasked_ssn="000-12-1234",
            masked_cc="**** **** **** 4512",
            unmasked_cc="4532-0150-1234-4512",
            masked_mail="carlos****@example.com",
            unmasked_mail="carlos.mendoza@example.com"
        ))

        # 8. Indirect identifiers + Secret Key
        samples.append(builder.build_scenario_h_indirect_identifiers(
            emp_id="EMP-44109",
            dept="Treasury Audit Operations",
            mgr_name="Amit Trivedi",
            secret_key="a8f9c2d1e0b4a7c9d3e5f1b29a8c7e6d"
        ))

        # 9. Similar names (Anti-Merge guard)
        samples.append(builder.build_scenario_i_similar_names(
            name1="David Kim",
            name2="David Klein",
            name3="David Kuhn"
        ))

        # 10. Same person variants (Corroborated resolution)
        samples.append(builder.build_scenario_j_same_person_variants(
            full_name="Meera Joshi",
            short_name="M. Joshi",
            email="meera.joshi@example.com",
            emp_id="EMP-33219"
        ))

        # 11. Metadata PII
        samples.append(builder.build_scenario_l_metadata_pii(
            author="Deepak Verma",
            creator_email="deepak.verma@example.com",
            org="Cadence Enterprise Security",
            body="Review findings indicate third-party assessment completed without policy exceptions."
        ))

        # 12. Additional Enterprise National & Financial IDs (PESEL, Passport, PAN, Bank Acct)
        s12_id = builder.next_sample_id()
        ent_nat = builder.next_entity_id()
        p_text = "Polish contractor with PESEL 90051412347, Passport No: Z9182341, Indian Corporate PAN: AAACC9981M, and Account: 987654321098."
        b12 = builder.build_scenario_a_plain_text(
            person="Stanislaw Lem",
            email="stanislaw.lem@example.com",
            phone="+1-555-019-4411",
            ssn="000-88-9911"
        )
        # We can create a dedicated national financial sample
        b12_blk = builder.next_block_id()
        b12_ann1 = builder.next_ann_id()
        b12_ann2 = builder.next_ann_id()
        b12_ann3 = builder.next_ann_id()
        b12_ann4 = builder.next_ann_id()
        sample_12 = DatasetSample(
            sample_id=s12_id,
            split="train",
            category="national_financial",
            document_modality="PDF-LIKE PAGE",
            text_content=p_text,
            document_info=builder.build_scenario_a_plain_text("A", "b@example.com", "1", "000-00-0000").document_info,
            blocks=[
                builder.build_scenario_a_plain_text("A", "b@example.com", "1", "000-00-0000").blocks[0]
            ],
            pii_annotations=[
                builder.build_scenario_a_plain_text("A", "b@example.com", "1", "000-00-0000").pii_annotations[0]
            ]
        )
        # Let's cleanly construct sample 12 properly:
        from evaluation.multimodal_dataset.schemas import DocumentAnnotation, BlockAnnotation, PIIAnnotation, RelationshipAnnotation
        s12_doc = DocumentAnnotation(document_title="Cross-Border Tax & Banking Record", file_type="pdf", total_pages_or_slides=1)
        s12_b1 = BlockAnnotation(builder.next_block_id(), s12_id, "paragraph", p_text, [0.05, 0.10, 0.95, 0.30], 1, 1)
        a_pesel = PIIAnnotation(builder.next_ann_id(), s12_id, "PESEL", "90051412347", "90051412347", [0.25, 0.10, 0.45, 0.15], 1, "native_text", entity_id=ent_nat)
        a_pass = PIIAnnotation(builder.next_ann_id(), s12_id, "PASSPORT", "Z9182341", "Z9182341", [0.55, 0.10, 0.75, 0.15], 1, "native_text", entity_id=ent_nat)
        a_pan = PIIAnnotation(builder.next_ann_id(), s12_id, "PAN", "AAACC9981M", "AAACC9981M", [0.25, 0.18, 0.50, 0.23], 1, "native_text", entity_id=ent_nat)
        a_acct = PIIAnnotation(builder.next_ann_id(), s12_id, "BANK_ACCOUNT", "987654321098", "987654321098", [0.60, 0.18, 0.85, 0.23], 1, "native_text", entity_id=ent_nat)
        r_nat = RelationshipAnnotation(builder.next_rel_id(), s12_id, a_pesel.annotation_id, a_acct.annotation_id, "ASSOCIATED_WITH", "Remittance bank account associated with foreign contractor")
        a_pesel.relationship_ids = [r_nat.relationship_id]
        a_acct.relationship_ids = [r_nat.relationship_id]

        samples.append(DatasetSample(
            sample_id=s12_id, split="train", category="national_financial", document_modality="PDF-LIKE PAGE",
            text_content=p_text, document_info=s12_doc, blocks=[s12_b1],
            pii_annotations=[a_pesel, a_pass, a_pan, a_acct], relationships=[r_nat], visuals=[]
        ))

        # 13. Corporate Vendor & Customer Contract
        s13_id = builder.next_sample_id()
        ent_vend = builder.next_entity_id()
        c_text = "Vendor procurement agreement referencing VENDOR_ID: VEND-49201 and Customer Account: CUST-88102 with Director DIN: 01827364."
        s13_doc = DocumentAnnotation(document_title="Master Services Procurement Agreement", file_type="docx", total_pages_or_slides=1)
        s13_b1 = BlockAnnotation(builder.next_block_id(), s13_id, "paragraph", c_text, [0.05, 0.15, 0.95, 0.35], 1, 1)
        a_vend = PIIAnnotation(builder.next_ann_id(), s13_id, "VENDOR_ID", "VEND-49201", "VEND-49201", [0.35, 0.15, 0.55, 0.20], 1, "native_text", entity_id=ent_vend)
        a_cust = PIIAnnotation(builder.next_ann_id(), s13_id, "CUSTOMER_ID", "CUST-88102", "CUST-88102", [0.70, 0.15, 0.90, 0.20], 1, "native_text", entity_id=ent_vend)
        a_din = PIIAnnotation(builder.next_ann_id(), s13_id, "DIRECTOR_ID", "01827364", "01827364", [0.35, 0.25, 0.55, 0.30], 1, "native_text", entity_id=ent_vend)
        r_corp = RelationshipAnnotation(builder.next_rel_id(), s13_id, a_vend.annotation_id, a_cust.annotation_id, "ASSOCIATED_WITH", "Vendor to customer contracting party linkage")
        a_vend.relationship_ids = [r_corp.relationship_id]
        a_cust.relationship_ids = [r_corp.relationship_id]
        samples.append(DatasetSample(
            sample_id=s13_id, split="train", category="corporate_identifiers", document_modality="DOCX-LIKE PAGE",
            text_content=c_text, document_info=s13_doc, blocks=[s13_b1],
            pii_annotations=[a_vend, a_cust, a_din], relationships=[r_corp], visuals=[]
        ))

        # 14. Second Table with Credit Card & Bank Account
        samples.append(builder.build_scenario_b_table_pii(
            rows=[
                {"name": "Suresh Raina", "email": "suresh.raina@example.com", "phone": "+1-555-019-6632", "ifsc": "KKBK0001829"},
                {"name": "Anil Kumble", "email": "anil.kumble@example.com", "phone": "+1-555-019-7741", "ifsc": "UTIB0002931"},
            ]
        ))

        # 15. Second Plain Text with Address & DOB
        s15_id = builder.next_sample_id()
        ent_dob = builder.next_entity_id()
        d_text = "Executive Pooja Hegde, born on 1987-04-12, currently lives at 45 Residency Road, Bangalore."
        s15_doc = DocumentAnnotation(document_title="Executive Biographical Summary", file_type="txt", total_pages_or_slides=1)
        s15_b1 = BlockAnnotation(builder.next_block_id(), s15_id, "paragraph", d_text, [0.05, 0.10, 0.95, 0.25], 1, 1)
        a_pname = PIIAnnotation(builder.next_ann_id(), s15_id, "PERSON", "Pooja Hegde", "Pooja Hegde", [0.15, 0.10, 0.35, 0.15], 1, "native_text", entity_id=ent_dob)
        a_dob = PIIAnnotation(builder.next_ann_id(), s15_id, "DOB", "1987-04-12", "1987-04-12", [0.45, 0.10, 0.65, 0.15], 1, "native_text", entity_id=ent_dob)
        a_addr = PIIAnnotation(builder.next_ann_id(), s15_id, "ADDRESS", "45 Residency Road, Bangalore", "45 Residency Road, Bangalore", [0.30, 0.18, 0.85, 0.23], 1, "native_text", entity_id=ent_dob)
        r_dob = RelationshipAnnotation(builder.next_rel_id(), s15_id, a_pname.annotation_id, a_dob.annotation_id, "SAME_ENTITY", "Birth date attribute for executive")
        a_pname.relationship_ids = [r_dob.relationship_id]
        a_dob.relationship_ids = [r_dob.relationship_id]
        samples.append(DatasetSample(
            sample_id=s15_id, split="train", category="plain_text", document_modality="TEXT",
            text_content=d_text, document_info=s15_doc, blocks=[s15_b1],
            pii_annotations=[a_pname, a_dob, a_addr], relationships=[r_dob], visuals=[]
        ))

        # 16-21. HARD NEGATIVES (Train split: 6 hard negatives)
        samples.append(builder.build_scenario_k_hard_negative(
            "Enterprise Security Policy",
            "Optiv cybersecurity risk framework mandates multi-factor authentication across all Amazon AWS infrastructure."
        ))
        samples.append(builder.build_scenario_k_hard_negative(
            "Finance Department Overview",
            "The Department of Finance approved annual operational budget allocation under Project 10291."
        ))
        samples.append(builder.build_scenario_k_hard_negative(
            "Employee Handbook 2026",
            "Employee Handbook Section 4.2: Working hours and paid leave entitlements for full-time corporate staff."
        ))
        samples.append(builder.build_scenario_k_hard_negative(
            "Technical Error Log",
            "Database exception code 123456 triggered during query execution on table sys_audit_events."
        ))
        samples.append(builder.build_scenario_k_hard_negative(
            "Release Calendar",
            "Quarterly product release schedule confirmed for effective launch timestamp 2026-10-09."
        ))
        samples.append(builder.build_scenario_k_hard_negative(
            "Public Test Helpdesk",
            "General inquiries regarding public documentation can be submitted to public-support@example.com."
        ))

        # 22-25. Additional positive samples to complete Train partition
        # Plain text with Credit Card
        s22_id = builder.next_sample_id()
        ent_cc = builder.next_entity_id()
        cc_text = "Billing authorization: Sandeep Reddy registered corporate credit card 4532-0150-1234-5678."
        s22_doc = DocumentAnnotation(document_title="Corporate Travel Card Registration", file_type="txt", total_pages_or_slides=1)
        s22_b1 = BlockAnnotation(builder.next_block_id(), s22_id, "paragraph", cc_text, [0.05, 0.10, 0.95, 0.25], 1, 1)
        a_cc_p = PIIAnnotation(builder.next_ann_id(), s22_id, "PERSON", "Sandeep Reddy", "Sandeep Reddy", [0.25, 0.10, 0.45, 0.15], 1, "native_text", entity_id=ent_cc)
        a_cc_num = PIIAnnotation(builder.next_ann_id(), s22_id, "CREDIT_CARD", "4532-0150-1234-5678", "4532-0150-1234-5678", [0.65, 0.10, 0.95, 0.15], 1, "native_text", entity_id=ent_cc)
        r_cc = RelationshipAnnotation(builder.next_rel_id(), s22_id, a_cc_p.annotation_id, a_cc_num.annotation_id, "SAME_ENTITY", "Corporate card assigned to individual")
        a_cc_p.relationship_ids = [r_cc.relationship_id]
        a_cc_num.relationship_ids = [r_cc.relationship_id]
        samples.append(DatasetSample(
            sample_id=s22_id, split="train", category="financial_banking", document_modality="TEXT",
            text_content=cc_text, document_info=s22_doc, blocks=[s22_b1],
            pii_annotations=[a_cc_p, a_cc_num], relationships=[r_cc], visuals=[]
        ))

        # Second Screenshot OCR
        samples.append(builder.build_scenario_e_screenshot_ocr(
            name="Nikhil Kamath",
            email="nikhil.kamath@example.com",
            phone="+1-555-019-1102",
            emp_id="EMP-90214",
            address="77 Tech Park, Hyderabad"
        ))

        # Second Org-Chart
        samples.append(builder.build_scenario_d_org_chart(
            ceo={"name": "Alok Sharma", "email": "alok.sharma@example.com", "din": "01928374"},
            manager={"name": "Kiran Rao", "email": "kiran.rao@example.com", "empid": "EMP-81029"},
            engineer={"name": "Tanvi Shah", "empid": "EMP-71928"}
        ))

        # Second Masked sample
        samples.append(builder.build_scenario_g_masked_pii(
            masked_ssn="98X-XX-XX21",
            unmasked_ssn="000-11-9921",
            masked_cc="4532-XXXX-XXXX-1122",
            unmasked_cc="4532-0150-9988-1122",
            masked_mail="deepa****@example.com",
            unmasked_mail="deepa.narayan@example.com"
        ))

        return samples

    def generate_validation_samples(self, builder: ScenarioBuilder) -> List[DatasetSample]:
        samples: List[DatasetSample] = []

        # 1. Plain text with validation-unique identity
        samples.append(builder.build_scenario_a_plain_text(
            person="Ananya Roy",
            email="ananya.roy@example.com",
            phone="+1-555-011-8273",
            ssn="666-32-1192"
        ))

        # 2. Table PII
        samples.append(builder.build_scenario_b_table_pii(
            rows=[
                {"name": "Devendra Joshi", "email": "devendra.joshi@example.com", "phone": "+1-555-011-9928", "ifsc": "PUNB0001928"},
                {"name": "Clara Schumann", "email": "clara.schumann@example.com", "phone": "+1-555-011-4401", "ifsc": "BARB0003829"},
            ]
        ))

        # 3. Same person variants
        samples.append(builder.build_scenario_j_same_person_variants(
            full_name="Siddharth Rao",
            short_name="S. Rao",
            email="siddharth.rao@example.com",
            emp_id="EMP-20492"
        ))

        # 4. Controlled OCR noise
        samples.append(builder.build_scenario_f_ocr_noisy(
            noisy_pan="AAACC998IM",
            canonical_pan="AAACC9981M",
            noisy_ssn="666-3Z-II92",
            canonical_ssn="666-32-1192"
        ))

        # 5. HARD NEGATIVE (Validation split: 1 hard negative)
        samples.append(builder.build_scenario_k_hard_negative(
            "Corporate Governance Overview",
            "Cadence Risk Committee reviewed internal policy TPRM-6.0 compliance without staffing adjustments."
        ))

        return samples

    def generate_test_samples(self, builder: ScenarioBuilder) -> List[DatasetSample]:
        samples: List[DatasetSample] = []

        # 1. Plain text with test-unique identity
        samples.append(builder.build_scenario_a_plain_text(
            person="Rohan Kapoor",
            email="rohan.kapoor@example.com",
            phone="+1-555-012-9944",
            ssn="900-44-8833"
        ))

        # 2. Org-Chart hierarchy with test identities
        samples.append(builder.build_scenario_d_org_chart(
            ceo={"name": "Sunita Deshmukh", "email": "sunita.deshmukh@example.com", "din": "03948572"},
            manager={"name": "Lucas Lindgren", "email": "lucas.lindgren@example.com", "empid": "EMP-30920"},
            engineer={"name": "Gaurav Sen", "empid": "EMP-30921"}
        ))

        # 3. Same person variants
        samples.append(builder.build_scenario_j_same_person_variants(
            full_name="Farhan Qureshi",
            short_name="F. Qureshi",
            email="farhan.qureshi@example.com",
            emp_id="EMP-30919"
        ))

        # 4. Indirect context + Secret
        samples.append(builder.build_scenario_h_indirect_identifiers(
            emp_id="EMP-30999",
            dept="Enterprise Cloud Vault",
            mgr_name="Manish Sisodia",
            secret_key="b1e2d3c4a5f6e7d8c9b0a1f2e3d4c5b6"
        ))

        # 5. HARD NEGATIVE (Test split: 1 hard negative)
        samples.append(builder.build_scenario_k_hard_negative(
            "Enterprise Architecture Whitepaper",
            "Production Kubernetes cluster deployment relies on Amazon EKS security groups across standard TCP port 443."
        ))

        return samples

    def generate_dataset(self) -> List[DatasetSample]:
        """Generate complete, deterministic, validated dataset with zero leakage."""
        self.rng.seed(self.seed)

        train_builder = ScenarioBuilder(split="train", start_sample_idx=1)
        val_builder = ScenarioBuilder(split="validation", start_sample_idx=1)
        test_builder = ScenarioBuilder(split="test", start_sample_idx=1)

        train_samples = self.generate_train_samples(train_builder)
        val_samples = self.generate_validation_samples(val_builder)
        test_samples = self.generate_test_samples(test_builder)

        all_samples = train_samples + val_samples + test_samples

        # Run strict validation to ensure zero leakage and schema conformance
        validate_dataset(all_samples)

        return all_samples


if __name__ == "__main__":
    import os
    from evaluation.multimodal_dataset.exporters import export_multimodal_dataset
    gen = MultimodalDatasetGenerator(seed=42)
    dataset = gen.generate_dataset()
    paths = export_multimodal_dataset(dataset, base_output_dir=os.path.join("data", "multimodal_dataset"))
    print(f"Generated and exported {len(dataset)} multimodal samples successfully.")
