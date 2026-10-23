"""
Production FastAPI REST & WebSocket Serving Layer for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 11 Requirements:
- POST /ask: Accepts AskRequest(query: str, session_id: Optional[str]),
  returns validated SupportAgentResponse.
- POST /add-document: Accepts DocumentUpload(title: str, content: str),
  chunks, embeds, and updates ChromaDB collections.
- WebSocket Endpoint: WS /ws/chat via app.websocket.py.
- Telemetry disabled, deterministic offline MOCK_LLM execution.
"""

import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from schemas.response_models import (
    AskRequest,
    DocumentUpload,
    SupportAgentResponse,
    create_support_agent_response,
)
from guardrails.pii_masker import mask_pii
from guardrails.injection_detector import detect_prompt_injection, INJECTION_REFUSAL_MESSAGE
from memory.session_memory import GLOBAL_SESSION_MANAGER
from crew.recruitment_crew import run_recruitment_crew
from rag.chunking import fixed_size_chunking, sentence_based_chunking
from rag.vector_store import (
    get_chroma_client,
    get_or_create_collections,
    get_embedding_function,
)
from observability.logger import log_request, read_logs, verify_no_unmasked_phone_pii
from app.websocket import router as websocket_router
from governance.budget_controller import validate_runtime_budget
from cache.response_cache import GLOBAL_RESPONSE_CACHE, normalize_query
from autogen_review.review_team import review_support_response


# Initialize FastAPI App
app = FastAPI(
    title="Naukri.com Domain Support Agent API",
    version="1.0.0",
    description=(
        "Production-grade REST & WebSocket API for HR policy RAG, "
        "application status tracking, and multi-agent coordination."
    ),
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount WebSocket router
app.include_router(websocket_router)


# ------------------------------------------------------------------------------
# REST Endpoints
# ------------------------------------------------------------------------------

@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint confirming service status and operational track."""
    return {
        "status": "healthy",
        "service": "Naukri.com Domain Support Agent",
        "track": config.TRACK_NAME,
        "mock_llm": config.MOCK_LLM_ENABLED,
        "governance_risk": config.RISK_CLASSIFICATION,
    }


@app.post(
    "/ask",
    response_model=SupportAgentResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inference"],
)
def ask_question(request: AskRequest) -> SupportAgentResponse:
    """
    Main question-answering inference endpoint.
    
    Accepts:
        AskRequest(query: str, session_id: Optional[str])
        
    Enforces:
        - Max 1,000 character length limit (HTTP 413)
        - Pre-disk PII redaction on log writes
        - Prompt injection safety detection
        - Multi-turn session memory carryover and coreference resolution
        - Strict SupportAgentResponse Pydantic schema validation
    """
    start_time = time.perf_counter()
    trace_id = str(uuid.uuid4())
    raw_query = request.query.strip()

    # Governance Layer 2: Runtime Budget Limit (1,000 chars max)
    is_budget_valid, budget_err = validate_runtime_budget(raw_query)
    if not is_budget_valid:
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_request(
            trace_id=trace_id,
            endpoint="/ask",
            latency_ms=latency_ms,
            query=raw_query[:200] + "... [OVERSIZED_PAYLOAD]",
            status_code=413,
            cached=False,
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=budget_err,
        )

    # Security: Prompt Injection Guardrail
    is_injection, pattern = detect_prompt_injection(raw_query)
    if is_injection:
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_request(
            trace_id=trace_id,
            endpoint="/ask",
            latency_ms=latency_ms,
            query=raw_query,
            status_code=200,
            cached=False,
            extra={"guardrail": "prompt_injection_blocked", "pattern": pattern},
        )
        return create_support_agent_response(
            query=raw_query,
            final_answer=INJECTION_REFUSAL_MESSAGE,
            intent="out_of_scope",
            sources=[],
            escalation_recommended=False,
            review_status="refused",
            trace_id=trace_id,
            cached=False,
            latency_ms=latency_ms,
        )

    # Governance Layer 2: Normalized Response Cache Fast-Path (standalone inquiries)
    if not request.session_id:
        cached_resp = GLOBAL_RESPONSE_CACHE.get(raw_query)
        if cached_resp is not None:
            latency_ms = (time.perf_counter() - start_time) * 1000
            cached_resp.trace_id = trace_id
            cached_resp.cached = True
            cached_resp.latency_ms = latency_ms
            log_request(
                trace_id=trace_id,
                endpoint="/ask",
                latency_ms=latency_ms,
                query=raw_query,
                status_code=200,
                cached=True,
                extra={"intent": cached_resp.intent, "cache": "hit"},
            )
            return cached_resp

    # Multi-turn Coreference Resolution
    effective_query = raw_query
    if request.session_id:
        resolved_q, rec_id, needs_clarification = GLOBAL_SESSION_MANAGER.resolve_coreference(
            request.session_id, raw_query
        )
        if needs_clarification:
            clarification_msg = (
                "I don't have context on which application you are referring to. "
                "Please provide the specific application ID (e.g., APP-1001)."
            )
            GLOBAL_SESSION_MANAGER.add_user_turn(request.session_id, raw_query)
            GLOBAL_SESSION_MANAGER.add_ai_turn(request.session_id, clarification_msg)

            latency_ms = (time.perf_counter() - start_time) * 1000
            log_request(
                trace_id=trace_id,
                endpoint="/ask",
                latency_ms=latency_ms,
                query=raw_query,
                status_code=200,
                cached=False,
            )
            return create_support_agent_response(
                query=raw_query,
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

    # Multi-Agent Execution via CrewAI Kickoff
    response = run_recruitment_crew(effective_query, verbose=False)
    response.trace_id = trace_id
    response.query = raw_query  # Keep original user query in top-level field

    # Governance Layer 3: AutoGen Multi-Agent Secondary Review Stage
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

    # Update session memory
    if request.session_id:
        GLOBAL_SESSION_MANAGER.add_user_turn(request.session_id, raw_query)
        GLOBAL_SESSION_MANAGER.add_ai_turn(request.session_id, response.final_answer)

    latency_ms = (time.perf_counter() - start_time) * 1000
    response.latency_ms = latency_ms
    response.cached = False

    # Store in normalized response cache
    if not request.session_id:
        GLOBAL_RESPONSE_CACHE.set(raw_query, response)

    log_request(
        trace_id=trace_id,
        endpoint="/ask",
        latency_ms=latency_ms,
        query=raw_query,
        status_code=200,
        cached=False,
        extra={"intent": response.intent, "review_status": response.review_status},
    )

    return response


@app.post(
    "/add-document",
    status_code=status.HTTP_200_OK,
    tags=["Administration"],
)
def add_document(upload: DocumentUpload) -> Dict[str, Any]:
    """
    Administrative document upload and vector indexing endpoint.
    
    Accepts:
        DocumentUpload(title: str, content: str)
        
    Actions:
        1. Persists markdown file in knowledge_base/.
        2. Applies dual chunking strategies (Fixed 200/40 and Sentence-based).
        3. Embeds and upserts chunks into ChromaDB collections.
        4. Writes structured log record with trace attribution.
    """
    start_time = time.perf_counter()
    trace_id = str(uuid.uuid4())

    title = upload.title.strip()
    content = upload.content.strip()

    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document title cannot be empty.",
        )
    if len(content) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document content must contain at least 10 characters.",
        )

    # Format filename safely
    filename = title if title.endswith(".md") else f"{title}.md"
    file_path = config.KNOWLEDGE_BASE_DIR / filename

    try:
        # Write to disk
        file_path.write_text(content, encoding="utf-8")

        # Chunk using both strategies
        fixed_chunks = fixed_size_chunking(content, doc_id=filename, window=200, overlap=40)
        sentence_chunks = sentence_based_chunking(content, doc_id=filename)

        # Upsert into ChromaDB
        client = get_chroma_client()
        embedding_fn = get_embedding_function()
        fixed_col, sentence_col = get_or_create_collections(client, embedding_fn)

        if fixed_chunks:
            fixed_col.upsert(
                ids=[c.chunk_id for c in fixed_chunks],
                documents=[c.content for c in fixed_chunks],
                metadatas=[
                    {
                        "doc_id": c.doc_id,
                        "strategy": c.strategy,
                        "char_length": c.char_length,
                        "index": c.index,
                    }
                    for c in fixed_chunks
                ],
            )

        if sentence_chunks:
            sentence_col.upsert(
                ids=[c.chunk_id for c in sentence_chunks],
                documents=[c.content for c in sentence_chunks],
                metadatas=[
                    {
                        "doc_id": c.doc_id,
                        "strategy": c.strategy,
                        "char_length": c.char_length,
                        "index": c.index,
                    }
                    for c in sentence_chunks
                ],
            )

        latency_ms = (time.perf_counter() - start_time) * 1000
        log_request(
            trace_id=trace_id,
            endpoint="/add-document",
            latency_ms=latency_ms,
            query=f"Upload document: {filename}",
            status_code=200,
            cached=False,
            extra={
                "fixed_chunks": len(fixed_chunks),
                "sentence_chunks": len(sentence_chunks),
            },
        )

        return {
            "status": "success",
            "title": title,
            "filename": filename,
            "fixed_chunks_count": len(fixed_chunks),
            "sentence_chunks_count": len(sentence_chunks),
            "message": f"Document '{filename}' successfully chunked and indexed into ChromaDB collections.",
        }

    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_request(
            trace_id=trace_id,
            endpoint="/add-document",
            latency_ms=latency_ms,
            query=f"Failed document upload: {filename}",
            status_code=500,
            cached=False,
            extra={"error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and index document: {str(exc)}",
        )


@app.get("/logs", tags=["Observability"])
def get_recent_logs(limit: int = 50) -> Dict[str, Any]:
    """Retrieves recent structured logs for operational monitoring."""
    entries = read_logs(limit=limit)
    return {
        "count": len(entries),
        "limit": limit,
        "logs": entries,
        "zero_unmasked_pii": verify_no_unmasked_phone_pii(),
    }


@app.get("/cache/stats", tags=["Observability"])
def get_cache_statistics() -> Dict[str, Any]:
    """Retrieves runtime statistics for the normalized response cache."""
    return GLOBAL_RESPONSE_CACHE.stats()


@app.post("/cache/clear", tags=["Administration"])
def clear_response_cache() -> Dict[str, Any]:
    """Clears the normalized in-memory response cache."""
    GLOBAL_RESPONSE_CACHE.clear()
    return {"status": "success", "message": "Normalized response cache cleared successfully."}

