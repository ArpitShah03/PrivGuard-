import json
import pandas as pd
from typing import List, Dict, Any
from models.schemas import DocumentAnalysisResult

def generate_report_dict(result: DocumentAnalysisResult) -> Dict[str, Any]:
    findings_by_type = {}
    high_risk_count = 0
    
    for f in result.findings:
        findings_by_type[f.pii_type] = findings_by_type.get(f.pii_type, 0) + 1
        if f.severity in ["CRITICAL", "HIGH"]:
            high_risk_count += 1
            
    remaining_count = len(result.validation_result.remaining_findings) if result.validation_result else 0
            
    return {
        "file_name": result.file_name,
        "file_type": result.file_type,
        "status": result.status,
        "total_pii_detected": len(result.findings),
        "high_risk_pii": high_risk_count,
        "pii_breakdown": findings_by_type,
        "remaining_pii_after_redaction": remaining_count,
        "uncertain_blocks": result.validation_result.uncertain_blocks_count if result.validation_result else 0,
        "sanitized_file_path": getattr(result, "sanitized_file_path", None),
        "validation_message": result.validation_result.message if result.validation_result else "",
        "error": result.error_message
    }

def generate_json_report(results: List[DocumentAnalysisResult]) -> str:
    report_data = [generate_report_dict(r) for r in results]
    return json.dumps(report_data, indent=2)

def generate_csv_report(results: List[DocumentAnalysisResult]) -> str:
    report_data = [generate_report_dict(r) for r in results]
    df = pd.DataFrame(report_data)
    # Convert dicts to strings for CSV
    if 'pii_breakdown' in df.columns:
        df['pii_breakdown'] = df['pii_breakdown'].apply(lambda x: json.dumps(x))
    return df.to_csv(index=False)
