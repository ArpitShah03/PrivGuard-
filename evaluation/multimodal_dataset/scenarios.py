from typing import List, Dict, Any, Optional
from evaluation.multimodal_dataset.schemas import (
    DatasetSample,
    DocumentAnnotation,
    BlockAnnotation,
    PIIAnnotation,
    RelationshipAnnotation,
    VisualAnnotation,
)


class ScenarioBuilder:
    """
    Stateful builder for creating deterministic multimodal dataset samples
    with synchronized sequential IDs.
    """
    def __init__(self, split: str, start_sample_idx: int = 1):
        self.split = split
        self.sample_idx = start_sample_idx
        self.ann_counter = 1
        self.block_counter = 1
        self.rel_counter = 1
        self.vis_counter = 1
        self.entity_counter = 1

    def next_sample_id(self) -> str:
        s_id = f"sample_{self.split}_{self.sample_idx:04d}"
        self.sample_idx += 1
        return s_id

    def next_ann_id(self) -> str:
        a_id = f"ann_{self.split}_{self.ann_counter:04d}"
        self.ann_counter += 1
        return a_id

    def next_block_id(self) -> str:
        b_id = f"blk_{self.split}_{self.block_counter:04d}"
        self.block_counter += 1
        return b_id

    def next_rel_id(self) -> str:
        r_id = f"rel_{self.split}_{self.rel_counter:04d}"
        self.rel_counter += 1
        return r_id

    def next_vis_id(self) -> str:
        v_id = f"vis_{self.split}_{self.vis_counter:04d}"
        self.vis_counter += 1
        return v_id

    def next_entity_id(self) -> str:
        e_id = f"entity_{self.split}_{self.entity_counter:04d}"
        self.entity_counter += 1
        return e_id

    # -------------------------------------------------------------------------
    # Scenario A: Plain Text PII
    # -------------------------------------------------------------------------
    def build_scenario_a_plain_text(self, person: str, email: str, phone: str, ssn: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_id = self.next_entity_id()

        text = f"{person} can be contacted at {email} or {phone}. Official SSN on record is {ssn}."
        doc_info = DocumentAnnotation(document_title="Personnel Verification Note", file_type="txt", total_pages_or_slides=1)

        b1 = BlockAnnotation(
            block_id=self.next_block_id(), sample_id=sample_id, block_type="paragraph",
            text=text, bbox=[0.05, 0.10, 0.95, 0.20], page_or_slide=1, order=1
        )

        a1_id = self.next_ann_id()
        a2_id = self.next_ann_id()
        a3_id = self.next_ann_id()
        a4_id = self.next_ann_id()

        ann1 = PIIAnnotation(
            annotation_id=a1_id, sample_id=sample_id, pii_type="PERSON", text=person, normalized_text=person,
            bbox=[0.05, 0.10, 0.25, 0.14], page_or_slide=1, source="native_text", entity_id=ent_id,
            relationship_ids=[]
        )
        ann2 = PIIAnnotation(
            annotation_id=a2_id, sample_id=sample_id, pii_type="EMAIL", text=email, normalized_text=email,
            bbox=[0.40, 0.10, 0.65, 0.14], page_or_slide=1, source="native_text", entity_id=ent_id,
            relationship_ids=[]
        )
        ann3 = PIIAnnotation(
            annotation_id=a3_id, sample_id=sample_id, pii_type="PHONE", text=phone, normalized_text=phone,
            bbox=[0.70, 0.10, 0.90, 0.14], page_or_slide=1, source="native_text", entity_id=ent_id,
            relationship_ids=[]
        )
        ann4 = PIIAnnotation(
            annotation_id=a4_id, sample_id=sample_id, pii_type="SSN", text=ssn, normalized_text=ssn,
            bbox=[0.35, 0.15, 0.55, 0.19], page_or_slide=1, source="native_text", entity_id=ent_id,
            relationship_ids=[]
        )

        r1 = RelationshipAnnotation(self.next_rel_id(), sample_id, a1_id, a2_id, "SAME_ENTITY", "Identified in same personal statement")
        r2 = RelationshipAnnotation(self.next_rel_id(), sample_id, a1_id, a4_id, "SAME_ENTITY", "Identity to SSN linkage")
        ann1.relationship_ids = [r1.relationship_id, r2.relationship_id]
        ann2.relationship_ids = [r1.relationship_id]
        ann4.relationship_ids = [r2.relationship_id]

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="plain_text", document_modality="TEXT",
            text_content=text, document_info=doc_info, blocks=[b1],
            pii_annotations=[ann1, ann2, ann3, ann4], relationships=[r1, r2], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario B: PII Inside Tables
    # -------------------------------------------------------------------------
    def build_scenario_b_table_pii(
        self,
        rows: List[Dict[str, str]],
        bank_info: Optional[Dict[str, str]] = None
    ) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title="Vendor Disbursement Payroll Table", file_type="docx", total_pages_or_slides=1)

        blocks = []
        anns = []
        rels = []

        # Table header block
        b_hdr = BlockAnnotation(
            block_id=self.next_block_id(), sample_id=sample_id, block_type="table_cell",
            text="Employee Name | Corporate Email | Work Phone | Bank IFSC",
            bbox=[0.05, 0.15, 0.95, 0.20], page_or_slide=1, order=1
        )
        blocks.append(b_hdr)

        y_offset = 0.22
        for r_idx, row in enumerate(rows):
            ent_id = self.next_entity_id()
            y1 = y_offset + (r_idx * 0.08)
            y2 = y1 + 0.06

            row_text = f"{row['name']} | {row['email']} | {row['phone']} | {row['ifsc']}"
            b_row = BlockAnnotation(
                block_id=self.next_block_id(), sample_id=sample_id, block_type="table_cell",
                text=row_text, bbox=[0.05, y1, 0.95, y2], page_or_slide=1, order=r_idx + 2
            )
            blocks.append(b_row)

            a_name_id = self.next_ann_id()
            a_mail_id = self.next_ann_id()
            a_phon_id = self.next_ann_id()
            a_ifsc_id = self.next_ann_id()

            a_name = PIIAnnotation(
                a_name_id, sample_id, "PERSON", row['name'], row['name'],
                [0.05, y1, 0.28, y2], 1, "table", entity_id=ent_id
            )
            a_mail = PIIAnnotation(
                a_mail_id, sample_id, "EMAIL", row['email'], row['email'],
                [0.30, y1, 0.55, y2], 1, "table", entity_id=ent_id
            )
            a_phon = PIIAnnotation(
                a_phon_id, sample_id, "PHONE", row['phone'], row['phone'],
                [0.58, y1, 0.78, y2], 1, "table", entity_id=ent_id
            )
            a_ifsc = PIIAnnotation(
                a_ifsc_id, sample_id, "IFSC", row['ifsc'], row['ifsc'],
                [0.80, y1, 0.95, y2], 1, "table", entity_id=ent_id
            )

            r_same = RelationshipAnnotation(self.next_rel_id(), sample_id, a_name_id, a_mail_id, "SAME_ENTITY", "Table row entity alignment")
            r_loc = RelationshipAnnotation(self.next_rel_id(), sample_id, a_name_id, a_ifsc_id, "ASSOCIATED_WITH", "Remittance banking info for employee")
            a_name.relationship_ids = [r_same.relationship_id, r_loc.relationship_id]
            a_mail.relationship_ids = [r_same.relationship_id]
            a_ifsc.relationship_ids = [r_loc.relationship_id]

            anns.extend([a_name, a_mail, a_phon, a_ifsc])
            rels.extend([r_same, r_loc])

        full_text = "\n".join([b.text for b in blocks])
        v1 = VisualAnnotation(
            visual_id=self.next_vis_id(), sample_id=sample_id, visual_type="table_grid",
            bbox=[0.05, 0.15, 0.95, y_offset + (len(rows) * 0.08)], page_or_slide=1, has_embedded_text=True
        )

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="tabular", document_modality="TABLE",
            text_content=full_text, document_info=doc_info, blocks=blocks,
            pii_annotations=anns, relationships=rels, visuals=[v1]
        )

    # -------------------------------------------------------------------------
    # Scenario C: PII Split Across Layout Elements (PPTX Shape traversal)
    # -------------------------------------------------------------------------
    def build_scenario_c_split_layout(self, first_name: str, last_name: str, emp_id: str, dept: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_id = self.next_entity_id()
        doc_info = DocumentAnnotation(document_title="Leadership Card PPTX", file_type="pptx", total_pages_or_slides=1)

        b1 = BlockAnnotation(self.next_block_id(), sample_id, "shape", first_name, [0.10, 0.20, 0.30, 0.30], 1, 1)
        b2 = BlockAnnotation(self.next_block_id(), sample_id, "shape", last_name, [0.32, 0.20, 0.55, 0.30], 1, 2)
        b3 = BlockAnnotation(self.next_block_id(), sample_id, "shape", f"Employee ID: {emp_id}", [0.10, 0.35, 0.50, 0.45], 1, 3)
        b4 = BlockAnnotation(self.next_block_id(), sample_id, "shape", f"Division: {dept}", [0.10, 0.50, 0.45, 0.60], 1, 4)

        a1_id = self.next_ann_id()
        a2_id = self.next_ann_id()
        a3_id = self.next_ann_id()

        full_name = f"{first_name} {last_name}"
        a1 = PIIAnnotation(a1_id, sample_id, "PERSON", first_name, full_name, [0.10, 0.20, 0.30, 0.30], 1, "shape", is_partial=True, entity_id=ent_id)
        a2 = PIIAnnotation(a2_id, sample_id, "PERSON", last_name, full_name, [0.32, 0.20, 0.55, 0.30], 1, "shape", is_partial=True, entity_id=ent_id)
        a3 = PIIAnnotation(a3_id, sample_id, "EMPLOYEE_ID", emp_id, emp_id, [0.28, 0.35, 0.50, 0.45], 1, "shape", entity_id=ent_id)

        r1 = RelationshipAnnotation(self.next_rel_id(), sample_id, a1_id, a2_id, "SAME_ENTITY", "Split first name and surname across adjacent shapes")
        r2 = RelationshipAnnotation(self.next_rel_id(), sample_id, a1_id, a3_id, "BELONGS_TO", "Shape grouping attaches employee ID to identity")
        a1.relationship_ids = [r1.relationship_id, r2.relationship_id]
        a2.relationship_ids = [r1.relationship_id]
        a3.relationship_ids = [r2.relationship_id]

        full_text = f"{first_name} {last_name}\nEmployee ID: {emp_id}\nDivision: {dept}"
        return DatasetSample(
            sample_id=sample_id, split=self.split, category="split_layout", document_modality="PPTX-LIKE SLIDE",
            text_content=full_text, document_info=doc_info, blocks=[b1, b2, b3, b4],
            pii_annotations=[a1, a2, a3], relationships=[r1, r2], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario D: Org-Chart Style PII (Hierarchy, MANAGES / REPORTS_TO)
    # -------------------------------------------------------------------------
    def build_scenario_d_org_chart(
        self,
        ceo: Dict[str, str],
        manager: Dict[str, str],
        engineer: Dict[str, str]
    ) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title="Corporate Governance Chart", file_type="pptx", total_pages_or_slides=1)

        ent_ceo = self.next_entity_id()
        ent_mgr = self.next_entity_id()
        ent_eng = self.next_entity_id()

        # CEO node at top
        b_ceo = BlockAnnotation(self.next_block_id(), sample_id, "shape", f"Chief Executive: {ceo['name']}\nEmail: {ceo['email']}\nDIN: {ceo['din']}", [0.35, 0.10, 0.65, 0.25], 1, 1)
        # Manager node in middle
        b_mgr = BlockAnnotation(self.next_block_id(), sample_id, "shape", f"VP Operations: {manager['name']}\nEmail: {manager['email']}\nEmp ID: {manager['empid']}", [0.35, 0.40, 0.65, 0.55], 1, 2)
        # Engineer node at bottom
        b_eng = BlockAnnotation(self.next_block_id(), sample_id, "shape", f"Lead Architect: {engineer['name']}\nEmp ID: {engineer['empid']}", [0.35, 0.70, 0.65, 0.85], 1, 3)

        a_ceo_name = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", ceo['name'], ceo['name'], [0.45, 0.10, 0.65, 0.15], 1, "shape", entity_id=ent_ceo)
        a_ceo_mail = PIIAnnotation(self.next_ann_id(), sample_id, "EMAIL", ceo['email'], ceo['email'], [0.42, 0.15, 0.65, 0.20], 1, "shape", entity_id=ent_ceo)
        a_ceo_din = PIIAnnotation(self.next_ann_id(), sample_id, "DIRECTOR_ID", ceo['din'], ceo['din'], [0.42, 0.20, 0.60, 0.25], 1, "shape", entity_id=ent_ceo)

        a_mgr_name = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", manager['name'], manager['name'], [0.45, 0.40, 0.65, 0.45], 1, "shape", entity_id=ent_mgr)
        a_mgr_empid = PIIAnnotation(self.next_ann_id(), sample_id, "EMPLOYEE_ID", manager['empid'], manager['empid'], [0.45, 0.50, 0.62, 0.55], 1, "shape", entity_id=ent_mgr)

        a_eng_name = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", engineer['name'], engineer['name'], [0.45, 0.70, 0.65, 0.75], 1, "shape", entity_id=ent_eng)
        a_eng_empid = PIIAnnotation(self.next_ann_id(), sample_id, "EMPLOYEE_ID", engineer['empid'], engineer['empid'], [0.45, 0.78, 0.62, 0.83], 1, "shape", entity_id=ent_eng)

        # Hierarchy relationships
        r_hier1 = RelationshipAnnotation(self.next_rel_id(), sample_id, a_ceo_name.annotation_id, a_mgr_name.annotation_id, "MANAGES", "Org hierarchy tree link CEO -> VP")
        r_hier2 = RelationshipAnnotation(self.next_rel_id(), sample_id, a_eng_name.annotation_id, a_mgr_name.annotation_id, "REPORTS_TO", "Lead architect reports to VP Operations")

        # Identity relationships
        r_ceo_ident = RelationshipAnnotation(self.next_rel_id(), sample_id, a_ceo_name.annotation_id, a_ceo_din.annotation_id, "SAME_ENTITY", "Director ID belongs to CEO")
        a_ceo_name.relationship_ids = [r_hier1.relationship_id, r_ceo_ident.relationship_id]
        a_mgr_name.relationship_ids = [r_hier1.relationship_id, r_hier2.relationship_id]
        a_eng_name.relationship_ids = [r_hier2.relationship_id]
        a_ceo_din.relationship_ids = [r_ceo_ident.relationship_id]

        v_org = VisualAnnotation(self.next_vis_id(), sample_id, "diagram", [0.30, 0.08, 0.70, 0.90], 1, has_embedded_text=True)

        full_text = f"{b_ceo.text}\n---\n{b_mgr.text}\n---\n{b_eng.text}"
        return DatasetSample(
            sample_id=sample_id, split=self.split, category="org_chart", document_modality="PPTX-LIKE SLIDE",
            text_content=full_text, document_info=doc_info, blocks=[b_ceo, b_mgr, b_eng],
            pii_annotations=[a_ceo_name, a_ceo_mail, a_ceo_din, a_mgr_name, a_mgr_empid, a_eng_name, a_eng_empid],
            relationships=[r_hier1, r_hier2, r_ceo_ident], visuals=[v_org]
        )

    # -------------------------------------------------------------------------
    # Scenario E: Screenshot-Style Visual PII (OCR Origin)
    # -------------------------------------------------------------------------
    def build_scenario_e_screenshot_ocr(self, name: str, email: str, phone: str, emp_id: str, address: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_id = self.next_entity_id()
        doc_info = DocumentAnnotation(document_title="Internal CRM User Profile Snapshot", file_type="png", total_pages_or_slides=1)

        v_snap = VisualAnnotation(self.next_vis_id(), sample_id, "screenshot", [0.10, 0.15, 0.90, 0.85], 1, has_embedded_text=True, ocr_confidence=0.92)

        ocr_text = f"[CRM PROFILE]\nFull Name: {name}\nAccount Email: {email}\nPhone: {phone}\nBadge: {emp_id}\nOffice: {address}"
        b_ocr = BlockAnnotation(self.next_block_id(), sample_id, "image_region", ocr_text, [0.12, 0.18, 0.88, 0.82], 1, 1, is_ocr=True)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", name, name, [0.25, 0.25, 0.50, 0.30], 1, "OCR", entity_id=ent_id)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "EMAIL", email, email, [0.30, 0.35, 0.65, 0.40], 1, "OCR", entity_id=ent_id)
        a3 = PIIAnnotation(self.next_ann_id(), sample_id, "PHONE", phone, phone, [0.25, 0.45, 0.50, 0.50], 1, "OCR", entity_id=ent_id)
        a4 = PIIAnnotation(self.next_ann_id(), sample_id, "EMPLOYEE_ID", emp_id, emp_id, [0.25, 0.55, 0.45, 0.60], 1, "OCR", entity_id=ent_id)
        a5 = PIIAnnotation(self.next_ann_id(), sample_id, "ADDRESS", address, address, [0.25, 0.65, 0.55, 0.70], 1, "OCR", entity_id=ent_id)

        r_same = RelationshipAnnotation(self.next_rel_id(), sample_id, a1.annotation_id, a2.annotation_id, "SAME_ENTITY", "OCR Card Profile attributes")
        a1.relationship_ids = [r_same.relationship_id]
        a2.relationship_ids = [r_same.relationship_id]

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="screenshot_ocr", document_modality="IMAGE/OCR",
            text_content=ocr_text, document_info=doc_info, blocks=[b_ocr],
            pii_annotations=[a1, a2, a3, a4, a5], relationships=[r_same], visuals=[v_snap]
        )

    # -------------------------------------------------------------------------
    # Scenario F: Controlled OCR Noise (O<->0, I<->1, S<->5)
    # -------------------------------------------------------------------------
    def build_scenario_f_ocr_noisy(self, noisy_pan: str, canonical_pan: str, noisy_ssn: str, canonical_ssn: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title="Scanned National ID Verification", file_type="pdf", total_pages_or_slides=1)

        ocr_content = f"Scanned Record: Tax PAN ID {noisy_pan} and Social Sec {noisy_ssn} detected with optical noise."
        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", ocr_content, [0.05, 0.20, 0.95, 0.35], 1, 1, is_ocr=True)

        a1 = PIIAnnotation(
            self.next_ann_id(), sample_id, "PAN", noisy_pan, canonical_pan,
            [0.25, 0.20, 0.48, 0.26], 1, "OCR"
        )
        a2 = PIIAnnotation(
            self.next_ann_id(), sample_id, "SSN", noisy_ssn, canonical_ssn,
            [0.65, 0.20, 0.88, 0.26], 1, "OCR"
        )

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="ocr_noisy", document_modality="IMAGE/OCR",
            text_content=ocr_content, document_info=doc_info, blocks=[b1],
            pii_annotations=[a1, a2], relationships=[], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario G: Partially Masked PII
    # -------------------------------------------------------------------------
    def build_scenario_g_masked_pii(
        self,
        masked_ssn: str,
        unmasked_ssn: str,
        masked_cc: str,
        unmasked_cc: str,
        masked_mail: str,
        unmasked_mail: str
    ) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title="Customer Account Redacted Statement", file_type="docx", total_pages_or_slides=1)

        text = f"Audit log: Customer verification completed. SSN: {masked_ssn}, Credit Card on file: {masked_cc}, Email confirmation sent to {masked_mail}."
        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", text, [0.05, 0.15, 0.95, 0.30], 1, 1)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "SSN", masked_ssn, unmasked_ssn, [0.45, 0.16, 0.62, 0.21], 1, "native_text", is_masked=True)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "CREDIT_CARD", masked_cc, unmasked_cc, [0.10, 0.22, 0.45, 0.27], 1, "native_text", is_masked=True)
        a3 = PIIAnnotation(self.next_ann_id(), sample_id, "EMAIL", masked_mail, unmasked_mail, [0.65, 0.22, 0.92, 0.27], 1, "native_text", is_masked=True)

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="masked_pii", document_modality="DOCX-LIKE PAGE",
            text_content=text, document_info=doc_info, blocks=[b1],
            pii_annotations=[a1, a2, a3], relationships=[], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario H: Indirect Identifiers (Sensitive Role + Dept + Manager context)
    # -------------------------------------------------------------------------
    def build_scenario_h_indirect_identifiers(self, emp_id: str, dept: str, mgr_name: str, secret_key: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_emp = self.next_entity_id()
        ent_mgr = self.next_entity_id()
        doc_info = DocumentAnnotation(document_title="Privileged Access Request", file_type="docx", total_pages_or_slides=1)

        content = f"Privileged Access Audit:\nEmployee ID: {emp_id}\nAssigned Department: {dept}\nAuthorizing Manager: {mgr_name}\nTemporary Vault Key: {secret_key}"
        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", content, [0.05, 0.10, 0.95, 0.35], 1, 1)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "EMPLOYEE_ID", emp_id, emp_id, [0.25, 0.14, 0.45, 0.18], 1, "native_text", entity_id=ent_emp)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", mgr_name, mgr_name, [0.40, 0.22, 0.65, 0.26], 1, "native_text", entity_id=ent_mgr)
        a3 = PIIAnnotation(self.next_ann_id(), sample_id, "SECRET", secret_key, secret_key, [0.42, 0.28, 0.90, 0.32], 1, "native_text", entity_id=ent_emp)

        r_assoc = RelationshipAnnotation(self.next_rel_id(), sample_id, a1.annotation_id, a2.annotation_id, "REPORTS_TO", "Indirect role linkage to supervising manager")
        r_sec = RelationshipAnnotation(self.next_rel_id(), sample_id, a1.annotation_id, a3.annotation_id, "BELONGS_TO", "Vault key issued to employee")
        a1.relationship_ids = [r_assoc.relationship_id, r_sec.relationship_id]
        a2.relationship_ids = [r_assoc.relationship_id]
        a3.relationship_ids = [r_sec.relationship_id]

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="indirect_context", document_modality="DOCX-LIKE PAGE",
            text_content=content, document_info=doc_info, blocks=[b1],
            pii_annotations=[a1, a2, a3], relationships=[r_assoc, r_sec], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario I: Similar Names (Distinct Entities - Anti-Merge Guard)
    # -------------------------------------------------------------------------
    def build_scenario_i_similar_names(self, name1: str, name2: str, name3: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title="Candidate Evaluation Roster", file_type="docx", total_pages_or_slides=1)

        ent1 = self.next_entity_id()
        ent2 = self.next_entity_id()
        ent3 = self.next_entity_id()

        text = f"Interview Roster for Senior Analyst:\nCandidate 1: {name1} (ID: EMP-101)\nCandidate 2: {name2} (ID: EMP-102)\nCandidate 3: {name3} (ID: EMP-103)"
        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", text, [0.05, 0.10, 0.95, 0.35], 1, 1)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", name1, name1, [0.22, 0.14, 0.45, 0.18], 1, "native_text", entity_id=ent1)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", name2, name2, [0.22, 0.20, 0.45, 0.24], 1, "native_text", entity_id=ent2)
        a3 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", name3, name3, [0.22, 0.26, 0.45, 0.30], 1, "native_text", entity_id=ent3)

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="similar_names", document_modality="DOCX-LIKE PAGE",
            text_content=text, document_info=doc_info, blocks=[b1],
            pii_annotations=[a1, a2, a3], relationships=[], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario J: Same Person Represented Differently (Corroborated Resolution)
    # -------------------------------------------------------------------------
    def build_scenario_j_same_person_variants(self, full_name: str, short_name: str, email: str, emp_id: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_id = self.next_entity_id()
        doc_info = DocumentAnnotation(document_title="Executive Signature Memorandum", file_type="pdf", total_pages_or_slides=1)

        p1_text = f"Memo prepared by {full_name}, reachable at {email}."
        p2_text = f"Approved and countersigned by {short_name} (Badge: {emp_id})."
        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", p1_text, [0.05, 0.15, 0.95, 0.25], 1, 1)
        b2 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", p2_text, [0.05, 0.30, 0.95, 0.40], 1, 2)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", full_name, full_name, [0.35, 0.15, 0.60, 0.20], 1, "native_text", entity_id=ent_id)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "EMAIL", email, email, [0.72, 0.15, 0.95, 0.20], 1, "native_text", entity_id=ent_id)
        a3 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", short_name, full_name, [0.42, 0.30, 0.62, 0.35], 1, "native_text", entity_id=ent_id)
        a4 = PIIAnnotation(self.next_ann_id(), sample_id, "EMPLOYEE_ID", emp_id, emp_id, [0.72, 0.30, 0.90, 0.35], 1, "native_text", entity_id=ent_id)

        r_corrob = RelationshipAnnotation(self.next_rel_id(), sample_id, a1.annotation_id, a3.annotation_id, "SAME_ENTITY", "Variant name resolved via shared employee email/id context")
        a1.relationship_ids = [r_corrob.relationship_id]
        a3.relationship_ids = [r_corrob.relationship_id]

        full_text = f"{p1_text}\n{p2_text}"
        return DatasetSample(
            sample_id=sample_id, split=self.split, category="entity_resolution", document_modality="PDF-LIKE PAGE",
            text_content=full_text, document_info=doc_info, blocks=[b1, b2],
            pii_annotations=[a1, a2, a3, a4], relationships=[r_corrob], visuals=[]
        )

    # -------------------------------------------------------------------------
    # Scenario K: Hard Negatives (Corporate Lookalikes, Numbers, Timestamps)
    # -------------------------------------------------------------------------
    def build_scenario_k_hard_negative(self, title: str, body_text: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        doc_info = DocumentAnnotation(document_title=title, file_type="txt", total_pages_or_slides=1)

        b1 = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", body_text, [0.05, 0.10, 0.95, 0.40], 1, 1)

        return DatasetSample(
            sample_id=sample_id, split=self.split, category="hard_negative", document_modality="TEXT",
            text_content=body_text, document_info=doc_info, blocks=[b1],
            pii_annotations=[], relationships=[], visuals=[], is_hard_negative=True
        )

    # -------------------------------------------------------------------------
    # Scenario L: Metadata PII (Document Properties)
    # -------------------------------------------------------------------------
    def build_scenario_l_metadata_pii(self, author: str, creator_email: str, org: str, body: str) -> DatasetSample:
        sample_id = self.next_sample_id()
        ent_id = self.next_entity_id()
        doc_info = DocumentAnnotation(
            document_title="Quarterly Compliance Review",
            file_type="docx",
            total_pages_or_slides=1,
            metadata_attributes={"author": author, "creator_email": creator_email, "company": org}
        )

        b_meta1 = BlockAnnotation(self.next_block_id(), sample_id, "metadata", f"Author: {author}", [0.0, 0.0, 0.0, 0.0], 1, 1)
        b_meta2 = BlockAnnotation(self.next_block_id(), sample_id, "metadata", f"Creator: {creator_email}", [0.0, 0.0, 0.0, 0.0], 1, 2)
        b_body = BlockAnnotation(self.next_block_id(), sample_id, "paragraph", body, [0.05, 0.15, 0.95, 0.35], 1, 3)

        a1 = PIIAnnotation(self.next_ann_id(), sample_id, "PERSON", author, author, [0.0, 0.0, 0.0, 0.0], 1, "metadata", entity_id=ent_id)
        a2 = PIIAnnotation(self.next_ann_id(), sample_id, "EMAIL", creator_email, creator_email, [0.0, 0.0, 0.0, 0.0], 1, "metadata", entity_id=ent_id)

        r_meta = RelationshipAnnotation(self.next_rel_id(), sample_id, a1.annotation_id, a2.annotation_id, "SAME_ENTITY", "Document author metadata pair")
        a1.relationship_ids = [r_meta.relationship_id]
        a2.relationship_ids = [r_meta.relationship_id]

        full_text = f"[METADATA]\nAuthor: {author}\nCreator: {creator_email}\nCompany: {org}\n[BODY]\n{body}"
        return DatasetSample(
            sample_id=sample_id, split=self.split, category="metadata_pii", document_modality="DOCX-LIKE PAGE",
            text_content=full_text, document_info=doc_info, blocks=[b_meta1, b_meta2, b_body],
            pii_annotations=[a1, a2], relationships=[r_meta], visuals=[]
        )
