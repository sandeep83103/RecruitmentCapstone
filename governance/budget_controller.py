"""
Runtime Budget Controller for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 15 Layer 2 Governance:
- Enforces runtime character/token budget ceiling (max 1,000 characters).
- Rejects oversized requests immediately to protect system resources and prevent DoS.
- Verification Command (Line 336): python governance/budget_controller.py
  Expected Outcome: Oversized prompt rejected under runtime cap.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config


class RuntimeBudgetExceeded(Exception):
    """Exception raised when an incoming request exceeds the allocated runtime budget."""
    def __init__(self, query_length: int, max_limit: int):
        self.query_length = query_length
        self.max_limit = max_limit
        super().__init__(
            f"Query length ({query_length} characters) exceeds maximum allowed "
            f"runtime budget of {max_limit} characters."
        )


def validate_runtime_budget(
    query: str,
    max_chars: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validates whether the user inquiry complies with the runtime character ceiling.
    
    Returns:
        (is_valid: bool, error_message: Optional[str])
    """
    limit = max_chars if max_chars is not None else config.MAX_QUERY_CHARACTER_LIMIT
    length = len(query.strip())

    if length > limit:
        msg = (
            f"Query length ({length} characters) exceeds maximum allowed "
            f"runtime budget of {limit} characters."
        )
        return False, msg

    return True, None


def enforce_runtime_budget(query: str, max_chars: Optional[int] = None) -> None:
    """
    Enforces runtime budget, raising RuntimeBudgetExceeded if limit is exceeded.
    """
    limit = max_chars if max_chars is not None else config.MAX_QUERY_CHARACTER_LIMIT
    length = len(query.strip())
    if length > limit:
        raise RuntimeBudgetExceeded(query_length=length, max_limit=limit)


def demonstrate_budget_controller() -> None:
    """
    Demonstrates Task 15 verification requirements:
    1. Compliant query under 1000 characters passes budget check.
    2. Oversized query (>1000 characters) is rejected with clear error message.
    """
    print("=" * 75)
    print("Task 15: AI Governance Runtime Budget Controller Demonstration")
    print("Track: Naukri.com Recruitment & HR Operations")
    print("=" * 75)

    limit = config.MAX_QUERY_CHARACTER_LIMIT
    print(f"Configured Runtime Character Ceiling: {limit} characters\n")

    # Scenario 1: Compliant Query
    compliant_query = "What is the probation period duration and the 30-day review schedule?"
    is_valid, err = validate_runtime_budget(compliant_query)
    print(f"Scenario 1: Compliant Request ({len(compliant_query)} chars)")
    print(f"  Input  : \"{compliant_query}\"")
    print(f"  Result : {'PASSED' if is_valid else 'FAILED'} (Error: {err})")
    assert is_valid is True, "Compliant query should pass runtime budget check."

    # Scenario 2: Oversized Query
    oversized_payload = "Please check application status. " + ("X" * (limit + 50))
    is_valid_over, err_over = validate_runtime_budget(oversized_payload)
    print(f"\nScenario 2: Oversized Request ({len(oversized_payload)} chars)")
    print(f"  Result : {'PASSED' if is_valid_over else 'REJECTED'}")
    print(f"  Notice : {err_over}")
    assert is_valid_over is False, "Oversized query must be rejected."
    assert f"exceeds maximum allowed runtime budget of {limit}" in err_over

    # Scenario 3: Exception Enforcement Verification
    print("\nScenario 3: Exception Throw Verification")
    try:
        enforce_runtime_budget(oversized_payload)
        print("ERROR: RuntimeBudgetExceeded exception was not raised!")
    except RuntimeBudgetExceeded as exc:
        print(f"  SUCCESS: Caught expected exception -> {exc}")

    print("\n" + "=" * 75)
    print("Verification Result: Oversized prompt rejected under runtime cap.")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_budget_controller()
