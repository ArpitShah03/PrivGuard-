from typing import List, Dict, Any, Optional
from audit.models import ScanRecord


def compute_operational_and_security_metrics(scans: List[ScanRecord]) -> Dict[str, Any]:
    """
    Computes operational and security metrics directly from empirical ScanRecord data.
    Strictly separates Extraction Coverage from Detection Recall.
    """
    if not scans:
        return {
            "total_documents_scanned": 0,
            "documents_sanitized": 0,
            "documents_blocked": 0,
            "documents_human_review": 0,
            "sanitization_rate_pct": 0.0,
            "block_rate_pct": 0.0,
            "human_review_rate_pct": 0.0,
            "total_blocks": 0,
            "inspected_blocks": 0,
            "uncertain_blocks": 0,
            "overall_extraction_coverage_pct": 0.0,
            "total_pii_detected_before": 0,
            "total_residual_pii_after": 0,
            "total_high_risk_residual": 0,
            "average_processing_time_ms": 0.0,
            "avg_processing_time_by_type": {},
            "coverage_disclaimer": "Extraction coverage measures content visibility (inspected blocks / total blocks) and is distinct from detection recall."
        }

    total_scanned = len(scans)
    sanitized = sum(1 for s in scans if s.security_decision == "SANITIZED")
    blocked = sum(1 for s in scans if s.security_decision == "BLOCKED")
    human_review = sum(1 for s in scans if s.security_decision == "HUMAN_REVIEW")

    total_blocks = sum(s.total_blocks for s in scans)
    inspected_blocks = sum(s.inspected_blocks for s in scans)
    uncertain_blocks = sum(s.uncertain_blocks for s in scans)

    overall_coverage = round((inspected_blocks / total_blocks * 100.0) if total_blocks > 0 else 100.0, 2)

    pii_before = sum(s.pii_before for s in scans)
    pii_after = sum(s.pii_after for s in scans)
    high_risk_residual = sum(s.high_risk_residual for s in scans)

    # Average timing
    total_times = [s.total_time_ms for s in scans if s.total_time_ms > 0]
    avg_total_time = round(sum(total_times) / len(total_times), 2) if total_times else 0.0

    # Timing by file type
    time_by_type_map = {}
    for s in scans:
        ft = (s.file_type or "unknown").lower()
        if s.total_time_ms > 0:
            time_by_type_map.setdefault(ft, []).append(s.total_time_ms)

    avg_by_type = {
        ft: round(sum(times) / len(times), 2)
        for ft, times in time_by_type_map.items()
    }

    return {
        "total_documents_scanned": total_scanned,
        "documents_sanitized": sanitized,
        "documents_blocked": blocked,
        "documents_human_review": human_review,
        "sanitization_rate_pct": round(sanitized / total_scanned * 100.0, 2),
        "block_rate_pct": round(blocked / total_scanned * 100.0, 2),
        "human_review_rate_pct": round(human_review / total_scanned * 100.0, 2),
        "total_blocks": total_blocks,
        "inspected_blocks": inspected_blocks,
        "uncertain_blocks": uncertain_blocks,
        "overall_extraction_coverage_pct": overall_coverage,
        "total_pii_detected_before": pii_before,
        "total_residual_pii_after": pii_after,
        "total_high_risk_residual": high_risk_residual,
        "average_processing_time_ms": avg_total_time,
        "avg_processing_time_by_type": avg_by_type,
        "coverage_disclaimer": "Extraction coverage measures content visibility (inspected blocks / total blocks) and is distinct from detection recall."
    }
