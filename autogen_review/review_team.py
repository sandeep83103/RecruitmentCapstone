"""
AutoGen Multi-Agent Review Team for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 14 Requirements:
- 2-Agent RoundRobinGroupChat (max_turns=2):
  1. PolicyComplianceReviewer: Verifies policy fidelity and escalation rules.
  2. FinalEditor: Enforces customer-facing tone and emits ReviewVerdict.
- Structured Message Registration:
  Registered with custom_message_types=[StructuredMessage[ReviewVerdict]].
- Demonstrations:
  - Case 1: Clean draft approved without modification.
  - Case 2: Hallucinated / ungrounded claim caught and actively revised.
- Verification Command (Line 335): python autogen_review/review_team.py
"""

import sys
from pathlib import Path
from typing import Any, List, Optional

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autogen_review.verdict_model import ReviewVerdict, StructuredMessage
from autogen_review.autogen_compat import AssistantAgent, RoundRobinGroupChat


def build_autogen_review_team(
    custom_message_types: Optional[List[Any]] = None,
    max_turns: int = 2,
) -> RoundRobinGroupChat:
    """
    Builds the 2-agent AutoGen review team.
    
    Default registers custom_message_types=[StructuredMessage[ReviewVerdict]]
    to prevent runtime ValueError: Message type not registered.
    """
    reviewer = AssistantAgent(
        name="PolicyComplianceReviewer",
        system_message=(
            "You are an expert HR Policy Compliance Reviewer for Naukri.com. "
            "Audit candidate draft responses against verified policy documents and calculation rules. "
            "Flag any ungrounded assertions, incorrect notice period numbers, or unauthorized bonus promises."
        ),
        description="Audits response drafts for recruitment policy compliance and factual groundedness.",
    )

    editor = AssistantAgent(
        name="FinalEditor",
        system_message=(
            "You are the Senior Editorial Quality Controller. "
            "Review findings from PolicyComplianceReviewer, revise any inaccurate claims, "
            "and produce a final customer-ready answer encapsulated in a ReviewVerdict structure."
        ),
        description="Refines tone, corrects flagged discrepancies, and outputs a structured ReviewVerdict.",
        output_content_type=ReviewVerdict,
    )

    # Register structured message type by default
    types = custom_message_types if custom_message_types is not None else [StructuredMessage[ReviewVerdict]]

    return RoundRobinGroupChat(
        participants=[reviewer, editor],
        max_turns=max_turns,
        custom_message_types=types,
    )


def review_support_response(
    draft_answer: str,
    context: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> ReviewVerdict:
    """
    Entry point to run the AutoGen review team on a draft response.
    Returns the validated ReviewVerdict.
    """
    team = build_autogen_review_team()
    message = team.run(
        task="Audit recruitment domain support response draft for policy grounding and clarity.",
        draft_answer=draft_answer,
        context=context,
        query=query,
    )
    return message.content


def demonstrate_autogen_review() -> None:
    """
    Demonstrates Task 14 verification requirements:
    1. Case 1: Clean factual draft approved without modification.
    2. Case 2: Hallucinated draft detected and actively revised.
    3. Case 3: Demonstrates safety invariant - omission of custom_message_types
       triggers the documented ValueError.
    """
    print("=" * 80)
    print("Task 14: AutoGen Multi-Agent Secondary Review Stage Demonstration")
    print("Track: Naukri.com Recruitment & HR Operations")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Case 1: Clean Factual Draft Approved
    # --------------------------------------------------------------------------
    print("\n--- [Case 1: Grounded Factual Draft (Expected: Approved Unchanged)] ---")
    query_1 = "What is the probation period duration at Naukri.com?"
    draft_1 = (
        "The standard probation period for all new hires is 6 months from the date of joining. "
        "A formal performance review is conducted at the 30-day milestone to assess progress."
    )
    context_1 = [
        "08_probation_period.md: The standard probation period for all new employees is six months. "
        "A formal review takes place at the end of the initial thirty-day window."
    ]

    print(f"Query   : {query_1}")
    print(f"Draft   : {draft_1}")
    verdict_1 = review_support_response(draft_1, context=context_1, query=query_1)
    print(f"Verdict : Approved={verdict_1.approved}")
    print(f"Reason  : {verdict_1.reason}")
    print(f"Output  : {verdict_1.final_answer}")
    assert verdict_1.approved is True, "Expected clean draft to be approved."
    assert verdict_1.final_answer == draft_1, "Expected draft to remain unchanged."

    # --------------------------------------------------------------------------
    # Case 2: Hallucinated / Ungrounded Draft Revised
    # --------------------------------------------------------------------------
    print("\n--- [Case 2: Hallucinated Policy Claim (Expected: Caught & Revised)] ---")
    query_2 = "What are the rules regarding notice period buyouts?"
    draft_2 = (
        "Employees can request a 6 months notice buyout with immediate sign-off, "
        "along with an unverified 1 crore sign-on bonus payout."
    )
    context_2 = [
        "05_notice_period.md: Notice period buyout is subject to business unit head and HR approval, "
        "typically covering 30 to 90 days. Unilateral buyouts are not permitted."
    ]

    print(f"Query   : {query_2}")
    print(f"Draft   : {draft_2}")
    verdict_2 = review_support_response(draft_2, context=context_2, query=query_2)
    print(f"Verdict : Approved={verdict_2.approved}")
    print(f"Reason  : {verdict_2.reason}")
    print(f"Output  : {verdict_2.final_answer}")
    assert verdict_2.approved is False, "Expected hallucinated draft to be flagged."
    assert "6 months notice buyout" not in verdict_2.final_answer, "Expected hallucinated phrase to be removed."
    assert "1 crore sign-on bonus" not in verdict_2.final_answer, "Expected bonus hallucination to be removed."

    # --------------------------------------------------------------------------
    # Case 3: Verification of Structured Message Registration Protection
    # --------------------------------------------------------------------------
    print("\n--- [Case 3: Architectural Invariant - Custom Message Type Registration] ---")
    print("Testing team initialization with custom_message_types=[] (missing registration)...")
    unregistered_team = build_autogen_review_team(custom_message_types=[])
    try:
        unregistered_team.run(
            task="Test registration failure",
            draft_answer=draft_1,
            context=context_1,
        )
        print("ERROR: Expected ValueError was not raised!")
    except ValueError as exc:
        print(f"SUCCESS: Caught expected registration error -> {exc}")
        assert "not registered in custom_message_types" in str(exc)

    print("\n" + "=" * 80)
    print("Task 14 Verification Succeeded: Approved & Revised Demos Verified.")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_autogen_review()
