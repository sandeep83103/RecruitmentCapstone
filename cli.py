"""
Interactive Command-Line Interface (CLI) for Naukri.com Recruitment Support Agent.
Enables real-time terminal user input and multi-turn conversational interactions.
"""

import argparse
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from guardrails.pii_masker import mask_pii
from guardrails.injection_detector import detect_prompt_injection, INJECTION_REFUSAL_MESSAGE
from governance.budget_controller import validate_runtime_budget
from cache.response_cache import GLOBAL_RESPONSE_CACHE
from memory.session_memory import GLOBAL_SESSION_MANAGER
from crew.recruitment_crew import run_recruitment_crew
from autogen_review.review_team import review_support_response
from observability.logger import log_request
from schemas.response_models import SupportAgentResponse, create_support_agent_response


def process_user_query(
    raw_query: str,
    session_id: Optional[str] = None,
    verbose: bool = False,
) -> SupportAgentResponse:
    """Processes a single user input query through the complete 5-layer pipeline."""
    start_time = time.perf_counter()
    trace_id = str(uuid.uuid4())
    cleaned_query = raw_query.strip()

    # 1. Governance: Runtime Budget Limit (1,000 characters)
    is_budget_valid, budget_err = validate_runtime_budget(cleaned_query)
    if not is_budget_valid:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return create_support_agent_response(
            query=cleaned_query[:200] + "... [OVERSIZED_PAYLOAD]",
            final_answer=f"Error: {budget_err}",
            intent="out_of_scope",
            sources=[],
            escalation_recommended=False,
            review_status="refused",
            trace_id=trace_id,
            cached=False,
            latency_ms=latency_ms,
        )

    # 2. Security: Prompt Injection Detection
    is_injection, pattern = detect_prompt_injection(cleaned_query)
    if is_injection:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return create_support_agent_response(
            query=cleaned_query,
            final_answer=INJECTION_REFUSAL_MESSAGE,
            intent="out_of_scope",
            sources=[],
            escalation_recommended=False,
            review_status="refused",
            trace_id=trace_id,
            cached=False,
            latency_ms=latency_ms,
        )

    # 3. Cache Fast-Path (standalone inquiries)
    if not session_id:
        cached_resp = GLOBAL_RESPONSE_CACHE.get(cleaned_query)
        if cached_resp is not None:
            latency_ms = (time.perf_counter() - start_time) * 1000
            cached_resp.trace_id = trace_id
            cached_resp.cached = True
            cached_resp.latency_ms = latency_ms
            return cached_resp

    # 4. Multi-turn Coreference Resolution
    effective_query = cleaned_query
    if session_id:
        resolved_q, rec_id, needs_clarification = GLOBAL_SESSION_MANAGER.resolve_coreference(
            session_id, cleaned_query
        )
        if needs_clarification:
            clarification_msg = (
                "I don't have context on which application you are referring to. "
                "Please provide the specific application ID (e.g., APP-1001)."
            )
            GLOBAL_SESSION_MANAGER.add_user_turn(session_id, cleaned_query)
            GLOBAL_SESSION_MANAGER.add_ai_turn(session_id, clarification_msg)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return create_support_agent_response(
                query=cleaned_query,
                final_answer=clarification_msg,
                intent="status_lookup",
                sources=[],
                escalation_recommended=False,
                review_status="approved",
                trace_id=trace_id,
                cached=False,
                latency_ms=latency_ms,
            )
        effective_query = resolved_q

    # 5. Multi-Agent Crew Execution
    response = run_recruitment_crew(effective_query, verbose=verbose)
    response.trace_id = trace_id
    response.query = cleaned_query

    # 6. AutoGen Secondary Review
    if response.intent != "out_of_scope":
        verdict = review_support_response(
            draft_answer=response.final_answer,
            context=response.sources,
            query=effective_query,
        )
        if not verdict.approved:
            response.final_answer = verdict.final_answer
            response.review_status = "revised_by_audit"
        else:
            response.review_status = "approved"
        response.audit_reason = verdict.reason

    # 7. Session Memory Update
    if session_id:
        GLOBAL_SESSION_MANAGER.add_user_turn(session_id, cleaned_query)
        GLOBAL_SESSION_MANAGER.add_ai_turn(session_id, response.final_answer)

    latency_ms = (time.perf_counter() - start_time) * 1000
    response.latency_ms = latency_ms
    response.cached = False

    if not session_id:
        GLOBAL_RESPONSE_CACHE.set(cleaned_query, response)

    log_request(
        trace_id=trace_id,
        endpoint="cli",
        latency_ms=latency_ms,
        query=cleaned_query,
        status_code=200,
        cached=False,
        extra={"intent": response.intent, "review_status": response.review_status},
    )

    return response


def display_agent_response(response: SupportAgentResponse) -> None:
    """Pretty prints the agent response to the console."""
    print("\n" + "-" * 75)
    print(f"  [Intent]      : {response.intent}")
    print(f"  [Status]      : {response.review_status}")
    print(f"  [Sources]     : {response.sources if response.sources else 'None'}")
    if response.escalation_recommended:
        print("  [ESCALATION]  : [ALERT] HR Recruiter Escalation Triggered (Escalation Score >= 0.65)")
    else:
        print("  [Escalation]  : No escalation required (Normal)")
    if response.latency_ms is not None:
        print(f"  [Latency]     : {response.latency_ms:.2f} ms (Cached: {response.cached})")
    print("\n  [Final Answer]:")
    print(f"  {response.final_answer}")
    print("-" * 75 + "\n")


def run_interactive_session() -> None:
    """Runs an interactive REPL in the terminal for user questions."""
    session_id = f"cli_{uuid.uuid4().hex[:8]}"
    print("=" * 75)
    print("  Naukri.com Recruitment Domain Support Agent - Interactive Console")
    print("=" * 75)
    print(f"Session ID : {session_id} (Multi-turn memory active)")
    print("Commands   : Type 'reset' to clear session memory, 'exit' or 'quit' to exit.")
    print("Examples   :")
    print("  - Policy     : 'What is the standard probation period duration?'")
    print("  - Application: 'Check status of application APP-1011'")
    print("  - Follow-up  : 'What was its expected salary?' (pronoun resolution)")
    print("=" * 75 + "\n")

    while True:
        try:
            user_input = input("User Question > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("\nExiting interactive session. Goodbye!")
                break

            if user_input.lower() == "reset":
                GLOBAL_SESSION_MANAGER.clear_session(session_id)
                session_id = f"cli_{uuid.uuid4().hex[:8]}"
                print(f"\n[Session Reset] New Session ID: {session_id}\n")
                continue

            resp = process_user_query(user_input, session_id=session_id)
            display_agent_response(resp)

        except (KeyboardInterrupt, EOFError):
            print("\nSession interrupted. Exiting.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Naukri.com Recruitment Support Agent Interactive CLI"
    )
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Execute a single question and exit.",
    )
    parser.add_argument(
        "--session-id",
        "-s",
        type=str,
        default=None,
        help="Optional session ID for multi-turn conversation memory.",
    )
    args = parser.parse_args()

    if args.query:
        resp = process_user_query(args.query, session_id=args.session_id)
        display_agent_response(resp)
    else:
        run_interactive_session()


if __name__ == "__main__":
    main()
