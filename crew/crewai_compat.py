"""
CrewAI Compatibility and Orchestration Layer.
Provides standard Agent, Task, Crew, Process, and Tool abstractions conforming to CrewAI APIs.
Ensures 100% deterministic, offline execution with zero network requirements and zero build dependencies.
"""

from enum import Enum
import inspect
import json
import re
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel


class Process(str, Enum):
    """Execution process for Crew workflows."""
    sequential = "sequential"
    hierarchical = "hierarchical"


class TaskOutput(BaseModel):
    """Output representation for a completed Crew task."""
    description: str
    summary: Optional[str] = None
    raw: str
    agent: str

    def __str__(self) -> str:
        return self.raw


class CrewOutput(BaseModel):
    """Final output object returned by Crew.kickoff()."""
    raw: str
    tasks_output: List[TaskOutput] = []

    def __str__(self) -> str:
        return self.raw


class CrewTool:
    """Standard wrapper for CrewAI tools."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        description: str = "",
        args_schema: Optional[Dict[str, type]] = None,
    ):
        self.name = name
        self.func = func
        self.description = description
        self.args_schema = args_schema or {}

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.run(*args, **kwargs)


def tool(name_or_func: Union[str, Callable] = None, description: str = ""):
    """Decorator to define Crew tools."""
    def decorator(fn: Callable) -> CrewTool:
        tool_name = name_or_func if isinstance(name_or_func, str) else fn.__name__
        tool_desc = description or (fn.__doc__ or "").strip()
        sig = inspect.signature(fn)
        schema = {p.name: p.annotation for p in sig.parameters.values()}
        return CrewTool(name=tool_name, func=fn, description=tool_desc, args_schema=schema)

    if callable(name_or_func):
        return decorator(name_or_func)
    return decorator


class Agent:
    """
    CrewAI Agent specification with Least Autonomy governance enforcement.
    """

    ALLOWED_TOOLS_MAP = {
        "Recruitment Policy Researcher": {"rag_policy_tool", "rag_policy_lookup"},
        "Application Records Specialist": {"check_job_application_status"},
        "Senior HR Communication Specialist": set(),
    }

    def __init__(
        self,
        role: str,
        goal: str,
        backstory: str,
        tools: Optional[List[Any]] = None,
        llm: Optional[Any] = None,
        verbose: bool = True,
        allow_delegation: bool = False,
    ):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = self._normalize_tools(tools or [])
        self.llm = llm
        self.verbose = verbose
        self.allow_delegation = allow_delegation

        # Enforce Least Autonomy Governance Constraint (Task 15)
        self._enforce_least_autonomy()

    def _normalize_tools(self, tool_list: List[Any]) -> List[CrewTool]:
        normalized = []
        for t in tool_list:
            if isinstance(t, CrewTool):
                normalized.append(t)
            elif callable(t):
                name = getattr(t, "__name__", "tool")
                desc = getattr(t, "__doc__", "") or ""
                sig = inspect.signature(t)
                schema = {p.name: p.annotation for p in sig.parameters.values()}
                normalized.append(CrewTool(name=name, func=t, description=desc, args_schema=schema))
            elif hasattr(t, "name") and hasattr(t, "run"):
                normalized.append(t)
            else:
                raise ValueError(f"Unsupported tool format: {t}")
        return normalized

    def _enforce_least_autonomy(self) -> None:
        """
        Enforces Task 15 Governance:
        Application tool cannot be assigned to Retrieval Agent or Response Composer Agent.
        """
        if self.role in self.ALLOWED_TOOLS_MAP:
            allowed = self.ALLOWED_TOOLS_MAP[self.role]
            for t in self.tools:
                tool_name = getattr(t, "name", getattr(t, "__name__", str(t)))
                if tool_name not in allowed:
                    raise PermissionError(
                        f"Governance Violation (Least Autonomy): Tool '{tool_name}' "
                        f"is not permitted for role '{self.role}'. Allowed tools: {list(allowed)}."
                    )


class Task:
    """
    Represents an atomic assignment for an Agent in the Crew.
    """

    def __init__(
        self,
        description: str,
        expected_output: str,
        agent: Agent,
        tools: Optional[List[Any]] = None,
    ):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.tools = tools or []
        self.output: Optional[TaskOutput] = None


class Crew:
    """
    Crew orchestrator managing agents, task sequences, and deterministic execution.
    """

    def __init__(
        self,
        agents: List[Agent],
        tasks: List[Task],
        process: Process = Process.sequential,
        verbose: bool = True,
    ):
        self.agents = agents
        self.tasks = tasks
        self.process = process
        self.verbose = verbose

    def kickoff(self, inputs: Optional[Dict[str, Any]] = None) -> CrewOutput:
        """
        Executes crew tasks sequentially through agents, passing context forward.
        """
        inputs = inputs or {}
        context_outputs: List[str] = []
        task_results: List[TaskOutput] = []

        query = inputs.get("query", "")

        for idx, task in enumerate(self.tasks):
            agent = task.agent
            formatted_desc = task.description.format(**inputs) if inputs else task.description

            if self.verbose:
                print(f"\n[Agent: {agent.role}] Executing Task: {formatted_desc[:80]}...")

            raw_output = self._execute_agent_task(
                agent=agent,
                task_desc=formatted_desc,
                query=query,
                previous_context=context_outputs,
            )

            if self.verbose:
                print(f"[Agent: {agent.role}] Output: {raw_output[:120]}...")

            task_output = TaskOutput(
                description=formatted_desc,
                raw=raw_output,
                agent=agent.role,
            )
            task.output = task_output
            task_results.append(task_output)
            context_outputs.append(f"[{agent.role}]: {raw_output}")

        # The final task's output is synthesized by Response Composer Agent
        final_answer = task_results[-1].raw if task_results else "No response generated."
        return CrewOutput(raw=final_answer, tasks_output=task_results)

    def _execute_agent_task(
        self,
        agent: Agent,
        task_desc: str,
        query: str,
        previous_context: List[str],
    ) -> str:
        """Executes a single agent's assignment using the agent's LLM and tools."""
        llm = agent.llm

        # Build prompt representing agent assignment and context
        context_str = "\n".join(previous_context) if previous_context else "None"
        prompt = (
            f"Role: {agent.role}\n"
            f"Goal: {agent.goal}\n"
            f"Task: {task_desc}\n"
            f"User Query: {query}\n"
            f"Previous Findings:\n{context_str}\n"
        )

        # Agent with no tools (e.g. Response Composer Agent) directly generates final synthesis
        if not agent.tools:
            if hasattr(llm, "_synthesize_final_composer_answer"):
                return llm._synthesize_final_composer_answer(query, previous_context)
            # Default synthesis
            clean_context = "\n".join(previous_context)
            return (
                f"HR Formal Communication:\n"
                f"Regarding your inquiry '{query}':\n"
                f"{clean_context}"
            )

        # Agent with tools (Retrieval Agent or Lookup Agent):
        # Register agent's specific tools with LLM
        tool_map = {t.name: t for t in agent.tools}
        
        # Step 1: LLM proposes action
        react_step_1 = llm._generate_react_action(query, allowed_tools=list(tool_map.keys()))

        # Check if LLM determined an Action
        action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)", react_step_1)
        input_match = re.search(r"Action Input:\s*(\{.*?\})", react_step_1, re.DOTALL)

        if action_match and input_match:
            action_name = action_match.group(1).strip()
            try:
                action_args = json.loads(input_match.group(1).strip())
            except Exception:
                action_args = {}

            if self.verbose:
                print(f"  -> Tool Action: {action_name}({action_args})")

            # Execute tool if present in agent's allowed tools
            if action_name in tool_map:
                tool_instance = tool_map[action_name]
                tool_result = tool_instance.run(**action_args)
                obs_str = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)

                if self.verbose:
                    print(f"  <- Tool Observation: {obs_str[:120]}...")

                # Step 2: Synthesize answer with observation
                step_2_prompt = (
                    f"Human: {query}\n"
                    f"Action: {action_name}\n"
                    f"Action Input: {json.dumps(action_args)}\n"
                    f"Observation: {obs_str}\n"
                )
                step_2_response = llm.call(step_2_prompt)
                
                # Extract Final Answer
                final_match = re.search(r"Final Answer:\s*(.+)$", step_2_response, re.DOTALL)
                if final_match:
                    return final_match.group(1).strip()
                return step_2_response
            else:
                return f"Tool {action_name} not permitted for agent {agent.role}."

        # If no tool was needed
        return f"Completed assessment: {react_step_1}"
