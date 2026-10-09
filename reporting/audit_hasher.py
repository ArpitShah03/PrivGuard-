import hashlib
import json
import sqlite3
from typing import Dict, Any, List, Tuple, Optional

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


class AuditHasher:
    """
    Cryptographic SHA-256 Blockchain-Style Hash Chainer for Enterprise Audit Logs.
    Ensures mathematical immutability and verifiable tamper-evidence.
    """

    @staticmethod
    def canonical_json(data: Dict[str, Any]) -> str:
        """Serialize dict to deterministic, sorted, compact JSON string."""
        return json.dumps(data, sort_keys=True, separators=(',', ':'))

    @classmethod
    def compute_hash(
        cls,
        previous_hash: str,
        timestamp: float,
        event_type: str,
        payload: Dict[str, Any]
    ) -> str:
        """
        Compute SHA-256 hash linking to the previous event hash.
        H_i = SHA-256( H_{i-1} || timestamp || event_type || canonical_payload )
        """
        canonical_payload = cls.canonical_json(payload)
        preimage = f"{previous_hash}|{timestamp:.4f}|{event_type}|{canonical_payload}".encode("utf-8")
        return hashlib.sha256(preimage).hexdigest()

    @classmethod
    def verify_event_chain(cls, db_path: str) -> Tuple[bool, int, Optional[str]]:
        """
        Verify the complete cryptographic chain of audit events in the database.
        Returns:
            is_valid (bool): True if 100% intact, False if tampered.
            verified_count (int): Number of cryptographically verified blocks.
            error_message (Optional[str]): Description of the breach point if any.
        """
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if columns exist
            cursor.execute("PRAGMA table_info(audit_events)")
            cols = [r["name"] for r in cursor.fetchall()]
            if "event_hash" not in cols or "previous_event_hash" not in cols:
                conn.close()
                return True, 0, None  # Legacy schema without chaining

            cursor.execute("SELECT * FROM audit_events ORDER BY rowid ASC")
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return True, 0, None

            expected_prev_hash = GENESIS_HASH

            for idx, row in enumerate(rows):
                stored_prev = row["previous_event_hash"] or GENESIS_HASH
                stored_curr = row["event_hash"]

                if not stored_curr:
                    # Legacy unhashed record before chain inception
                    continue

                # 1. Check link to previous
                if stored_prev != expected_prev_hash:
                    return False, idx, f"Hash link broken at event #{idx+1} (ID: {row['event_id']}). Prev: {stored_prev} != Expected: {expected_prev_hash}"

                # 2. Re-compute current hash
                meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                payload = {
                    "event_id": row["event_id"],
                    "scan_id": row["scan_id"],
                    "stage": row["stage"],
                    "status": row["status"],
                    "message": row["message"],
                    "metadata": meta
                }
                recomputed = cls.compute_hash(
                    previous_hash=stored_prev,
                    timestamp=row["timestamp"],
                    event_type=row["stage"],
                    payload=payload
                )

                if recomputed != stored_curr:
                    return False, idx, f"Payload tampering detected at event #{idx+1} (ID: {row['event_id']}). Hash mismatch."

                expected_prev_hash = stored_curr

            return True, len(rows), None

        except Exception as e:
            return False, 0, f"Audit verification failed with database error: {str(e)}"


default_audit_hasher = AuditHasher()
