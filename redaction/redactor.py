import re
from typing import List, Dict, Tuple
from models.schemas import PIIFinding, DocumentBlock

class Redactor:
    def __init__(self):
        self.entity_counters = {}
        self.value_to_placeholder = {}

    def get_placeholder(self, pii_type: str, original_text: str) -> str:
        key = (pii_type, original_text.lower())
        if key in self.value_to_placeholder:
            return self.value_to_placeholder[key]
            
        if pii_type not in self.entity_counters:
            self.entity_counters[pii_type] = 1
        else:
            self.entity_counters[pii_type] += 1
            
        count = self.entity_counters[pii_type]
        placeholder = f"[{pii_type}_{count:03d}]"
        
        self.value_to_placeholder[key] = placeholder
        return placeholder

    def redact_block(self, block: DocumentBlock, findings: List[PIIFinding]) -> Tuple[DocumentBlock, Dict[str, str]]:
        if not findings:
             return DocumentBlock(**block.__dict__), self.value_to_placeholder
             
        # Sort findings by start index descending so replacement doesn't shift later indices
        sorted_findings = sorted(findings, key=lambda x: x.start, reverse=True)
        
        text = block.text
        for finding in sorted_findings:
            placeholder = finding.replacement_token if getattr(finding, "replacement_token", None) else self.get_placeholder(finding.pii_type, finding.text)
            text = text[:finding.start] + placeholder + text[finding.end:]
            
        sanitized_block = DocumentBlock(
            document_id=block.document_id,
            file_name=block.file_name,
            file_type=block.file_type,
            location=block.location,
            block_type=block.block_type,
            text=text,
            order=block.order,
            bbox=block.bbox,
            is_ocr=block.is_ocr,
            ocr_confidence=block.ocr_confidence,
            metadata=block.metadata.copy() if block.metadata else {},
            parent_id=block.parent_id
        )
        
        return sanitized_block, self.value_to_placeholder

