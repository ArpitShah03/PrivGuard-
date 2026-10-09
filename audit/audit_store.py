import os
import sqlite3
import json
import time
import contextlib
from typing import List, Dict, Any, Optional
from audit.models import ScanRecord, FindingAuditRecord, AuditEvent, HumanReviewRecord
from reporting.audit_hasher import AuditHasher, GENESIS_HASH

DEFAULT_DB_PATH = os.path.join("data", "audit.db")


class AuditStore:
    """
    Lightweight, local, persistent SQLite store for enterprise audit logging.
    Strictly prohibits storage of raw PII or secrets.
    """
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Scan Records Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_records (
                    scan_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    filename TEXT,
                    file_type TEXT,
                    processing_status TEXT,
                    total_blocks INTEGER,
                    inspected_blocks INTEGER,
                    uncertain_blocks INTEGER,
                    coverage_percentage REAL,
                    pii_before INTEGER,
                    pii_after INTEGER,
                    high_risk_residual INTEGER,
                    security_decision TEXT,
                    decision_reason TEXT,
                    sanitized_file_path TEXT,
                    extraction_time_ms REAL,
                    detection_time_ms REAL,
                    redaction_time_ms REAL,
                    rescan_time_ms REAL,
                    total_time_ms REAL
                )
            """)

            # 2. Finding Audit Records Table (ZERO RAW PII)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS finding_audit_records (
                    finding_id TEXT PRIMARY KEY,
                    scan_id TEXT,
                    pii_type TEXT,
                    replacement_token TEXT,
                    confidence REAL,
                    detection_method TEXT,
                    location TEXT,
                    severity TEXT,
                    is_ocr INTEGER,
                    is_masked INTEGER,
                    entity_id TEXT,
                    FOREIGN KEY(scan_id) REFERENCES scan_records(scan_id)
                )
            """)

            # 3. Audit Events Timeline Table (with cryptographic hash chaining)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    scan_id TEXT,
                    timestamp REAL,
                    stage TEXT,
                    status TEXT,
                    message TEXT,
                    metadata_json TEXT,
                    previous_event_hash TEXT,
                    event_hash TEXT,
                    FOREIGN KEY(scan_id) REFERENCES scan_records(scan_id)
                )
            """)

            # Schema migration for existing DB
            cursor.execute("PRAGMA table_info(audit_events)")
            cols = [r["name"] for r in cursor.fetchall()]
            if "previous_event_hash" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN previous_event_hash TEXT")
            if "event_hash" not in cols:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN event_hash TEXT")

            # 4. Human Review Actions Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_review_actions (
                    review_id TEXT PRIMARY KEY,
                    scan_id TEXT,
                    reviewer_id TEXT,
                    action TEXT,
                    justification TEXT,
                    timestamp REAL,
                    previous_decision TEXT,
                    new_decision TEXT,
                    action_hash TEXT,
                    FOREIGN KEY(scan_id) REFERENCES scan_records(scan_id)
                )
            """)

            conn.commit()

    def record_scan(self, scan: ScanRecord):
        """Insert or update a scan audit record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO scan_records (
                    scan_id, timestamp, filename, file_type, processing_status,
                    total_blocks, inspected_blocks, uncertain_blocks, coverage_percentage,
                    pii_before, pii_after, high_risk_residual, security_decision,
                    decision_reason, sanitized_file_path, extraction_time_ms,
                    detection_time_ms, redaction_time_ms, rescan_time_ms, total_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                scan.scan_id, scan.timestamp, scan.filename, scan.file_type, scan.processing_status,
                scan.total_blocks, scan.inspected_blocks, scan.uncertain_blocks, scan.coverage_percentage,
                scan.pii_before, scan.pii_after, scan.high_risk_residual, scan.security_decision,
                scan.decision_reason, scan.sanitized_file_path, scan.extraction_time_ms,
                scan.detection_time_ms, scan.redaction_time_ms, scan.rescan_time_ms, scan.total_time_ms
            ))
            conn.commit()

    def record_finding(self, record: FindingAuditRecord):
        """
        Record finding metadata in audit store.
        STRICT PRIVACY GUARANTEE: Does not accept or store raw text.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO finding_audit_records (
                    finding_id, scan_id, pii_type, replacement_token,
                    confidence, detection_method, location, severity,
                    is_ocr, is_masked, entity_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.finding_id, record.scan_id, record.pii_type, record.replacement_token,
                record.confidence, record.detection_method, record.location, record.severity,
                1 if record.is_ocr else 0, 1 if record.is_masked else 0, record.entity_id
            ))
            conn.commit()

    def record_event(self, event: AuditEvent):
        """Record lifecycle event in audit timeline with SHA-256 hash chaining."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch latest event hash for chaining
            cursor.execute("SELECT event_hash FROM audit_events ORDER BY rowid DESC LIMIT 1")
            last_row = cursor.fetchone()
            prev_hash = (last_row["event_hash"] if last_row and last_row["event_hash"] else GENESIS_HASH)
            event.previous_event_hash = prev_hash

            payload = {
                "event_id": event.event_id,
                "scan_id": event.scan_id,
                "stage": event.stage,
                "status": event.status,
                "message": event.message,
                "metadata": event.metadata
            }
            event.event_hash = AuditHasher.compute_hash(
                previous_hash=prev_hash,
                timestamp=event.timestamp,
                event_type=event.stage,
                payload=payload
            )

            cursor.execute("""
                INSERT OR REPLACE INTO audit_events (
                    event_id, scan_id, timestamp, stage, status, message, metadata_json,
                    previous_event_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.scan_id, event.timestamp, event.stage,
                event.status, event.message, json.dumps(event.metadata),
                event.previous_event_hash, event.event_hash
            ))
            conn.commit()

    def record_review_action(self, review: HumanReviewRecord):
        """
        Record a human compliance review decision (APPROVE, REJECT, MARK_FALSE_POSITIVE, RESCAN)
        with cryptographic integrity verification.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Compute action hash
            action_payload = {
                "review_id": review.review_id,
                "scan_id": review.scan_id,
                "reviewer_id": review.reviewer_id,
                "action": review.action,
                "justification": review.justification,
                "previous_decision": review.previous_decision,
                "new_decision": review.new_decision
            }
            review.action_hash = AuditHasher.compute_hash(
                previous_hash=GENESIS_HASH,
                timestamp=review.timestamp,
                event_type="HUMAN_REVIEW_ACTION",
                payload=action_payload
            )

            cursor.execute("""
                INSERT OR REPLACE INTO human_review_actions (
                    review_id, scan_id, reviewer_id, action, justification,
                    timestamp, previous_decision, new_decision, action_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                review.review_id, review.scan_id, review.reviewer_id, review.action,
                review.justification, review.timestamp, review.previous_decision,
                review.new_decision, review.action_hash
            ))

            # Also update security decision in scan_records
            cursor.execute("""
                UPDATE scan_records
                SET security_decision = ?, decision_reason = ?
                WHERE scan_id = ?
            """, (
                review.new_decision,
                f"Human Override by {review.reviewer_id}: {review.justification}",
                review.scan_id
            ))
            conn.commit()

    def get_review_actions(self, scan_id: str) -> List[HumanReviewRecord]:
        """Retrieve all review decisions for a scan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM human_review_actions
                WHERE scan_id = ? ORDER BY timestamp ASC
            """, (scan_id,))
            rows = cursor.fetchall()
            actions = []
            for r in rows:
                actions.append(HumanReviewRecord(
                    review_id=r["review_id"],
                    scan_id=r["scan_id"],
                    reviewer_id=r["reviewer_id"],
                    action=r["action"],
                    justification=r["justification"],
                    timestamp=r["timestamp"],
                    previous_decision=r["previous_decision"],
                    new_decision=r["new_decision"],
                    action_hash=r["action_hash"]
                ))
            return actions

    def get_scan(self, scan_id: str) -> Optional[ScanRecord]:
        """Retrieve scan record by scan_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_records WHERE scan_id = ?", (scan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ScanRecord(
                scan_id=row["scan_id"],
                timestamp=row["timestamp"],
                filename=row["filename"],
                file_type=row["file_type"],
                processing_status=row["processing_status"],
                total_blocks=row["total_blocks"],
                inspected_blocks=row["inspected_blocks"],
                uncertain_blocks=row["uncertain_blocks"],
                coverage_percentage=row["coverage_percentage"],
                pii_before=row["pii_before"],
                pii_after=row["pii_after"],
                high_risk_residual=row["high_risk_residual"],
                security_decision=row["security_decision"],
                decision_reason=row["decision_reason"],
                sanitized_file_path=row["sanitized_file_path"],
                extraction_time_ms=row["extraction_time_ms"],
                detection_time_ms=row["detection_time_ms"],
                redaction_time_ms=row["redaction_time_ms"],
                rescan_time_ms=row["rescan_time_ms"],
                total_time_ms=row["total_time_ms"]
            )

    def get_all_scans(self) -> List[ScanRecord]:
        """Retrieve all scan records ordered by timestamp descending."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scan_records ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            scans = []
            for row in rows:
                scans.append(ScanRecord(
                    scan_id=row["scan_id"],
                    timestamp=row["timestamp"],
                    filename=row["filename"],
                    file_type=row["file_type"],
                    processing_status=row["processing_status"],
                    total_blocks=row["total_blocks"],
                    inspected_blocks=row["inspected_blocks"],
                    uncertain_blocks=row["uncertain_blocks"],
                    coverage_percentage=row["coverage_percentage"],
                    pii_before=row["pii_before"],
                    pii_after=row["pii_after"],
                    high_risk_residual=row["high_risk_residual"],
                    security_decision=row["security_decision"],
                    decision_reason=row["decision_reason"],
                    sanitized_file_path=row["sanitized_file_path"],
                    extraction_time_ms=row["extraction_time_ms"],
                    detection_time_ms=row["detection_time_ms"],
                    redaction_time_ms=row["redaction_time_ms"],
                    rescan_time_ms=row["rescan_time_ms"],
                    total_time_ms=row["total_time_ms"]
                ))
            return scans

    def get_findings_for_scan(self, scan_id: str) -> List[FindingAuditRecord]:
        """Retrieve all finding audit records for a given scan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM finding_audit_records WHERE scan_id = ?", (scan_id,))
            rows = cursor.fetchall()
            records = []
            for r in rows:
                records.append(FindingAuditRecord(
                    finding_id=r["finding_id"],
                    scan_id=r["scan_id"],
                    pii_type=r["pii_type"],
                    replacement_token=r["replacement_token"],
                    confidence=r["confidence"],
                    detection_method=r["detection_method"],
                    location=r["location"],
                    severity=r["severity"],
                    is_ocr=bool(r["is_ocr"]),
                    is_masked=bool(r["is_masked"]),
                    entity_id=r["entity_id"]
                ))
            return records

    def get_events_for_scan(self, scan_id: str) -> List[AuditEvent]:
        """Retrieve chronological event timeline for a given scan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_events WHERE scan_id = ? ORDER BY timestamp ASC", (scan_id,))
            rows = cursor.fetchall()
            events = []
            for r in rows:
                events.append(AuditEvent(
                    event_id=r["event_id"],
                    scan_id=r["scan_id"],
                    timestamp=r["timestamp"],
                    stage=r["stage"],
                    status=r["status"],
                    message=r["message"],
                    metadata=json.loads(r["metadata_json"]) if r["metadata_json"] else {}
                ))
            return events


default_audit_store = AuditStore()
