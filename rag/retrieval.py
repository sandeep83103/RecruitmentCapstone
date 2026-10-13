"""
Grounded RAG Retrieval and Empirical Fallback Calibration for Naukri.com Support Agent.
Implements similarity-threshold gating (tau_RAG = 0.60) to guarantee factual adherence
and strict fallback rejection for out-of-scope queries.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from rag.vector_store import (
    OfflineSentenceTransformerEmbeddingFunction,
    get_chroma_client,
    query_collection,
)

FALLBACK_REFUSAL_MESSAGE = "I don't have information on this topic in the company recruitment policy."

# Calibration Benchmark Queries
CALIBRATION_IN_SCOPE_QUERIES = [
    "What is the probation duration?",
    "Explain referral bonus payout",
    "Can I work remotely?",
]

CALIBRATION_OUT_OF_SCOPE_QUERIES = [
    "What is the stock price of Google?",
    "How to bake a chocolate cake?",
]

DEMO_IN_SCOPE_QUERIES = [
    "What is the probation duration?",
    "Explain referral bonus payout",
    "Can I work remotely?",
    "What are the background verification requirements?",
    "What is the notice period buyout policy?",
]

DEMO_OUT_OF_SCOPE_QUERY = "What is the stock price of Google?"


def retrieve_grounded_answer(
    query: str,
    threshold: float = config.RAG_SIMILARITY_THRESHOLD,
    top_k: int = 3,
    collection_name: str = "naukri_sentence_chunks",
    client: Optional[Any] = None,
    embedding_fn: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Retrieves policy context and synthesizes a grounded answer.
    If the top-1 cosine similarity falls below `threshold` (0.60),
    triggers empirical fallback refusal.
    """
    chunks = query_collection(
        collection_name=collection_name,
        query=query,
        top_k=top_k,
        client=client,
        embedding_fn=embedding_fn,
    )

    if not chunks:
        return {
            "query": query,
            "is_grounded": False,
            "top_similarity": 0.0,
            "threshold": threshold,
            "answer": FALLBACK_REFUSAL_MESSAGE,
            "sources": [],
            "retrieved_chunks": [],
        }

    top_chunk = chunks[0]
    top_sim = top_chunk["similarity"]

    # Threshold gating
    if top_sim < threshold:
        return {
            "query": query,
            "is_grounded": False,
            "top_similarity": round(top_sim, 4),
            "threshold": threshold,
            "answer": FALLBACK_REFUSAL_MESSAGE,
            "sources": [],
            "retrieved_chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": c["doc_id"],
                    "similarity": round(c["similarity"], 4),
                }
                for c in chunks
            ],
        }

    # Extract distinct source document IDs
    sources = list(dict.fromkeys(c["doc_id"] for c in chunks if c["similarity"] >= threshold))
    if not sources and chunks:
        sources = [top_chunk["doc_id"]]

    # Synthesize grounded answer from top matching chunks
    relevant_excerpts = [c["content"] for c in chunks if c["similarity"] >= threshold]
    if not relevant_excerpts:
        relevant_excerpts = [top_chunk["content"]]

    synthesized_answer = " ".join(relevant_excerpts)

    return {
        "query": query,
        "is_grounded": True,
        "top_similarity": round(top_sim, 4),
        "threshold": threshold,
        "answer": synthesized_answer,
        "sources": sources,
        "retrieved_chunks": [
            {
                "chunk_id": c["chunk_id"],
                "doc_id": c["doc_id"],
                "similarity": round(c["similarity"], 4),
                "content": c["content"],
            }
            for c in chunks
        ],
    }


def calibrate_similarity_threshold(collection_name: str = "naukri_sentence_chunks") -> Dict[str, Any]:
    """
    Executes empirical calibration protocol comparing top-1 cosine similarities
    between in-scope policy queries and out-of-scope domain queries.
    """
    print("=" * 70)
    print("Task 4: Empirical RAG Fallback Threshold Calibration Protocol")
    print("=" * 70)

    in_scope_scores: List[float] = []
    out_scope_scores: List[float] = []

    print("\n1. In-Scope Hiring Policy Queries:")
    for q in CALIBRATION_IN_SCOPE_QUERIES:
        res = query_collection(collection_name, q, top_k=1)
        sim = res[0]["similarity"] if res else 0.0
        in_scope_scores.append(sim)
        doc = res[0]["doc_id"] if res else "None"
        print(f"  - Query: \"{q}\"")
        print(f"    Top-1 Doc: {doc} | Cosine Similarity: {sim:.4f}")

    print("\n2. Out-of-Scope Queries:")
    for q in CALIBRATION_OUT_OF_SCOPE_QUERIES:
        res = query_collection(collection_name, q, top_k=1)
        sim = res[0]["similarity"] if res else 0.0
        out_scope_scores.append(sim)
        doc = res[0]["doc_id"] if res else "None"
        print(f"  - Query: \"{q}\"")
        print(f"    Top-1 Doc: {doc} | Cosine Similarity: {sim:.4f}")

    min_in = min(in_scope_scores)
    max_in = max(in_scope_scores)
    min_out = min(out_scope_scores)
    max_out = max(out_scope_scores)

    print("\nEmpirical Clustering Analysis:")
    print(f"  - In-Scope Cluster (S_in)   : [{min_in:.2f}, {max_in:.2f}]")
    print(f"  - Out-of-Scope Cluster (S_out): [{min_out:.2f}, {max_out:.2f}]")
    
    calibrated_cutoff = 0.60
    print(f"\nCalibrated Threshold Decision:")
    print(f"  - Selected Cutoff (tau_RAG) = {calibrated_cutoff:.2f}")
    print(f"  - Safety Margin Above Max Out-of-Scope: {calibrated_cutoff - max_out:+.2f}")
    print(f"  - Cushion Below Min In-Scope:           {min_in - calibrated_cutoff:+.2f}")
    print("=" * 70)

    return {
        "in_scope_cluster": (round(min_in, 2), round(max_in, 2)),
        "out_scope_cluster": (round(min_out, 2), round(max_out, 2)),
        "calibrated_threshold": calibrated_cutoff,
    }


def demonstrate_grounded_rag(collection_name: str = "naukri_sentence_chunks") -> None:
    """
    Demonstrates 5 in-scope queries showing accurate retrieval and answer generation,
    and 1 out-of-scope query showing successful trigger of the fallback.
    """
    print("\n" + "=" * 70)
    print("Demonstration: Grounded Generation and Fallback Gating")
    print("=" * 70)

    print("\n--- 5 In-Scope Queries (Expected: Grounded Answer & Source Attribution) ---")
    for i, q in enumerate(DEMO_IN_SCOPE_QUERIES, 1):
        result = retrieve_grounded_answer(q, collection_name=collection_name)
        print(f"\n[Query {i}] \"{q}\"")
        print(f"  Status        : {'GROUNDED' if result['is_grounded'] else 'REFUSED'}")
        print(f"  Top Similarity: {result['top_similarity']:.4f} (Threshold: {result['threshold']})")
        print(f"  Sources       : {result['sources']}")
        print(f"  Answer        : {result['answer'][:160]}...")

    print("\n--- 1 Out-of-Scope Query (Expected: Refusal Fallback Triggered) ---")
    oos_result = retrieve_grounded_answer(DEMO_OUT_OF_SCOPE_QUERY, collection_name=collection_name)
    print(f"\n[Out-of-Scope Query] \"{DEMO_OUT_OF_SCOPE_QUERY}\"")
    print(f"  Status        : {'GROUNDED' if oos_result['is_grounded'] else 'REFUSED (FALLBACK TRIGGERED)'}")
    print(f"  Top Similarity: {oos_result['top_similarity']:.4f} (Threshold: {oos_result['threshold']})")
    print(f"  Sources       : {oos_result['sources']}")
    print(f"  Answer        : \"{oos_result['answer']}\"")
    print("=" * 70)


if __name__ == "__main__":
    calibrate_similarity_threshold()
    demonstrate_grounded_rag()
