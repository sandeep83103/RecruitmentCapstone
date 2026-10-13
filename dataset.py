"""
Job Application Dataset Generator for Naukri.com Support Agent.
Generates deterministic synthetic application records adhering to recruitment domain constraints.
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List

# Target Categories & Statuses
CATEGORIES = [
    "Software Engineer",
    "Data Analyst",
    "Product Manager",
    "HR Executive",
    "Sales Associate",
]

STATUSES = [
    "Applied",
    "Screening",
    "Interview Scheduled",
    "Offered",
    "Rejected",
]

# Realistic Indian Market CTC Bands (in INR)
SALARY_BANDS = {
    "HR Executive": (350000, 700000),
    "Sales Associate": (350000, 700000),
    "Software Engineer": (800000, 1800000),
    "Data Analyst": (800000, 1800000),
    "Product Manager": (2000000, 4500000),
}

FIRST_NAMES = [
    "Aarav", "Aditi", "Rohan", "Pooja", "Vikram", "Sneha", "Rahul", "Priya",
    "Ananya", "Karan", "Divya", "Arjun", "Meera", "Siddharth", "Neha", "Manish",
    "Ritu", "Deepak", "Tanvi", "Suresh", "Ishaan", "Kavita", "Gaurav", "Swati",
    "Amit", "Nisha", "Rajesh", "Simran", "Varun", "Sunita", "Harsh", "Pallavi",
    "Nikhil", "Shreya", "Abhishek", "Jyoti", "Pranav", "Aarti", "Tarun", "Komal",
    "Mayank", "Preeti", "Sanjay", "Bhavna", "Alok"
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Patel", "Singh", "Kumar", "Iyer", "Nair",
    "Reddy", "Mehta", "Joshi", "Chopra", "Bose", "Das", "Rao", "Mishra"
]

CITIES = ["Bengaluru", "Hyderabad", "Pune", "Gurugram", "Noida", "Mumbai", "Chennai"]


def generate_job_applications(seed: int = 42, count: int = 45) -> List[Dict[str, Any]]:
    """
    Deterministically generates job application records.
    
    Guarantees:
    - count >= 40 (default 45).
    - Every category has >= 3 records.
    - Every status has >= 1 record.
    - Salary matches realistic Indian CTC bands.
    - days_since_created in [0, 30].
    - flagged_priority_review percentage strictly within [10%, 30%].
    """
    random.seed(seed)
    
    # 1. Guarantee category baseline (at least 3 per category)
    assigned_categories = []
    for cat in CATEGORIES:
        assigned_categories.extend([cat] * 3)  # 5 * 3 = 15 records
        
    # Fill remaining categories uniformly/randomly
    remaining_count = count - len(assigned_categories)
    for _ in range(remaining_count):
        assigned_categories.append(random.choice(CATEGORIES))
    random.shuffle(assigned_categories)

    # 2. Guarantee status baseline (at least 1 per status)
    assigned_statuses = list(STATUSES)  # 5 records
    remaining_status_count = count - len(assigned_statuses)
    status_weights = [0.25, 0.25, 0.20, 0.15, 0.15]
    assigned_statuses.extend(random.choices(STATUSES, weights=status_weights, k=remaining_status_count))
    random.shuffle(assigned_statuses)

    # 3. Determine priority flags strictly within [10%, 30%]
    # For count = 45: 10% is 4.5, 30% is 13.5. Let's target exactly ~20% (9 records).
    target_priority_count = round(count * 0.20)
    priority_flags = [True] * target_priority_count + [False] * (count - target_priority_count)
    random.shuffle(priority_flags)

    records: List[Dict[str, Any]] = []

    for i in range(count):
        record_id = f"APP-{1001 + i}"
        category = assigned_categories[i]
        status = assigned_statuses[i]
        is_priority = priority_flags[i]
        
        # Candidate name
        first_name = FIRST_NAMES[i % len(FIRST_NAMES)]
        last_name = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
        candidate_name = f"{first_name} {last_name}"
        
        # Phone number with Indian format (useful for PII guardrail testing)
        phone_suffix = 100000000 + (i * 1234567) % 899999999
        phone_number = f"+91 {9000000000 + (phone_suffix % 999999999)}"

        # Salary in realistic CTC band rounded to nearest 10,000
        min_sal, max_sal = SALARY_BANDS[category]
        raw_sal = random.randint(min_sal, max_sal)
        expected_salary_inr = round(raw_sal / 10000) * 10000

        # Application age in days [0, 30]
        days_since_created = random.randint(0, 30)

        # Experience in years
        if category in ["HR Executive", "Sales Associate"]:
            experience_years = round(random.uniform(1.0, 5.0), 1)
        elif category in ["Software Engineer", "Data Analyst"]:
            experience_years = round(random.uniform(2.0, 8.0), 1)
        else:  # Product Manager
            experience_years = round(random.uniform(4.0, 12.0), 1)

        location = random.choice(CITIES)

        record = {
            "record_id": record_id,
            "candidate_name": candidate_name,
            "contact_phone": phone_number,
            "category": category,
            "status": status,
            "expected_salary_inr": expected_salary_inr,
            "days_since_created": days_since_created,
            "flagged_priority_review": is_priority,
            "experience_years": experience_years,
            "location": location,
        }
        records.append(record)

    return records


def validate_dataset(records: List[Dict[str, Any]]) -> bool:
    """Validates that the generated dataset satisfies all specification constraints."""
    total = len(records)
    assert total >= 40, f"Expected total >= 40, got {total}"

    # Category coverage
    cat_counts = {c: 0 for c in CATEGORIES}
    for r in records:
        cat_counts[r["category"]] += 1
    for cat, cnt in cat_counts.items():
        assert cnt >= 3, f"Category '{cat}' has {cnt} records (< 3 required)"

    # Status coverage
    status_counts = {s: 0 for s in STATUSES}
    for r in records:
        status_counts[r["status"]] += 1
    for status, cnt in status_counts.items():
        assert cnt >= 1, f"Status '{status}' has {cnt} records (< 1 required)"

    # Priority percentage band [10%, 30%]
    priority_count = sum(1 for r in records if r["flagged_priority_review"])
    priority_pct = (priority_count / total) * 100
    assert 10.0 <= priority_pct <= 30.0, f"Priority % {priority_pct:.1f}% out of [10%, 30%] band"

    # Days since created in [0, 30]
    for r in records:
        assert 0 <= r["days_since_created"] <= 30, f"Invalid age {r['days_since_created']}"

    # Salary validation
    for r in records:
        cat = r["category"]
        min_s, max_s = SALARY_BANDS[cat]
        sal = r["expected_salary_inr"]
        assert min_s <= sal <= max_s, f"Salary {sal} outside [{min_s}, {max_s}] for {cat}"

    return True


def save_dataset(records: List[Dict[str, Any]], output_path: Path) -> None:
    """Saves records to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


if __name__ == "__main__":
    records = generate_job_applications(seed=42, count=45)
    validate_dataset(records)
    
    data_file = Path(__file__).resolve().parent / "data" / "job_applications.json"
    save_dataset(records, data_file)

    print("=" * 60)
    print("Naukri.com Deterministic Dataset Generation Summary")
    print("=" * 60)
    print(f"Total Applications Generated: {len(records)}")
    
    # Category summary
    cat_counts = {c: 0 for c in CATEGORIES}
    for r in records:
        cat_counts[r["category"]] += 1
    print("\nCategory Distribution (Constraint: each >= 3):")
    for cat, cnt in cat_counts.items():
        print(f"  - {cat:20s}: {cnt}")

    # Status summary
    status_counts = {s: 0 for s in STATUSES}
    for r in records:
        status_counts[r["status"]] += 1
    print("\nStatus Distribution (Constraint: each >= 1):")
    for status, cnt in status_counts.items():
        print(f"  - {status:22s}: {cnt}")

    # Priority summary
    priority_cnt = sum(1 for r in records if r["flagged_priority_review"])
    pct = (priority_cnt / len(records)) * 100
    print(f"\nPriority Review Flag: {priority_cnt}/{len(records)} ({pct:.2f}%) [Band: 10% - 30%]")
    print(f"Dataset successfully exported to: {data_file}")
    print("=" * 60)
