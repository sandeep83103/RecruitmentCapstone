"""
Deterministic Mock LLM Implementation for CrewAI.
Implements the BaseLLM extension point with zero network calls and zero API key requirements.

Addresses the two critical Capstone pitfalls:
1. ReAct Observation Template Defense:
   CrewAI's ReAct system-prompt template contains the literal text:
   'Observation: the result of the action'.
   This mock parser strictly inspects model-generated outputs and real execution steps,
   NEVER searching the system prompt template for 'Observation:'.

2. Schema-Based Tool Dispatch:
   Dispatches tool calls by inspecting declared parameter schemas (e.g., {'record_id': str}
   for application lookup vs {'query': str} for RAG retrieval) rather than substring matching
   on tool names, preventing misclassification of tools such as 'rag_lookup'.
"""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union

# Attempt import from real crewai if available, otherwise use compliant protocol
try:
    from crewai.llms.base_llm import BaseLLM as CrewAIBaseLLM
except (ImportError, ModuleNotFoundError):
    class CrewAIBaseLLM(ABC):
        """Standard CrewAI BaseLLM abstraction for offline execution."""
        
        def __init__(self, model_name: str = "mock-deterministic-llm"):
            self.model_name = model_name

        @abstractmethod
        def call(self, messages: Union[str, List[Dict[str, str]]]) -> str:
            """Execute LLM generation call."""
            pass


class DeterministicMockLLM(CrewAIBaseLLM):
    """
    Production-grade Mock LLM providing deterministic grounded answers,
    tool action generation, and ReAct loop stepping without external network dependencies.
    """

    def __init__(
        self,
        model_name: str = "naukri-mock-llm-v1",
        tool_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        super().__init__(model_name=model_name)
        self.tool_registry = tool_registry or {}
        self.call_history: List[Any] = []

    def register_tool(
        self,
        name: str,
        func: Callable[..., Any],
        param_schema: Dict[str, type],
        description: str = "",
    ) -> None:
        """
        Registers a tool with an explicit parameter schema for schema-based dispatching.
        Avoids name-based substring heuristics (Pitfall 2).
        """
        self.tool_registry[name] = {
            "func": func,
            "schema": param_schema,
            "description": description,
        }

    def dispatch_tool_by_schema(self, tool_args: Dict[str, Any]) -> Optional[str]:
        """
        Dispatches to the registered tool whose parameter schema matches the provided arguments.
        Strictly schema-driven: e.g. {'record_id': ...} -> application lookup tool.
        """
        arg_keys = set(tool_args.keys())
        for tool_name, tool_meta in self.tool_registry.items():
            schema_keys = set(tool_meta["schema"].keys())
            if arg_keys == schema_keys:
                return tool_name
        return None

    def call(self, messages: Union[str, List[Dict[str, str]]]) -> str:
        """
        Processes conversation turns and emits deterministic ReAct actions or final responses.
        Guarded against system-prompt 'Observation:' template false-positives (Pitfall 1).
        """
        self.call_history.append(messages)

        # Normalize message representation
        user_query = ""
        last_observation = None

        if isinstance(messages, str):
            prompt_text = messages
        elif isinstance(messages, list):
            prompt_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
            )
        else:
            prompt_text = str(messages)

        # ----------------------------------------------------------------------
        # Pitfall 1 Defense:
        # CrewAI's system prompt contains:
        # "Observation: the result of the action"
        # We must ONLY look for real Observations generated during actual tool execution,
        # which occur AFTER a user turn or in explicit tool-result blocks.
        # ----------------------------------------------------------------------
        # Extract user query
        query_match = re.search(r"(?:user|Human):\s*(.+?)(?:\n\w+:|$)", prompt_text, re.DOTALL | re.IGNORECASE)
        if query_match:
            user_query = query_match.group(1).strip()
        else:
            # Fallback to entire prompt if single string
            user_query = prompt_text.strip()

        # Extract REAL observations (must follow an Action/Action Input block)
        real_obs_match = re.findall(
            r"Action Input:\s*\{.*?\}\s*\nObservation:\s*(.+?)(?:\nThought:|$)",
            prompt_text,
            re.DOTALL,
        )
        if real_obs_match:
            last_observation = real_obs_match[-1].strip()

        # ----------------------------------------------------------------------
        # ReAct Step 2: If we already have a real observation, formulate Final Answer
        # ----------------------------------------------------------------------
        if last_observation:
            return (
                f"Thought: I have evaluated the observation and verified all policy criteria.\n"
                f"Final Answer: {self._synthesize_final_answer(user_query, last_observation)}"
            )

        # ----------------------------------------------------------------------
        # ReAct Step 1: Analyze query and determine appropriate Action via Schema
        # ----------------------------------------------------------------------
        return self._generate_react_action(user_query)

    def _generate_react_action(self, query: str) -> str:
        """Generates ReAct action using schema matching."""
        normalized = query.lower()

        # Check for Application Lookup intent: record_id pattern (e.g., APP-1001)
        record_match = re.search(r"\bAPP-\d{4}\b", query, re.IGNORECASE)
        if record_match or "status" in normalized or "application" in normalized:
            record_id = record_match.group(0).upper() if record_match else "APP-1001"
            # Schema dispatch: application lookup requires {'record_id': ...}
            tool_name = self.dispatch_tool_by_schema({"record_id": record_id}) or "check_job_application_status"
            return (
                f"Thought: The user is requesting application details. I need to check the application status using its record ID.\n"
                f"Action: {tool_name}\n"
                f"Action Input: {json.dumps({'record_id': record_id})}"
            )

        # Check for Policy Query intent: requires {'query': ...}
        tool_name = self.dispatch_tool_by_schema({"query": query}) or "rag_policy_lookup"
        return (
            f"Thought: The user is asking a hiring policy question. I need to retrieve relevant policy excerpts from the knowledge base.\n"
            f"Action: {tool_name}\n"
            f"Action Input: {json.dumps({'query': query})}"
        )

    def _synthesize_final_answer(self, query: str, observation: str) -> str:
        """Synthesizes candidate-ready final answer from tool observation."""
        try:
            obs_data = json.loads(observation)
            if isinstance(obs_data, dict):
                if "status" in obs_data and "expected_salary_inr" in obs_data:
                    escalation = "Yes" if obs_data.get("escalation_recommended") else "No"
                    return (
                        f"Application {obs_data.get('record_id', 'N/A')} is currently in '{obs_data.get('status')}' stage. "
                        f"Expected CTC is INR {obs_data.get('expected_salary_inr', 0):,}. "
                        f"Escalation Score: {obs_data.get('escalation_score', 0.0):.2f} (Escalation Recommended: {escalation})."
                    )
                if "answer" in obs_data:
                    return str(obs_data["answer"])
        except (json.JSONDecodeError, TypeError):
            pass

        return f"Based on verified recruitment records: {observation}"
