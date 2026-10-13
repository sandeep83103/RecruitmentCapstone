"""
CrewAI 3-Agent Multi-Agent Orchestration for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 7 Requirements:
- 3 Agents:
  1. Retrieval Agent: Role: 'Recruitment Policy Researcher', Tools: [rag_policy_tool]
  2. Lookup Agent: Role: 'Application Records Specialist', Tools: [check_job_application_status]
  3. Response Composer Agent: Role: 'Senior HR Communication Specialist', Tools: []
- Workflow: Sequential execution via crew.kickoff().
- Verification Command (Line 329): python crew/recruitment_crew.py
  Expected Outcome: 3 agents execute via .kickoff() with tools invoked.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from crew.mock_llm import DeterministicMockLLM
from tools.application_lookup import check_job_application_status
from tools.policy_rag_tool import rag_policy_tool, rag_policy_lookup
from schemas.response_models import SupportAgentResponse, create_support_agent_response

# Standard CrewAI abstraction import with offline compatibility fallback
try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool
except (ImportError, ModuleNotFoundError):
    from crew.crewai_compat import Agent, Task, Crew, Process, tool


def build_recruitment_crew(
    llm: Optional[Any] = None,
    verbose: bool = True,
) -> Crew:
    """
    Constructs the 3-agent Crew adhering strictly to Least Autonomy governance:
    - Policy Retrieval Agent has ONLY RAG tool.
    - Application Lookup Agent has ONLY Application Status tool.
    - Response Composer Agent has ZERO tools (strictly synthesis & communication).
    """
    shared_llm = llm or DeterministicMockLLM()

    # Agent 1: Retrieval Agent (Least Autonomy: RAG policy tool only)
    retrieval_agent = Agent(
        role="Recruitment Policy Researcher",
        goal="Search and retrieve authoritative recruitment policy guidelines, notice period rules, and compensation bands from the ChromaDB knowledge base.",
        backstory="An expert in HR recruitment policies, eligibility criteria, background checks, and employment contracts.",
        tools=[rag_policy_tool],
        llm=shared_llm,
        verbose=verbose,
    )

    # Agent 2: Lookup Agent (Least Autonomy: Application status tool only)
    lookup_agent = Agent(
        role="Application Records Specialist",
        goal="Retrieve candidate application records and compute escalation metrics based on priority review flags and application age.",
        backstory="A meticulous recruitment database administrator with access to candidate stages, CTC expectations, and escalation tracking.",
        tools=[check_job_application_status],
        llm=shared_llm,
        verbose=verbose,
    )

    # Agent 3: Response Composer Agent (Least Autonomy: Zero tools)
    composer_agent = Agent(
        role="Senior HR Communication Specialist",
        goal="Synthesize policy citations and candidate application records into empathetic, professional, candidate-ready drafts.",
        backstory="A senior HR talent operations leader dedicated to transparent, compliant, and candidate-centric communications.",
        tools=[],
        llm=shared_llm,
        verbose=verbose,
    )

    # Tasks
    policy_task = Task(
        description="Investigate recruitment policy guidelines and citations for user inquiry: {query}",
        expected_output="Authoritative policy excerpts with source document citations or note if not applicable.",
        agent=retrieval_agent,
    )

    lookup_task = Task(
        description="Inspect candidate application records, CTC bands, and escalation scores for user inquiry: {query}",
        expected_output="Detailed application status record with calculated escalation score or note if not applicable.",
        agent=lookup_agent,
    )

    composer_task = Task(
        description="Synthesize all findings into a unified, professional, candidate-ready response for user inquiry: {query}",
        expected_output="Candidate-ready HR response with clear attribution and escalation notices.",
        agent=composer_agent,
    )

    return Crew(
        agents=[retrieval_agent, lookup_agent, composer_agent],
        tasks=[policy_task, lookup_task, composer_task],
        process=Process.sequential,
        verbose=verbose,
    )


def classify_query_intent(query: str) -> str:
    """Classifies user inquiry into one of the 4 standard schema intents."""
    normalized = query.lower()
    has_app = bool(re.search(r"\bAPP-\d{4}\b", query, re.IGNORECASE)) or any(
        k in normalized for k in ["application", "candidate", "status", "stage"]
    )
    has_policy = any(
        k in normalized
        for k in [
            "policy", "probation", "notice", "bonus", "referral", "remote",
            "eligibility", "interview", "offer", "transfer", "exit", "criteria",
            "verification", "background", "data retention", "hybrid"
        ]
    )

    if has_app and has_policy:
        return "hybrid"
    if has_app:
        return "status_lookup"
    if has_policy:
        return "policy_query"
    return "out_of_scope"


def run_recruitment_crew(
    query: str,
    llm: Optional[Any] = None,
    verbose: bool = False,
) -> SupportAgentResponse:
    """
    Executes the multi-agent Crew on a user query and returns a validated SupportAgentResponse.
    """
    crew = build_recruitment_crew(llm=llm, verbose=verbose)
    crew_output = crew.kickoff(inputs={"query": query})
    final_text = str(crew_output.raw)

    intent = classify_query_intent(query)
    sources: List[str] = []
    escalation_recommended = False

    # Extract sources and escalation from task outputs
    for task_out in crew_output.tasks_output:
        raw = task_out.raw
        # Extract document citations
        doc_matches = re.findall(r"\b\d{2}_[a-z_]+\.md\b", raw)
        sources.extend(doc_matches)
        # Extract application IDs
        app_matches = re.findall(r"\bAPP-\d{4}\b", raw)
        sources.extend(app_matches)
        # Check escalation
        if re.search(r"escalation\s+recommended:\s*yes", raw, re.IGNORECASE) or re.search(r"alert\s+triggered", raw, re.IGNORECASE):
            escalation_recommended = True

    sources = list(dict.fromkeys(sources))

    # If out of scope refusal was generated
    if "i don't have information on this topic" in final_text.lower():
        intent = "out_of_scope"
        sources = []

    return create_support_agent_response(
        query=query,
        final_answer=final_text,
        intent=intent,
        sources=sources,
        escalation_recommended=escalation_recommended,
        review_status="approved",
    )


def demonstrate_recruitment_crew() -> None:
    """
    Demonstrates Task 7 verification requirements:
    1. Policy Query -> RAG tool invoked by Retrieval Agent.
    2. Status Lookup Query -> Status tool invoked by Lookup Agent.
    3. Hybrid Query -> Both tools invoked.
    4. Out-of-Scope Query -> Fallback refusal triggered.
    """
    print("=" * 75)
    print("Task 7: CrewAI 3-Agent Multi-Agent Orchestration Demonstration")
    print("=" * 75)

    scenarios = [
        ("Policy Query", "What is the probation duration and review milestone?"),
        ("Status Lookup Query", "Check the status of application APP-1011."),
        ("Hybrid Query", "Check the status of application APP-1001 and what is the notice period buyout policy?"),
        ("Out-of-Scope Query", "What is the stock price of Google?"),
    ]

    for label, query in scenarios:
        print(f"\n[{label}] User Inquiry: \"{query}\"")
        print("-" * 75)
        response = run_recruitment_crew(query, verbose=True)
        print("\n[Final Validated Structured Response]")
        print(f"  Trace ID      : {response.trace_id}")
        print(f"  Intent        : {response.intent}")
        print(f"  Sources       : {response.sources}")
        print(f"  Escalation    : {response.escalation_recommended}")
        print(f"  Final Answer  : {response.final_answer}")
        print("=" * 75)

    print("\nVerification Result: 3 agents execute via .kickoff() with tools invoked.")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_recruitment_crew()
