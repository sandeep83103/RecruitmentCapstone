"""
Policy RAG Retrieval Tool for Recruitment Knowledge Base.
Wraps grounded retrieval across ChromaDB policy collections for agent invocation.
"""

from typing import Any, Dict
from rag.retrieval import retrieve_grounded_answer, FALLBACK_REFUSAL_MESSAGE


def rag_policy_lookup(query: str) -> Dict[str, Any]:
    """
    Recruitment Policy Knowledge Retrieval Tool.
    
    Args:
        query: Specific policy question regarding eligibility, notice period,
               probation, referral bonus, remote work, background verification, etc.
               
    Returns:
        Grounded answer with verified source citations and similarity scores.
    """
    if not query or not query.strip():
        return {
            "query": "",
            "is_grounded": False,
            "top_similarity": 0.0,
            "answer": "Please provide a valid policy inquiry.",
            "sources": [],
        }

    result = retrieve_grounded_answer(query.strip())
    return {
        "query": query,
        "is_grounded": result["is_grounded"],
        "top_similarity": result["top_similarity"],
        "answer": result["answer"],
        "sources": result["sources"],
    }


# Alias for CrewAI tools naming convention
rag_policy_tool = rag_policy_lookup


if __name__ == "__main__":
    print("=" * 70)
    print("Policy RAG Tool Demonstration")
    print("=" * 70)
    
    test_q = "What is the probation period duration?"
    print(f"\nQuery: {test_q}")
    out = rag_policy_lookup(test_q)
    print(f"Grounded : {out['is_grounded']} (Top Similarity: {out['top_similarity']})")
    print(f"Sources  : {out['sources']}")
    print(f"Answer   : {out['answer']}")
    print("=" * 70)
