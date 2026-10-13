"""
Unit and Integration Tests for Phase 2: Part 1 — Dataset Design & RAG Core.
Tests Tasks 1 through 5:
- Task 1: Dataset generator constraints (seed=42, N >= 40, category >= 3, status >= 1, priority 10-30%)
- Task 2: Policy Knowledge Base authoring (>= 12 distinct markdown files)
- Task 3: Dual chunking strategies (Fixed 200/40 vs Sentence-based) and ChromaDB indexing
- Task 4: Similarity threshold calibration and fallback gating (tau_RAG = 0.60)
- Task 5: Precision and recall evaluation
"""

import pytest
from pathlib import Path

import config
from dataset import (
    CATEGORIES,
    STATUSES,
    SALARY_BANDS,
    generate_job_applications,
    validate_dataset,
)
from rag.chunking import fixed_size_chunking, sentence_based_chunking
from rag.vector_store import (
    get_chroma_client,
    get_or_create_collections,
    load_knowledge_base_documents,
    query_collection,
)
from rag.retrieval import (
    FALLBACK_REFUSAL_MESSAGE,
    retrieve_grounded_answer,
    calibrate_similarity_threshold,
)
from rag.eval_chunking import (
    EVAL_QUERIES,
    evaluate_collection_precision_recall,
    run_chunking_comparison,
)


def test_dataset_generation_constraints():
    """Verify that dataset generation satisfies all strict Capstone criteria."""
    records = generate_job_applications(seed=42, count=45)
    assert len(records) >= 40
    assert validate_dataset(records) is True

    # Determinism test: calling with same seed produces identical results
    records_repeat = generate_job_applications(seed=42, count=45)
    assert records == records_repeat

    # Category coverage
    cat_counts = {c: 0 for c in CATEGORIES}
    for r in records:
        cat_counts[r["category"]] += 1
    for cat, cnt in cat_counts.items():
        assert cnt >= 3, f"Category {cat} has fewer than 3 records ({cnt})"

    # Status coverage
    status_counts = {s: 0 for s in STATUSES}
    for r in records:
        status_counts[r["status"]] += 1
    for s, cnt in status_counts.items():
        assert cnt >= 1, f"Status {s} has fewer than 1 record ({cnt})"

    # Priority percentage band [10%, 30%]
    priority_cnt = sum(1 for r in records if r["flagged_priority_review"])
    priority_pct = (priority_cnt / len(records)) * 100
    assert 10.0 <= priority_pct <= 30.0

    # Salary ranges
    for r in records:
        cat = r["category"]
        min_s, max_s = SALARY_BANDS[cat]
        assert min_s <= r["expected_salary_inr"] <= max_s


def test_knowledge_base_documents():
    """Verify >= 12 markdown documents exist with authoritative policy content."""
    docs = load_knowledge_base_documents()
    assert len(docs) >= 12

    expected_files = [
        "01_eligibility_criteria.md",
        "02_interview_scheduling.md",
        "03_offer_negotiation.md",
        "04_background_verification.md",
        "05_notice_period.md",
        "06_referral_bonus.md",
        "07_internal_transfer.md",
        "08_probation_period.md",
        "09_remote_work.md",
        "10_diversity_hiring.md",
        "11_exit_interview.md",
        "12_data_retention.md",
    ]

    doc_ids = [doc_id for doc_id, _ in docs]
    for ef in expected_files:
        assert ef in doc_ids, f"Missing required policy file: {ef}"

    for doc_id, text in docs:
        assert len(text.strip()) > 50, f"Policy file {doc_id} is unexpectedly short"


def test_dual_chunking_strategies():
    """Verify both chunking strategies generate valid chunk structures."""
    sample_text = (
        "The standard probation duration for all new hires is 6 months starting from the verified date of joining. "
        "A formal 30-day performance review milestone is conducted between the employee and line manager. "
        "HR issues an official confirmation letter based on manager endorsement."
    )

    # Strategy A: Fixed-size 200/40
    fixed_chunks = fixed_size_chunking(sample_text, doc_id="test_doc.md", window=200, overlap=40)
    assert len(fixed_chunks) >= 1
    for fc in fixed_chunks:
        assert fc.strategy == "fixed"
        assert fc.char_length <= 200
        assert fc.doc_id == "test_doc.md"

    # Strategy B: Sentence-based
    sent_chunks = sentence_based_chunking(sample_text, doc_id="test_doc.md")
    assert len(sent_chunks) == 3
    for sc in sent_chunks:
        assert sc.strategy == "sentence"
        assert sc.doc_id == "test_doc.md"


def test_chromadb_collections_exist_and_populated():
    """Verify ChromaDB collections are created and populated with chunks."""
    client = get_chroma_client()
    fixed_col, sentence_col = get_or_create_collections(client)

    assert fixed_col.count() > 0
    assert sentence_col.count() > 0


def test_similarity_calibration_and_threshold_gating():
    """Verify that in-scope queries pass tau_RAG=0.60 and out-of-scope triggers fallback."""
    calib_results = calibrate_similarity_threshold()
    min_in, max_in = calib_results["in_scope_cluster"]
    min_out, max_out = calib_results["out_scope_cluster"]

    # In-scope cluster should be distinctly higher than out-of-scope cluster
    assert min_in >= config.RAG_SIMILARITY_THRESHOLD
    assert max_out < config.RAG_SIMILARITY_THRESHOLD

    # In-scope query returns grounded answer
    grounded_res = retrieve_grounded_answer("What is the probation duration?")
    assert grounded_res["is_grounded"] is True
    assert grounded_res["top_similarity"] >= config.RAG_SIMILARITY_THRESHOLD
    assert "08_probation_period.md" in grounded_res["sources"]
    assert len(grounded_res["answer"]) > 10

    # Out-of-scope query triggers fallback refusal
    fallback_res = retrieve_grounded_answer("What is the stock price of Google?")
    assert fallback_res["is_grounded"] is False
    assert fallback_res["top_similarity"] < config.RAG_SIMILARITY_THRESHOLD
    assert fallback_res["answer"] == FALLBACK_REFUSAL_MESSAGE


def test_chunking_evaluation():
    """Verify document-level Precision and Recall arithmetic across collections."""
    fixed_eval = evaluate_collection_precision_recall("naukri_fixed_chunks", top_k=3)
    sentence_eval = evaluate_collection_precision_recall("naukri_sentence_chunks", top_k=3)

    assert len(fixed_eval) == len(EVAL_QUERIES)
    assert len(sentence_eval) == len(EVAL_QUERIES)

    for item in fixed_eval:
        assert 0.0 <= item["precision"] <= 1.0
        assert 0.0 <= item["recall"] <= 1.0

    for item in sentence_eval:
        assert 0.0 <= item["precision"] <= 1.0
        assert 0.0 <= item["recall"] <= 1.0

    comparison = run_chunking_comparison(top_k=3)
    assert "recommendation" in comparison
    assert len(comparison["recommendation"]) > 20
