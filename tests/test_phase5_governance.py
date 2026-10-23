"""
Comprehensive Verification Test Suite for Phase 5 (Part 4):
Resilience, AI Governance & Optimization.
Track: Naukri.com Recruitment & HR Operations.

Verifies:
- Task 14: Post-Generation AutoGen Review Stage (autogen_review/)
  - Clean draft approved without modification.
  - Hallucinated / ungrounded claim caught and actively revised.
  - StructuredMessage[ReviewVerdict] registration validation.
- Task 15: Four-Layer AI Governance Model (governance/)
  - Layer 1: Principle of Least Autonomy (tool privilege isolation).
  - Layer 1: Risk classification (Medium-to-High).
  - Layer 2: Runtime character ceiling (1,000 characters).
- Task 16: Normalized Query Response Cache (cache/)
  - Query normalization logic.
  - Hit / Miss behavior and call counter metrics.
  - LRU capacity eviction.
  - End-to-end FastAPI serving integration with cache fast-path.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

import config
from app.api import app
from autogen_review.verdict_model import ReviewVerdict, StructuredMessage
from autogen_review.autogen_compat import RoundRobinGroupChat, AssistantAgent
from autogen_review.review_team import build_autogen_review_team, review_support_response
from governance.budget_controller import (
    validate_runtime_budget,
    enforce_runtime_budget,
    RuntimeBudgetExceeded,
)
from governance.least_autonomy_validator import validate_least_autonomy_bindings
from cache.response_cache import (
    NormalizedResponseCache,
    GLOBAL_RESPONSE_CACHE,
    normalize_query,
)
from schemas.response_models import SupportAgentResponse, create_support_agent_response
from tools.application_lookup import check_job_application_status
from tools.policy_rag_tool import rag_policy_tool
from crew.crewai_compat import Agent
from observability.logger import read_logs


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# Task 14: AutoGen Review Stage Tests
# ==============================================================================

def test_autogen_review_clean_draft_approved():
    """Verify Case 1: Standard factual draft is approved without modifications."""
    query = "What is the probation period duration?"
    draft = "The standard probation period is 6 months with a 30-day review milestone."
    context = ["08_probation_period.md: Probation is six months."]

    verdict = review_support_response(draft, context=context, query=query)
    assert isinstance(verdict, ReviewVerdict)
    assert verdict.approved is True
    assert verdict.final_answer == draft
    assert "verified" in verdict.reason.lower() or "compliant" in verdict.reason.lower()


def test_autogen_review_hallucinated_draft_revised():
    """Verify Case 2: Hallucinated / ungrounded claim is caught and revised."""
    query = "Can I buyout my notice period?"
    draft = "You can request a 6 months notice buyout with an unverified 1 crore sign-on bonus payout."
    context = ["05_notice_period.md: Notice buyout requires HR approval for 30 to 90 days."]

    verdict = review_support_response(draft, context=context, query=query)
    assert isinstance(verdict, ReviewVerdict)
    assert verdict.approved is False
    assert "6 months notice buyout" not in verdict.final_answer
    assert "1 crore sign-on bonus" not in verdict.final_answer
    assert "standard 30 to 90 days notice buyout" in verdict.final_answer
    assert "ungrounded" in verdict.reason.lower() or "audit" in verdict.reason.lower()


def test_autogen_structured_message_registration_failure():
    """
    Verify Architectural Invariant:
    If custom_message_types is not registered, RoundRobinGroupChat raises ValueError.
    """
    unregistered_team = build_autogen_review_team(custom_message_types=[])
    with pytest.raises(ValueError) as excinfo:
        unregistered_team.run(
            task="Test registration failure",
            draft_answer="Sample draft",
            context=["Sample context"],
        )
    assert "not registered in custom_message_types" in str(excinfo.value)


# ==============================================================================
# Task 15: AI Governance Model Tests
# ==============================================================================

def test_least_autonomy_enforcement():
    """
    Verify Layer 1: Principle of Least Autonomy.
    Validates that assigning an unauthorized tool raises PermissionError.
    """
    # 1. Compliant assignment passes
    validate_least_autonomy_bindings()

    # 2. Attaching application lookup to Retrieval Agent must raise PermissionError
    with pytest.raises(PermissionError) as exc_1:
        Agent(
            role="Recruitment Policy Researcher",
            goal="Goal",
            backstory="Story",
            tools=[rag_policy_tool, check_job_application_status],
        )
    assert "not permitted for role" in str(exc_1.value)

    # 3. Attaching RAG tool to Application Records Specialist must raise PermissionError
    with pytest.raises(PermissionError) as exc_2:
        Agent(
            role="Application Records Specialist",
            goal="Goal",
            backstory="Story",
            tools=[check_job_application_status, rag_policy_tool],
        )
    assert "not permitted for role" in str(exc_2.value)

    # 4. Attaching any tool to Senior HR Communication Specialist must raise PermissionError
    with pytest.raises(PermissionError) as exc_3:
        Agent(
            role="Senior HR Communication Specialist",
            goal="Goal",
            backstory="Story",
            tools=[rag_policy_tool],
        )
    assert "not permitted for role" in str(exc_3.value)


def test_risk_classification_metadata():
    """Verify Layer 1: System is categorized as Medium-to-High Risk."""
    assert config.RISK_CLASSIFICATION == "Medium-to-High"
    assert config.ESCALATION_THRESHOLD == 0.65


def test_runtime_budget_controller_validation():
    """Verify Layer 2: Runtime character ceiling (1,000 chars max)."""
    # Compliant
    valid_q = "What is the notice period for Software Engineers?"
    ok, err = validate_runtime_budget(valid_q)
    assert ok is True
    assert err is None

    # Oversized
    oversized = "A" * (config.MAX_QUERY_CHARACTER_LIMIT + 10)
    ok_over, err_over = validate_runtime_budget(oversized)
    assert ok_over is False
    assert "exceeds maximum allowed runtime budget" in err_over

    # Exception
    with pytest.raises(RuntimeBudgetExceeded) as excinfo:
        enforce_runtime_budget(oversized)
    assert "1010 characters" in str(excinfo.value)


# ==============================================================================
# Task 16: Normalized Query Response Cache Tests
# ==============================================================================

def test_query_normalization_invariants():
    """Verify query normalization handles whitespace, casing, and trailing punctuation."""
    cases = [
        ("  What is the notice period?  ", "what is the notice period"),
        ("WHAT IS THE NOTICE PERIOD???", "what is the notice period"),
        ("what   is   the   notice   period. ", "what is the notice period"),
        ("What is the notice period!", "what is the notice period"),
    ]
    for raw, expected in cases:
        assert normalize_query(raw) == expected


def test_response_cache_hit_miss_and_stats():
    """Verify response cache hit/miss behavior and stats tracking."""
    cache = NormalizedResponseCache(max_size=10)
    cache.clear()

    query = "What is the probation duration?"
    dummy_resp = create_support_agent_response(
        query=query,
        final_answer="Standard probation is 6 months.",
        intent="policy_query",
        sources=["08_probation_period.md"],
    )

    # Miss
    assert cache.get(query) is None
    assert cache.stats()["misses"] == 1
    assert cache.stats()["hits"] == 0

    # Store
    cache.set(query, dummy_resp)
    assert cache.stats()["current_size"] == 1

    # Hit with different casing/punctuation
    equivalent_query = "   WHAT IS THE PROBATION DURATION???   "
    hit_resp = cache.get(equivalent_query)
    assert hit_resp is not None
    assert hit_resp.cached is True
    assert hit_resp.final_answer == dummy_resp.final_answer
    assert cache.stats()["hits"] == 1
    assert cache.stats()["hit_ratio"] == 0.5


def test_response_cache_lru_eviction():
    """Verify LRU capacity eviction when cache exceeds max_size."""
    cache = NormalizedResponseCache(max_size=3)

    for i in range(1, 4):
        q = f"query {i}"
        resp = create_support_agent_response(query=q, final_answer=f"ans {i}", intent="policy_query")
        cache.set(q, resp)

    assert cache.stats()["current_size"] == 3
    # Access query 1 so query 2 becomes least recently used
    _ = cache.get("query 1")

    # Add query 4 -> query 2 should be evicted
    cache.set("query 4", create_support_agent_response(query="query 4", final_answer="ans 4", intent="policy_query"))
    assert cache.stats()["current_size"] == 3
    assert cache.get("query 2") is None  # Evicted
    assert cache.get("query 1") is not None  # Retained


# ==============================================================================
# End-to-End API Integration Tests (Cache & Governance)
# ==============================================================================

def test_api_cache_fast_path_and_stats(client: TestClient):
    """
    Verify POST /ask leverages normalized cache:
    1. First call: Cache miss, executed via multi-agent and AutoGen review.
    2. Second equivalent call: Cache hit, served fast with cached=True.
    3. Verify GET /cache/stats shows incremented hit counter.
    """
    GLOBAL_RESPONSE_CACHE.clear()

    q1 = f"Explain the referral bonus milestones {uuid.uuid4().hex[:4]}?"
    q2 = f"   {q1.lower()}   "

    # Turn 1: Cold request
    resp1 = client.post("/ask", json={"query": q1})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["cached"] is False

    # Turn 2: Equivalent request
    resp2 = client.post("/ask", json={"query": q2})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["cached"] is True
    assert data2["final_answer"] == data1["final_answer"]

    # Verify /cache/stats
    stats_resp = client.get("/cache/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1

    # Verify /cache/clear
    clear_resp = client.post("/cache/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "success"
    assert client.get("/cache/stats").json()["current_size"] == 0
