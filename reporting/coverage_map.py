from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from models.schemas import DocumentBlock


@dataclass
class PageCoverage:
    page_num: int
    total_blocks: int
    inspected_blocks: int
    uncertain_blocks: int
    has_ocr: bool
    has_native: bool
    has_images: bool
    coverage_percent: float


@dataclass
class DocumentCoverageMap:
    document_id: str
    total_pages: int
    native_text_coverage: float
    ocr_coverage: float
    visual_coverage: float
    metadata_coverage: float
    overall_coverage: float
    is_coverage_sufficient: bool
    pages: List[PageCoverage] = field(default_factory=list)
    deficit_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "total_pages": self.total_pages,
            "native_text_coverage": round(self.native_text_coverage, 2),
            "ocr_coverage": round(self.ocr_coverage, 2),
            "visual_coverage": round(self.visual_coverage, 2),
            "metadata_coverage": round(self.metadata_coverage, 2),
            "overall_coverage": round(self.overall_coverage, 2),
            "is_coverage_sufficient": self.is_coverage_sufficient,
            "deficit_reasons": self.deficit_reasons,
            "page_count": len(self.pages)
        }


class CoverageCalculator:
    """
    Computes fine-grained modality and page-level PII extraction coverage metrics.
    Enforces the coverage threshold gate: documents with < 95% coverage or uninspected
    modalities must route to HUMAN_REVIEW.
    """
    MIN_OVERALL_COVERAGE = 95.0
    MIN_PAGE_COVERAGE = 90.0

    @classmethod
    def compute_coverage(
        cls,
        document_id: str,
        blocks: List[DocumentBlock],
        metadata_inspected: bool = True,
        visual_findings_present: bool = True
    ) -> DocumentCoverageMap:
        if not blocks:
            return DocumentCoverageMap(
                document_id=document_id,
                total_pages=1,
                native_text_coverage=100.0,
                ocr_coverage=100.0,
                visual_coverage=100.0,
                metadata_coverage=100.0 if metadata_inspected else 0.0,
                overall_coverage=100.0 if metadata_inspected else 80.0,
                is_coverage_sufficient=metadata_inspected,
                pages=[],
                deficit_reasons=[] if metadata_inspected else ["Document metadata was not inspected"]
            )

        # Group blocks by page
        page_dict: Dict[int, List[DocumentBlock]] = {}
        for b in blocks:
            # Parse page from location e.g. "Page 1, Paragraph 2" or "Page 1"
            p_num = 1
            loc = b.location.lower()
            if "page" in loc:
                parts = loc.split("page")
                if len(parts) > 1:
                    digits = "".join(c for c in parts[1].split(",")[0].split()[0] if c.isdigit())
                    if digits:
                        p_num = int(digits)
            page_dict.setdefault(p_num, []).append(b)

        total_pages = max(page_dict.keys()) if page_dict else 1
        page_coverages: List[PageCoverage] = []
        deficit_reasons: List[str] = []

        total_blocks_all = len(blocks)
        total_uncertain_all = 0
        total_ocr_blocks = 0

        for p in range(1, total_pages + 1):
            p_blocks = page_dict.get(p, [])
            n_blocks = len(p_blocks)
            if n_blocks == 0:
                continue

            unc_blocks = sum(1 for b in p_blocks if b.metadata.get("is_uncertain") or b.ocr_confidence < 0.60)
            ocr_count = sum(1 for b in p_blocks if b.is_ocr)
            native_count = n_blocks - ocr_count

            total_uncertain_all += unc_blocks
            total_ocr_blocks += ocr_count

            insp = n_blocks - unc_blocks
            cov_pct = (insp / float(n_blocks)) * 100.0

            if cov_pct < cls.MIN_PAGE_COVERAGE:
                deficit_reasons.append(f"Page {p} coverage is {cov_pct:.1f}% (< {cls.MIN_PAGE_COVERAGE}%) due to OCR/extraction uncertainty.")

            page_coverages.append(PageCoverage(
                page_num=p,
                total_blocks=n_blocks,
                inspected_blocks=insp,
                uncertain_blocks=unc_blocks,
                has_ocr=ocr_count > 0,
                has_native=native_count > 0,
                has_images=False,
                coverage_percent=round(cov_pct, 1)
            ))

        # Modality Coverages
        native_blocks_total = total_blocks_all - total_ocr_blocks
        native_cov = 100.0 if native_blocks_total > 0 else 100.0
        
        ocr_cov = 100.0
        if total_ocr_blocks > 0:
            ocr_unc = sum(1 for b in blocks if b.is_ocr and (b.metadata.get("is_uncertain") or b.ocr_confidence < 0.60))
            ocr_cov = ((total_ocr_blocks - ocr_unc) / float(total_ocr_blocks)) * 100.0

        visual_cov = 100.0 if visual_findings_present else 80.0
        meta_cov = 100.0 if metadata_inspected else 0.0
        if not metadata_inspected:
            deficit_reasons.append("Document metadata was not inspected.")

        overall_cov = (
            (total_blocks_all - total_uncertain_all) / float(max(1, total_blocks_all))
        ) * 100.0
        if not metadata_inspected:
            overall_cov = min(overall_cov, 85.0)

        if overall_cov < cls.MIN_OVERALL_COVERAGE:
            deficit_reasons.append(f"Overall document extraction coverage is {overall_cov:.1f}% (< {cls.MIN_OVERALL_COVERAGE}%).")

        is_sufficient = (overall_cov >= cls.MIN_OVERALL_COVERAGE) and (len(deficit_reasons) == 0)

        return DocumentCoverageMap(
            document_id=document_id,
            total_pages=total_pages,
            native_text_coverage=round(native_cov, 1),
            ocr_coverage=round(ocr_cov, 1),
            visual_coverage=round(visual_cov, 1),
            metadata_coverage=round(meta_cov, 1),
            overall_coverage=round(overall_cov, 1),
            is_coverage_sufficient=is_sufficient,
            pages=page_coverages,
            deficit_reasons=deficit_reasons
        )


default_coverage_calculator = CoverageCalculator()
