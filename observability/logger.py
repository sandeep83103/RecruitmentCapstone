"""
ELK-Style Structured Logging for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 12 Requirements:
- Format: Single JSON-Lines entry per request written to logs/support_agent.jsonl.
- Data Hygiene Invariant: Input query passes through mask_pii() before being passed
  to the logger. Unmasked phone numbers never touch disk.
- Fields: timestamp, trace_id, endpoint, latency_ms, masked_query, status_code, cached.
- Verification Command (Line 333): cat logs/support_agent.jsonl
  Expected Outcome: JSONL log entries with trace IDs and zero unmasked phone PII.
"""

import json
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from guardrails.pii_masker import mask_pii, has_pii, INDIAN_PHONE_REGEX

_LOG_LOCK = threading.Lock()


class StructuredLogger:
    """
    Thread-safe, ELK-compatible structured JSONL logger enforcing strict
    pre-persistence PII sanitization.
    """

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or config.LOG_FILE_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_request(
        self,
        trace_id: str,
        endpoint: str,
        latency_ms: float,
        query: str,
        status_code: int = 200,
        cached: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Logs a single request/response event as a JSON-Lines entry.

        Data Hygiene Invariant:
        Applies mask_pii() immediately. Unmasked phone numbers never touch disk.
        """
        # Enforce pre-disk PII masking
        masked_query = mask_pii(query)

        # Defense-in-depth verification: no raw phone number should remain
        if has_pii(masked_query):
            # Fallback regex replace to ensure absolute zero leakage
            masked_query = INDIAN_PHONE_REGEX.sub("[PHONE_MASKED]", masked_query)

        timestamp_str = datetime.now(timezone.utc).isoformat()

        entry: Dict[str, Any] = {
            "timestamp": timestamp_str,
            "trace_id": str(trace_id).strip() if trace_id else str(uuid.uuid4()),
            "endpoint": str(endpoint),
            "latency_ms": round(float(latency_ms), 2),
            "masked_query": masked_query,
            "status_code": int(status_code),
            "cached": bool(cached),
        }

        if extra:
            # Mask any strings in extra metadata as well
            for k, v in extra.items():
                if isinstance(v, str):
                    entry[k] = mask_pii(v)
                else:
                    entry[k] = v

        serialized = json.dumps(entry, ensure_ascii=False)

        with _LOG_LOCK:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(serialized + "\n")

        return entry

    def read_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Reads and parses entries from the JSONL log file."""
        if not self.log_path.exists():
            return []

        entries: List[Dict[str, Any]] = []
        with _LOG_LOCK:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        if limit is not None and limit > 0:
            return entries[-limit:]
        return entries

    def clear_logs(self) -> None:
        """Truncates the structured log file for testing."""
        with _LOG_LOCK:
            if self.log_path.exists():
                with open(self.log_path, "w", encoding="utf-8") as f:
                    pass

    def verify_no_unmasked_phone_pii(self) -> bool:
        """
        Verifies that no unmasked Indian phone numbers exist in the log file.
        Returns True if zero unmasked phone PII exists, False otherwise.
        """
        if not self.log_path.exists():
            return True

        with _LOG_LOCK:
            content = self.log_path.read_text(encoding="utf-8")
            return not bool(INDIAN_PHONE_REGEX.search(content))


# Module-level default logger instance
DEFAULT_LOGGER = StructuredLogger()


def log_request(
    trace_id: str,
    endpoint: str,
    latency_ms: float,
    query: str,
    status_code: int = 200,
    cached: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Module-level convenience wrapper for logging structured requests."""
    return DEFAULT_LOGGER.log_request(
        trace_id=trace_id,
        endpoint=endpoint,
        latency_ms=latency_ms,
        query=query,
        status_code=status_code,
        cached=cached,
        extra=extra,
    )


def read_logs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Module-level convenience wrapper to read JSONL logs."""
    return DEFAULT_LOGGER.read_logs(limit=limit)


def verify_no_unmasked_phone_pii() -> bool:
    """Module-level convenience wrapper to verify zero unmasked phone PII in logs."""
    return DEFAULT_LOGGER.verify_no_unmasked_phone_pii()


def demonstrate_structured_logging() -> None:
    """Demonstrates Task 12 structured logging and PII redaction invariants."""
    print("=" * 75)
    print("Task 12: ELK-Style Structured Logging & Pre-Disk PII Redaction Demo")
    print("=" * 75)

    sample_queries = [
        ("POST /ask", 14.25, "What is the probation period duration?", 200, False),
        ("POST /ask", 8.10, "Check candidate at +91 9876543210 for APP-1001", 200, False),
        ("POST /add-document", 22.40, "Upload 13_relocation_allowance.md policy", 200, False),
        ("WS /ws/chat", 5.20, "Call me at +91-9123456789 regarding interview", 200, False),
        ("POST /ask", 0.85, "What is the probation period duration?", 200, True),
    ]

    for ep, lat, q, status, cached in sample_queries:
        tid = str(uuid.uuid4())
        entry = log_request(
            trace_id=tid,
            endpoint=ep,
            latency_ms=lat,
            query=q,
            status_code=status,
            cached=cached,
        )
        print(f"Logged [{entry['endpoint']}] Status: {entry['status_code']} | Latency: {entry['latency_ms']}ms | Masked Query: \"{entry['masked_query']}\"")

    zero_leakage = verify_no_unmasked_phone_pii()
    print("-" * 75)
    print(f"Data Hygiene Invariant (Zero Unmasked Phone PII on disk): {zero_leakage}")
    print(f"Log destination: {config.LOG_FILE_PATH}")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_structured_logging()
