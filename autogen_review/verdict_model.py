"""
Pydantic Verdict Models for AutoGen Review Stage (Task 14).
Track: Naukri.com Recruitment & HR Operations.
"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ReviewVerdict(BaseModel):
    """
    Structured message payload emitted by AutoGen FinalEditor agent.
    
    Attributes:
        approved: Whether the initial draft is fully grounded and policy-compliant.
        final_answer: The verified or revised candidate-ready response.
        reason: Rationale detailing policy compliance or specific edits made.
    """
    approved: bool = Field(
        ...,
        description="True if draft was approved unchanged; False if revised due to ungrounded claims.",
    )
    final_answer: str = Field(
        ...,
        description="Final customer-ready answer after editorial and compliance review.",
    )
    reason: str = Field(
        ...,
        description="Compliance audit reason or description of modifications.",
    )


class StructuredMessage(BaseModel, Generic[T]):
    """
    Generic structured message envelope for AutoGen AgentChat protocol.
    Requires explicit registration in RoundRobinGroupChat(custom_message_types=[...]).
    """
    sender: str
    content: T
    message_type: str = "StructuredMessage"
