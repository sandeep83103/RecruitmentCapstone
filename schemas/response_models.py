"""
Pydantic Response Schemas for Naukri.com Domain Support Agent.
Enforces strict contract validation on all agent outputs (Task 9).
"""

import uuid
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class SupportAgentResponse(BaseModel):
    """
    Standard structured response contract emitted by the multi-agent system.
    Guarantees trace attribution, intent categorization, grounded answers,
    and escalation recommendations.
    """
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique UUIDv4 trace identifier for observability.",
    )
    query: str = Field(
        ...,
        description="Original or PII-masked candidate/recruiter query.",
    )
    intent: Literal["policy_query", "status_lookup", "hybrid", "out_of_scope"] = Field(
        ...,
        description="Classified domain intent.",
    )
    final_answer: str = Field(
        ...,
        description="Candidate-ready, grounded synthesized response.",
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Referenced policy documents (e.g., '08_probation_period.md') or application record IDs.",
    )
    escalation_recommended: bool = Field(
        default=False,
        description="Flag indicating if application requires senior recruiter/manager escalation.",
    )
    review_status: str = Field(
        default="approved",
        description="Quality and compliance audit status (e.g., 'approved', 'revised', 'refused').",
    )
    cached: bool = Field(
        default=False,
        description="Flag indicating if response was served from normalized in-memory cache.",
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Total response latency in milliseconds.",
    )
    audit_reason: Optional[str] = Field(
        default=None,
        description="Compliance audit reason from AutoGen secondary review stage.",
    )

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        if not v or not v.strip():
            return str(uuid.uuid4())
        return v.strip()


class AskRequest(BaseModel):
    """Input payload for /ask inference endpoint."""
    query: str = Field(..., min_length=1, description="User query text.")
    session_id: Optional[str] = Field(None, description="Optional multi-turn conversation session ID.")


class DocumentUpload(BaseModel):
    """Input payload for /add-document administrative endpoint."""
    title: str = Field(..., description="Document identifier/title (e.g., '13_relocation_allowance.md').")
    content: str = Field(..., min_length=10, description="Policy document text content.")


def create_support_agent_response(
    query: str,
    final_answer: str,
    intent: Literal["policy_query", "status_lookup", "hybrid", "out_of_scope"],
    sources: Optional[List[str]] = None,
    escalation_recommended: bool = False,
    review_status: str = "approved",
    trace_id: Optional[str] = None,
    cached: bool = False,
    latency_ms: Optional[float] = None,
    audit_reason: Optional[str] = None,
) -> SupportAgentResponse:
    """Helper factory for instantiating and validating SupportAgentResponse instances."""
    return SupportAgentResponse(
        trace_id=trace_id or str(uuid.uuid4()),
        query=query,
        intent=intent,
        final_answer=final_answer,
        sources=sources or [],
        escalation_recommended=escalation_recommended,
        review_status=review_status,
        cached=cached,
        latency_ms=latency_ms,
        audit_reason=audit_reason,
    )
