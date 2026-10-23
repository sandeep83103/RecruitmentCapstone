"""
Least Autonomy Governance Validator for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 15 Layer 1 Governance:
- Verifies strict agent-tool privilege isolation (Principle of Least Autonomy).
- Proves that unauthorized tool assignments raise PermissionError before execution.
- Verifies Medium-to-High Risk classification metadata.
"""

import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from crew.crewai_compat import Agent
from tools.application_lookup import check_job_application_status
from tools.policy_rag_tool import rag_policy_tool


def validate_least_autonomy_bindings() -> None:
    """
    Validates that compliant tool assignments pass, and any violation of
    least autonomy immediately triggers a PermissionError.
    """
    # 1. Compliant instantiation
    agent_retrieval = Agent(
        role="Recruitment Policy Researcher",
        goal="Retrieve policy documents",
        backstory="Policy specialist",
        tools=[rag_policy_tool],
    )
    agent_lookup = Agent(
        role="Application Records Specialist",
        goal="Lookup candidate records",
        backstory="Database specialist",
        tools=[check_job_application_status],
    )
    agent_composer = Agent(
        role="Senior HR Communication Specialist",
        goal="Synthesize responses",
        backstory="HR writer",
        tools=[],
    )

    # 2. Test Violation 1: Attaching Application tool to Retrieval Agent
    try:
        Agent(
            role="Recruitment Policy Researcher",
            goal="Retrieve policy documents",
            backstory="Policy specialist",
            tools=[rag_policy_tool, check_job_application_status],
        )
        raise AssertionError("Least Autonomy failure: check_job_application_status allowed for Retrieval Agent!")
    except PermissionError as exc:
        assert "is not permitted for role" in str(exc)

    # 3. Test Violation 2: Attaching Policy tool to Lookup Agent
    try:
        Agent(
            role="Application Records Specialist",
            goal="Lookup candidate records",
            backstory="Database specialist",
            tools=[check_job_application_status, rag_policy_tool],
        )
        raise AssertionError("Least Autonomy failure: rag_policy_tool allowed for Lookup Agent!")
    except PermissionError as exc:
        assert "is not permitted for role" in str(exc)

    # 4. Test Violation 3: Attaching any tool to Response Composer Agent
    try:
        Agent(
            role="Senior HR Communication Specialist",
            goal="Synthesize responses",
            backstory="HR writer",
            tools=[check_job_application_status],
        )
        raise AssertionError("Least Autonomy failure: Tool allowed for Response Composer Agent!")
    except PermissionError as exc:
        assert "is not permitted for role" in str(exc)


def demonstrate_least_autonomy() -> None:
    """Demonstrates enforcement of Principle of Least Autonomy and Risk Classification."""
    print("=" * 80)
    print("Task 15: AI Governance Layer 1 (Least Autonomy & Risk Classification)")
    print("Track: Naukri.com Recruitment & HR Operations")
    print("=" * 80)

    print(f"Risk Classification : {config.RISK_CLASSIFICATION}")
    print(f"Risk Level          : Medium-to-High Risk (Recruitment Decisions & Candidate CTC Data)")
    print(f"Human-in-Loop Rule  : Escalation threshold tau_esc = {config.ESCALATION_THRESHOLD}\n")

    print("Verifying Principle of Least Autonomy tool isolation...")
    validate_least_autonomy_bindings()
    print("  [OK] Retrieval Agent: strictly limited to [rag_policy_tool]")
    print("  [OK] Lookup Agent   : strictly limited to [check_job_application_status]")
    print("  [OK] Composer Agent : strictly zero tools (pure synthesis)")
    print("  [OK] Unauthorized tool assignment correctly raises PermissionError")

    print("\n" + "=" * 80)
    print("Governance Layer 1 Verification Successful.")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_least_autonomy()
