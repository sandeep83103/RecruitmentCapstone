"""
Unit Tests for Phase 1: Environment, Configuration, and DeterministicMockLLM.
Verifies telemetry suppression, schema dispatching, and ReAct observation template safety.
"""

import os
import pytest
import config
from crew.mock_llm import DeterministicMockLLM, CrewAIBaseLLM


def test_telemetry_suppression():
    """Verify outbound telemetry is strictly disabled upon config import."""
    assert os.environ.get("CREWAI_DISABLE_TELEMETRY") == "true"
    assert os.environ.get("OTEL_SDK_DISABLED") == "true"
    assert config.MOCK_LLM_ENABLED is True
    assert config.RANDOM_SEED == 42


def test_base_llm_inheritance():
    """Verify DeterministicMockLLM correctly extends BaseLLM."""
    llm = DeterministicMockLLM(model_name="test-mock-llm")
    assert isinstance(llm, CrewAIBaseLLM)
    assert llm.model_name == "test-mock-llm"


def test_react_observation_template_safety():
    """
    Pitfall 1 Test:
    CrewAI system prompt template literally contains:
    'Observation: the result of the action'
    Verify that our parser does NOT false-positive match this template text on turn 1.
    """
    llm = DeterministicMockLLM()

    # Simulated CrewAI ReAct prompt containing the literal template text
    system_prompt_with_template = (
        "You are an AI assistant.\n"
        "Use the following format:\n"
        "Question: the input question you must answer\n"
        "Thought: you should always think about what to do\n"
        "Action: the action to take\n"
        "Action Input: the input to the action\n"
        "Observation: the result of the action\n"
        "... (this Thought/Action/Action Input/Observation can repeat N times)\n"
        "Thought: I now know the final answer\n"
        "Final Answer: the final answer to the original input question\n\n"
        "Human: What is the probation period policy?"
    )

    response = llm.call(system_prompt_with_template)

    # Must NOT return a Final Answer on turn 1
    assert "Final Answer:" not in response
    # Must propose a ReAct Action instead
    assert "Action:" in response
    assert "Action Input:" in response


def test_schema_based_tool_dispatch():
    """
    Pitfall 2 Test:
    Verify tool dispatching is driven by argument schema, not by substring matching on tool name.
    """
    llm = DeterministicMockLLM()

    # Register two tools, including 'rag_lookup' which contains 'lookup' in its name
    def dummy_rag(query: str):
        return "policy excerpt"

    def dummy_app_lookup(record_id: str):
        return {"status": "Offered"}

    llm.register_tool(
        name="rag_lookup",
        func=dummy_rag,
        param_schema={"query": str},
        description="Search policies",
    )
    llm.register_tool(
        name="check_job_application_status",
        func=dummy_app_lookup,
        param_schema={"record_id": str},
        description="Lookup status",
    )

    # Dispatch by argument schema
    dispatched_app = llm.dispatch_tool_by_schema({"record_id": "APP-1001"})
    assert dispatched_app == "check_job_application_status"

    dispatched_rag = llm.dispatch_tool_by_schema({"query": "notice period"})
    assert dispatched_rag == "rag_lookup"


def test_react_step_two_with_real_observation():
    """Verify that when a genuine tool observation exists, the final answer is generated."""
    llm = DeterministicMockLLM()

    prompt_with_real_observation = (
        "Human: Check status for APP-1002\n"
        "Thought: I need to check the status.\n"
        "Action: check_job_application_status\n"
        'Action Input: {"record_id": "APP-1002"}\n'
        'Observation: {"record_id": "APP-1002", "status": "Offered", "expected_salary_inr": 1800000, "escalation_score": 0.35, "escalation_recommended": false}\n'
    )

    response = llm.call(prompt_with_real_observation)
    assert "Final Answer:" in response
    assert "APP-1002" in response
    assert "Offered" in response
    assert "1,800,000" in response
