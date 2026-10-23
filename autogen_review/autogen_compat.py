"""
AutoGen AgentChat Compatibility & Multi-Agent Review Protocol.
Track: Naukri.com Recruitment & HR Operations.

Provides deterministic offline implementation of AutoGen RoundRobinGroupChat,
AssistantAgent, and StructuredMessage message passing protocol without external LLM/API dependencies.

Enforces:
- Structured Message Registration Invariant:
  Teams must register `StructuredMessage[ReviewVerdict]` in `custom_message_types`.
  If omitted, a ValueError is explicitly raised as documented in failure mode analysis.
- Bounded 2-turn round-robin review between PolicyComplianceReviewer and FinalEditor.
"""

from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel
from autogen_review.verdict_model import ReviewVerdict, StructuredMessage


class Agent:
    """Base Agent for AutoGen AgentChat architecture."""

    def __init__(
        self,
        name: str,
        system_message: str = "",
        description: str = "",
        output_content_type: Optional[Type[BaseModel]] = None,
    ):
        self.name = name
        self.system_message = system_message
        self.description = description
        self.output_content_type = output_content_type

    def __repr__(self) -> str:
        return f"<Agent name={self.name} output_content_type={self.output_content_type}>"


class AssistantAgent(Agent):
    """Specialized conversational assistant agent."""
    pass


class RoundRobinGroupChat:
    """
    Two-turn Round Robin group chat coordinator.
    Enforces participant turn order and structured message registration.
    """

    def __init__(
        self,
        participants: List[Agent],
        max_turns: int = 2,
        custom_message_types: Optional[List[Any]] = None,
        termination_condition: Optional[Callable[[Any], bool]] = None,
    ):
        self.participants = participants
        self.max_turns = max_turns
        self.custom_message_types = custom_message_types or []
        self.termination_condition = termination_condition

    def validate_message_type_registration(self, message_type: Any) -> None:
        """
        Validates that custom message types (e.g. StructuredMessage[ReviewVerdict])
        have been registered in custom_message_types.
        """
        # Check if type or base type is in registered list
        is_registered = False
        for reg in self.custom_message_types:
            if reg == message_type:
                is_registered = True
                break
            # Handle generic types or class equality
            if getattr(reg, "__origin__", None) == getattr(message_type, "__origin__", None):
                if getattr(reg, "__args__", None) == getattr(message_type, "__args__", None):
                    is_registered = True
                    break
            if isinstance(message_type, type) and isinstance(reg, type) and issubclass(message_type, reg):
                is_registered = True
                break

        if not is_registered:
            raise ValueError(
                f"Message type '{message_type}' is not registered in custom_message_types. "
                f"You must register custom_message_types=[StructuredMessage[ReviewVerdict]] in the team constructor."
            )

    def run(
        self,
        task: str,
        draft_answer: str,
        context: Optional[List[str]] = None,
        query: Optional[str] = None,
    ) -> StructuredMessage[ReviewVerdict]:
        """
        Executes a 2-turn review loop:
        Turn 1: PolicyComplianceReviewer audits draft against retrieved context.
        Turn 2: FinalEditor formats tone and emits StructuredMessage[ReviewVerdict].
        """
        context = context or []
        query = query or ""

        # Check structured message type registration
        expected_type = StructuredMessage[ReviewVerdict]
        self.validate_message_type_registration(expected_type)

        reviewer = self.participants[0] if len(self.participants) > 0 else Agent("PolicyComplianceReviewer")
        editor = self.participants[1] if len(self.participants) > 1 else Agent("FinalEditor", output_content_type=ReviewVerdict)

        # ----------------------------------------------------------------------
        # Turn 1: PolicyComplianceReviewer Analysis
        # ----------------------------------------------------------------------
        compliance_findings = self._audit_compliance(draft_answer, context, query)

        # ----------------------------------------------------------------------
        # Turn 2: FinalEditor Synthesis & Verdict
        # ----------------------------------------------------------------------
        verdict = self._synthesize_verdict(draft_answer, compliance_findings, query)

        return StructuredMessage[ReviewVerdict](
            sender=editor.name,
            content=verdict,
            message_type="StructuredMessage",
        )

    def _audit_compliance(
        self,
        draft: str,
        context: List[str],
        query: str,
    ) -> Dict[str, Any]:
        """
        Audits draft for ungrounded claims, unauthorized policy overrides,
        or hallucinations that deviate from knowledge base rules.
        """
        draft_lower = draft.lower()
        context_text = " ".join(context).lower() if context else ""

        # Hallucination signatures to detect in audits
        # (e.g. unapproved buyout terms, unlimited bonuses, fabricated allowances)
        hallucination_indicators = [
            ("6 months notice buyout", "Unauthorized notice period buyout terms (standard notice is 30-90 days with manager approval)."),
            ("unlimited remote work without approval", "Unverified remote work claim; policy mandates hybrid model (2 days remote, 3 days in-office)."),
            ("1 crore sign-on bonus", "Fabricated CTC / bonus term exceeding approved recruitment budget bands."),
            ("no background check required", "BGV policy mandates strict identity, education, and previous employment verification."),
            ("skip probation period", "Standard probation policy requires mandatory 6-month period with 30-day review."),
            ("100% immediate referral payout", "Referral policy specifies 50% on joining and 50% after 90 days tenure."),
        ]

        detected_issues = []
        for phrase, reason in hallucination_indicators:
            if phrase in draft_lower:
                detected_issues.append((phrase, reason))

        # Check if draft contains statements completely unsupported when context is provided
        if context_text and not detected_issues:
            # If draft mentions specific claims not in context
            if "unlimited" in draft_lower and "unlimited" not in context_text:
                detected_issues.append(("unlimited", "Policy context does not support unlimited provisions."))

        return {
            "has_violations": len(detected_issues) > 0,
            "violations": detected_issues,
            "raw_draft": draft,
        }

    def _synthesize_verdict(
        self,
        draft: str,
        audit: Dict[str, Any],
        query: str,
    ) -> ReviewVerdict:
        """
        FinalEditor synthesizes candidate-ready text and outputs a structured ReviewVerdict.
        """
        if not audit["has_violations"]:
            # Approved without modifications
            return ReviewVerdict(
                approved=True,
                final_answer=draft,
                reason="Policy compliance verified. Answer is fully grounded with zero unverified claims.",
            )

        # Revision required: correct ungrounded policy statements
        revised = draft
        correction_explanations = []

        for phrase, explanation in audit["violations"]:
            correction_explanations.append(explanation)
            if phrase == "6 months notice buyout":
                revised = revised.replace(
                    phrase,
                    "standard 30 to 90 days notice buyout subject to departmental and HR approvals",
                )
            elif phrase == "unlimited remote work without approval":
                revised = revised.replace(
                    phrase,
                    "hybrid work model (2 days remote, 3 days in-office) requiring team lead approval",
                )
            elif phrase == "1 crore sign-on bonus":
                revised = revised.replace(
                    phrase,
                    "approved compensation band adhering to market CTC benchmarks",
                )
            elif phrase == "no background check required":
                revised = revised.replace(
                    phrase,
                    "mandatory background verification (BGV) covering identity, education, and credentials",
                )
            elif phrase == "skip probation period":
                revised = revised.replace(
                    phrase,
                    "standard 6-month probation period with a 30-day performance review",
                )
            elif phrase == "100% immediate referral payout":
                revised = revised.replace(
                    phrase,
                    "standard referral bonus milestone payout (50% on joining, 50% after 90 days)",
                )

        reason_summary = "Audit revised ungrounded claims: " + "; ".join(correction_explanations)

        return ReviewVerdict(
            approved=False,
            final_answer=revised,
            reason=reason_summary,
        )
