"""
Job Application Lookup Tool with Formulaic Escalation Scoring.
Track: Naukri.com Recruitment & HR Operations.

Task 6 Requirements:
- Signature: check_job_application_status(record_id: str) -> dict
- Formula:
    escalation_score = 0.5 * I(flagged_priority_review) + 0.5 * (days_since_created / 30)
- Escalation Threshold: tau_esc = 0.65.
- Justification:
  Captures priority-flagged candidates stalled for >9 days (0.5 + 0.5 * 9/30 = 0.65),
  and guarantees that fresh or standard applications remain unescalated unless critical.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

# Project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "job_applications.json"

ESCALATION_THRESHOLD = 0.65
WEIGHT_FLAG = 0.5
WEIGHT_RECENCY = 0.5
MAX_DAYS = 30


def calculate_escalation_score(
    flagged_priority_review: bool,
    days_since_created: int,
    w_flag: float = WEIGHT_FLAG,
    w_recency: float = WEIGHT_RECENCY,
    max_days: int = MAX_DAYS,
) -> float:
    """
    Computes deterministic escalation score in [0.0, 1.0].
    Formula:
        score = w_flag * I(flagged_priority_review) + w_recency * (days_since_created / 30)
    """
    flag_val = 1.0 if flagged_priority_review else 0.0
    recency_factor = min(max(days_since_created / float(max_days), 0.0), 1.0)
    raw_score = (w_flag * flag_val) + (w_recency * recency_factor)
    return round(raw_score, 4)


def load_application_records() -> Dict[str, Dict[str, Any]]:
    """Loads application records indexed by record_id."""
    if not DATA_FILE.exists():
        # Fallback to dynamic dataset generation if file is missing
        from dataset import generate_job_applications, save_dataset
        records = generate_job_applications(seed=42, count=45)
        save_dataset(records, DATA_FILE)
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return {rec["record_id"].upper(): rec for rec in data}


def check_job_application_status(record_id: str) -> Dict[str, Any]:
    """
    Application Lookup Tool for recruitment agents.
    
    Args:
        record_id: Unique candidate application identifier (e.g., 'APP-1001').
        
    Returns:
        Structured dictionary containing application details, salary, and escalation metrics.
    """
    normalized_id = record_id.strip().upper()
    records = load_application_records()

    if normalized_id not in records:
        return {
            "error": f"Application record '{record_id}' not found.",
            "record_id": record_id,
            "found": False,
            "escalation_score": 0.0,
            "escalation_recommended": False,
        }

    raw = records[normalized_id]
    days = int(raw.get("days_since_created", 0))
    is_priority = bool(raw.get("flagged_priority_review", False))

    score = calculate_escalation_score(
        flagged_priority_review=is_priority,
        days_since_created=days,
    )
    is_escalated = bool(score >= ESCALATION_THRESHOLD)

    return {
        "record_id": raw["record_id"],
        "candidate_name": raw["candidate_name"],
        "status": raw["status"],
        "category": raw["category"],
        "expected_salary_inr": raw["expected_salary_inr"],
        "days_since_created": days,
        "flagged_priority_review": is_priority,
        "experience_years": raw.get("experience_years"),
        "location": raw.get("location"),
        "escalation_score": score,
        "escalation_recommended": is_escalated,
        "found": True,
    }


def demonstrate_escalation_lookup() -> None:
    """Executes demonstration protocol required for Task 6 validation."""
    print("=" * 75)
    print("Task 6: Application Lookup Tool with Formulaic Escalation Scoring")
    print("=" * 75)
    print(f"Designed Formula: escalation_score = 0.5 * I(flag) + 0.5 * (days / 30)")
    print(f"Escalation Threshold (tau_esc): {ESCALATION_THRESHOLD}")
    print("=" * 75)

    records = load_application_records()
    
    # Find one record with escalation >= 0.65 and one with escalation < 0.65
    high_rec_id = None
    low_rec_id = None

    for rec_id in sorted(records.keys()):
        res = check_job_application_status(rec_id)
        if res["escalation_recommended"] and high_rec_id is None:
            high_rec_id = rec_id
        elif not res["escalation_recommended"] and low_rec_id is None:
            low_rec_id = rec_id
        if high_rec_id and low_rec_id:
            break

    # Demo 1: High Escalation Application
    print(f"\n[Case 1: Escalation Triggered (>= {ESCALATION_THRESHOLD})]")
    res_high = check_job_application_status(high_rec_id or "APP-1001")
    print(f"  Record ID        : {res_high['record_id']}")
    print(f"  Candidate Name   : {res_high['candidate_name']}")
    print(f"  Category / Status: {res_high['category']} | {res_high['status']}")
    print(f"  Expected Salary  : INR {res_high['expected_salary_inr']:,}")
    print(f"  Days Stalled     : {res_high['days_since_created']} days")
    print(f"  Priority Flag    : {res_high['flagged_priority_review']}")
    print(f"  Formula Breakdown: 0.5 * {1.0 if res_high['flagged_priority_review'] else 0.0} + 0.5 * ({res_high['days_since_created']} / 30)")
    print(f"  Escalation Score : {res_high['escalation_score']:.4f}")
    print(f"  Escalation Action: {'[YES] HR Recruiter Alert Triggered' if res_high['escalation_recommended'] else '[NO]'}")

    # Demo 2: Normal Application (Below Threshold)
    print(f"\n[Case 2: Standard Application (< {ESCALATION_THRESHOLD})]")
    res_low = check_job_application_status(low_rec_id or "APP-1002")
    print(f"  Record ID        : {res_low['record_id']}")
    print(f"  Candidate Name   : {res_low['candidate_name']}")
    print(f"  Category / Status: {res_low['category']} | {res_low['status']}")
    print(f"  Expected Salary  : INR {res_low['expected_salary_inr']:,}")
    print(f"  Days Stalled     : {res_low['days_since_created']} days")
    print(f"  Priority Flag    : {res_low['flagged_priority_review']}")
    print(f"  Formula Breakdown: 0.5 * {1.0 if res_low['flagged_priority_review'] else 0.0} + 0.5 * ({res_low['days_since_created']} / 30)")
    print(f"  Escalation Score : {res_low['escalation_score']:.4f}")
    print(f"  Escalation Action: {'[YES] HR Recruiter Alert Triggered' if res_low['escalation_recommended'] else '[NO] Normal Cadence'}")

    # Demo 3: Non-Existent Record Lookup
    print(f"\n[Case 3: Non-Existent Record Lookup]")
    res_missing = check_job_application_status("APP-9999")
    print(f"  Record ID        : {res_missing['record_id']}")
    print(f"  Found            : {res_missing['found']}")
    print(f"  Error Message    : {res_missing.get('error')}")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_escalation_lookup()
