"""
Crew Package for Naukri.com Domain Support Agent.
"""

from crew.mock_llm import DeterministicMockLLM, CrewAIBaseLLM
from crew.crewai_compat import (
    Agent,
    Task,
    Crew,
    Process,
    tool,
    CrewTool,
    TaskOutput,
    CrewOutput,
)
from crew.recruitment_crew import (
    build_recruitment_crew,
    run_recruitment_crew,
    classify_query_intent,
    demonstrate_recruitment_crew,
)

__all__ = [
    "DeterministicMockLLM",
    "CrewAIBaseLLM",
    "Agent",
    "Task",
    "Crew",
    "Process",
    "tool",
    "CrewTool",
    "TaskOutput",
    "CrewOutput",
    "build_recruitment_crew",
    "run_recruitment_crew",
    "classify_query_intent",
    "demonstrate_recruitment_crew",
]
