"""
Evaluation and LLM-as-a-Judge Suite Package for Naukri.com Domain Support Agent.
"""

from evaluation.judge_suite import (
    load_benchmark_queries,
    evaluate_accuracy,
    evaluate_grounding,
    evaluate_completeness,
    evaluate_safety,
    run_benchmark_evaluation,
)

__all__ = [
    "load_benchmark_queries",
    "evaluate_accuracy",
    "evaluate_grounding",
    "evaluate_completeness",
    "evaluate_safety",
    "run_benchmark_evaluation",
]
