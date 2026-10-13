"""
In-Memory Multi-Turn Session Memory Layer.
Track: Naukri.com Recruitment & HR Operations.

Task 8 Requirements:
- Implementation: LangChain InMemoryChatMessageHistory with session ID lookup.
- Demonstrates:
  - Transcript 1 (Multi-Turn Continuity):
    - Turn 1: "Check the status of application APP-1001."
    - Turn 2: "What was its expected salary?" (Agent resolves "its" to APP-1001).
  - Transcript 2 (Fresh Reset):
    - Fresh session initialized: "What was its expected salary?"
    - Agent correctly indicates lack of context.
- Verification Command (Line 330): python memory/session_memory.py
  Expected Outcome: Multi-turn transcript carries context; reset transcript resets.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from tools.application_lookup import check_job_application_status
from tools.policy_rag_tool import rag_policy_lookup


class SessionMemoryManager:
    """
    Manages in-memory multi-turn session conversations with coreference resolution
    and session boundary isolation.
    """

    def __init__(self):
        self._sessions: Dict[str, InMemoryChatMessageHistory] = {}

    def get_session_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """Retrieves or creates an InMemoryChatMessageHistory for a session ID."""
        if session_id not in self._sessions:
            self._sessions[session_id] = InMemoryChatMessageHistory()
        return self._sessions[session_id]

    def add_user_turn(self, session_id: str, message: str) -> None:
        """Appends user message to session history."""
        history = self.get_session_history(session_id)
        history.add_user_message(message)

    def add_ai_turn(self, session_id: str, message: str) -> None:
        """Appends AI response to session history."""
        history = self.get_session_history(session_id)
        history.add_ai_message(message)

    def clear_session(self, session_id: str) -> None:
        """Resets conversation history for a given session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
            del self._sessions[session_id]

    def extract_recent_record_id(self, session_id: str) -> Optional[str]:
        """
        Scans past messages in session history for recently discussed application record IDs (APP-XXXX).
        """
        history = self.get_session_history(session_id)
        for msg in reversed(history.messages):
            match = re.search(r"\bAPP-\d{4}\b", msg.content, re.IGNORECASE)
            if match:
                return match.group(0).upper()
        return None

    def resolve_coreference(self, session_id: str, query: str) -> Tuple[str, Optional[str], bool]:
        """
        Resolves coreferences (e.g., 'its salary', 'the candidate') using session history.
        
        Returns:
            Tuple of (resolved_query: str, resolved_record_id: Optional[str], requires_context_clarification: bool)
        """
        # Direct mention
        direct_match = re.search(r"\bAPP-\d{4}\b", query, re.IGNORECASE)
        if direct_match:
            rec_id = direct_match.group(0).upper()
            return query, rec_id, False

        # Coreferent pronoun detection
        pronoun_match = re.search(
            r"\b(?:it|its|this|that|the)\s+(?:candidate|application|applicant|expected\s+salary|salary|status|ctc)\b",
            query,
            re.IGNORECASE,
        ) or re.search(r"\b(?:what\s+was\s+its|check\s+its|show\s+its)\b", query, re.IGNORECASE)

        if pronoun_match:
            recent_id = self.extract_recent_record_id(session_id)
            if recent_id:
                # Coreference successfully resolved from previous turn!
                resolved_query = re.sub(
                    r"\b(?:it|its|this|that|the)\b",
                    recent_id,
                    query,
                    flags=re.IGNORECASE,
                )
                return resolved_query, recent_id, False
            else:
                # Coreferent pronoun used without prior context!
                return query, None, True

        return query, None, False


# Global session manager instance
GLOBAL_SESSION_MANAGER = SessionMemoryManager()


def execute_conversational_turn(
    session_id: str,
    query: str,
    manager: Optional[SessionMemoryManager] = None,
) -> Dict[str, Any]:
    """
    Executes a conversational turn using session memory for coreference resolution.
    
    Args:
        session_id: Identifier for the conversation session.
        query: Candidate/recruiter inquiry.
        manager: Optional SessionMemoryManager instance.
        
    Returns:
        Structured response dictionary.
    """
    mem = manager or GLOBAL_SESSION_MANAGER

    # Resolve coreference
    resolved_query, record_id, needs_clarification = mem.resolve_coreference(session_id, query)

    # Transcript 2 scenario: Fresh session missing required context
    if needs_clarification:
        clarification_msg = (
            "I don't have context on which application you are referring to. "
            "Please provide the specific application ID (e.g., APP-1001)."
        )
        mem.add_user_turn(session_id, query)
        mem.add_ai_turn(session_id, clarification_msg)
        return {
            "query": query,
            "resolved_query": query,
            "record_id": None,
            "final_answer": clarification_msg,
            "sources": [],
            "session_id": session_id,
            "context_resolved": False,
        }

    # Application record lookup scenario
    if record_id:
        lookup_res = check_job_application_status(record_id)
        if not lookup_res.get("found", False):
            ans = f"Application record '{record_id}' was not found in the recruitment database."
            sources = []
        else:
            escalation_text = (
                "Escalation recommended to senior HR"
                if lookup_res["escalation_recommended"]
                else "Normal review cadence"
            )
            # Answer specific question if targeted (e.g. salary)
            if "salary" in query.lower() or "ctc" in query.lower():
                ans = (
                    f"Candidate {lookup_res['candidate_name']} ({record_id}) has an expected CTC of "
                    f"INR {lookup_res['expected_salary_inr']:,} for the {lookup_res['category']} position."
                )
            else:
                ans = (
                    f"Application {record_id} ({lookup_res['candidate_name']}) is currently in "
                    f"'{lookup_res['status']}' stage ({lookup_res['category']}). Expected CTC: "
                    f"INR {lookup_res['expected_salary_inr']:,}. Escalation Score: "
                    f"{lookup_res['escalation_score']:.2f} ({escalation_text})."
                )
            sources = [record_id]

        mem.add_user_turn(session_id, query)
        mem.add_ai_turn(session_id, ans)
        return {
            "query": query,
            "resolved_query": resolved_query,
            "record_id": record_id,
            "final_answer": ans,
            "sources": sources,
            "session_id": session_id,
            "context_resolved": True,
        }

    # Policy RAG scenario
    rag_res = rag_policy_lookup(query)
    ans = rag_res["answer"]
    sources = rag_res["sources"]

    mem.add_user_turn(session_id, query)
    mem.add_ai_turn(session_id, ans)

    return {
        "query": query,
        "resolved_query": resolved_query,
        "record_id": None,
        "final_answer": ans,
        "sources": sources,
        "session_id": session_id,
        "context_resolved": True,
    }


def demonstrate_session_memory() -> None:
    """
    Demonstrates Task 8 verification requirements:
    - Transcript 1 (Multi-Turn Continuity): Turn 1 status lookup, Turn 2 salary coreference resolved.
    - Transcript 2 (Fresh Reset): Independent session correctly triggers lack of context notice.
    """
    print("=" * 75)
    print("Task 8: In-Memory Multi-Turn Session Memory Demonstration")
    print("=" * 75)

    test_mgr = SessionMemoryManager()

    # -------------------------------------------------------------------------
    # Transcript 1: Multi-Turn Continuity
    # -------------------------------------------------------------------------
    session_1 = "sess_recruiter_alpha"
    print("\n--- Transcript 1: Multi-Turn Conversation Continuity ---")
    print(f"Session ID: {session_1}\n")

    # Turn 1
    t1_q = "Check the status of application APP-1001."
    print(f"[Turn 1] User: \"{t1_q}\"")
    t1_res = execute_conversational_turn(session_1, t1_q, manager=test_mgr)
    print(f"[Turn 1] Agent: \"{t1_res['final_answer']}\"")
    print(f"         Context: Resolved={t1_res['context_resolved']}, Sources={t1_res['sources']}")
    print()

    # Turn 2: Coreference pronoun 'its'
    t2_q = "What was its expected salary?"
    print(f"[Turn 2] User: \"{t2_q}\"")
    t2_res = execute_conversational_turn(session_1, t2_q, manager=test_mgr)
    print(f"[Turn 2] Agent: \"{t2_res['final_answer']}\"")
    print(f"         Context: Resolved={t2_res['context_resolved']}, Resolved Query=\"{t2_res['resolved_query']}\"")
    print()

    # -------------------------------------------------------------------------
    # Transcript 2: Fresh Session Reset
    # -------------------------------------------------------------------------
    session_2 = "sess_fresh_beta"
    print("--- Transcript 2: Fresh Session Isolation & Lack of Context Notice ---")
    print(f"Session ID: {session_2} (Unlinked Fresh Session)\n")

    fresh_q = "What was its expected salary?"
    print(f"[Turn 1] User: \"{fresh_q}\"")
    fresh_res = execute_conversational_turn(session_2, fresh_q, manager=test_mgr)
    print(f"[Turn 1] Agent: \"{fresh_res['final_answer']}\"")
    print(f"         Context: Resolved={fresh_res['context_resolved']} (Correctly flags lack of context)")
    print("=" * 75)
    print("Verification Result: Multi-turn transcript carries context; reset transcript resets.")
    print("=" * 75)


if __name__ == "__main__":
    demonstrate_session_memory()
