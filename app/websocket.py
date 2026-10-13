"""
WebSocket Real-Time Chat Handler for Naukri.com Domain Support Agent.
Track: Recruitment & HR Operations.

Task 11 Requirements:
- WS /ws/chat: Real-time bidirectional streaming session.
- Implements try...except WebSocketDisconnect: block to ensure disconnections
  don't disrupt the server runtime or crash the active process.
- Streaming responses with trace attribution, PII redaction, and session memory support.
"""

import asyncio
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from guardrails.pii_masker import mask_pii
from guardrails.injection_detector import detect_prompt_injection, INJECTION_REFUSAL_MESSAGE
from memory.session_memory import GLOBAL_SESSION_MANAGER
from crew.recruitment_crew import run_recruitment_crew, classify_query_intent
from schemas.response_models import SupportAgentResponse, create_support_agent_response
from observability.logger import log_request

logger = logging.getLogger("app.websocket")
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket client connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def send_json_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        await websocket.send_json(message)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket) -> None:
    """
    Bidirectional streaming chat endpoint (/ws/chat).
    
    Resilience Guarantee:
    Implements a strict try...except WebSocketDisconnect block to cleanly
    absorb connection drops without leaking coroutines or crashing the server.
    """
    await manager.connect(websocket)
    trace_id = str(uuid.uuid4())
    logger.info(f"WebSocket client connected. Initial trace_id: {trace_id}")

    try:
        while True:
            # Await client payload
            raw_data = await websocket.receive_text()
            start_time = time.perf_counter()
            current_trace = str(uuid.uuid4())

            # Parse input payload (accepts raw string or JSON dict)
            query = ""
            session_id: Optional[str] = None

            try:
                payload = json.loads(raw_data)
                if isinstance(payload, dict):
                    query = payload.get("query", "").strip()
                    session_id = payload.get("session_id")
                else:
                    query = str(payload).strip()
            except (json.JSONDecodeError, TypeError):
                query = raw_data.strip()

            if not query:
                await websocket.send_json({
                    "event": "error",
                    "status_code": 400,
                    "message": "Query cannot be empty.",
                })
                continue

            # Governance Constraint: Max 1,000 character limit (HTTP 413 equivalent)
            if len(query) > config.MAX_QUERY_CHARACTER_LIMIT:
                latency_ms = (time.perf_counter() - start_time) * 1000
                log_request(
                    trace_id=current_trace,
                    endpoint="/ws/chat",
                    latency_ms=latency_ms,
                    query=query[:200] + "... [OVERSIZED]",
                    status_code=413,
                    cached=False,
                )
                await websocket.send_json({
                    "event": "error",
                    "status_code": 413,
                    "message": f"Query length ({len(query)}) exceeds maximum limit of {config.MAX_QUERY_CHARACTER_LIMIT} characters.",
                })
                continue

            # Notify client that processing has begun
            await websocket.send_json({
                "event": "start",
                "trace_id": current_trace,
                "session_id": session_id,
            })

            # Check prompt injection
            is_injection, matched_pattern = detect_prompt_injection(query)
            if is_injection:
                latency_ms = (time.perf_counter() - start_time) * 1000
                log_request(
                    trace_id=current_trace,
                    endpoint="/ws/chat",
                    latency_ms=latency_ms,
                    query=query,
                    status_code=200,
                    cached=False,
                    extra={"injection_pattern": matched_pattern},
                )
                refusal_resp = create_support_agent_response(
                    query=query,
                    final_answer=INJECTION_REFUSAL_MESSAGE,
                    intent="out_of_scope",
                    sources=[],
                    escalation_recommended=False,
                    review_status="refused",
                    trace_id=current_trace,
                )
                await websocket.send_json({
                    "event": "chunk",
                    "chunk": INJECTION_REFUSAL_MESSAGE,
                })
                await websocket.send_json({
                    "event": "complete",
                    "response": refusal_resp.model_dump(),
                })
                continue

            # Multi-turn session memory resolution
            effective_query = query
            if session_id:
                resolved_q, rec_id, needs_clarification = GLOBAL_SESSION_MANAGER.resolve_coreference(session_id, query)
                if needs_clarification:
                    clarification = (
                        "I don't have context on which application you are referring to. "
                        "Please provide the specific application ID (e.g., APP-1001)."
                    )
                    GLOBAL_SESSION_MANAGER.add_user_turn(session_id, query)
                    GLOBAL_SESSION_MANAGER.add_ai_turn(session_id, clarification)
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    log_request(
                        trace_id=current_trace,
                        endpoint="/ws/chat",
                        latency_ms=latency_ms,
                        query=query,
                        status_code=200,
                        cached=False,
                    )
                    resp_clarify = create_support_agent_response(
                        query=query,
                        final_answer=clarification,
                        intent="status_lookup",
                        sources=[],
                        escalation_recommended=False,
                        review_status="approved",
                        trace_id=current_trace,
                    )
                    await websocket.send_json({
                        "event": "chunk",
                        "chunk": clarification,
                    })
                    await websocket.send_json({
                        "event": "complete",
                        "response": resp_clarify.model_dump(),
                    })
                    continue
                effective_query = resolved_q

            # Run multi-agent crew execution
            response_obj = run_recruitment_crew(effective_query, verbose=False)
            response_obj.trace_id = current_trace
            response_obj.query = query

            if session_id:
                GLOBAL_SESSION_MANAGER.add_user_turn(session_id, query)
                GLOBAL_SESSION_MANAGER.add_ai_turn(session_id, response_obj.final_answer)

            # Stream words/chunks to emulate real-time generation
            words = response_obj.final_answer.split(" ")
            chunk_size = 5
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size]) + " "
                await websocket.send_json({
                    "event": "chunk",
                    "chunk": chunk,
                })
                await asyncio.sleep(0.01)

            latency_ms = (time.perf_counter() - start_time) * 1000
            log_request(
                trace_id=current_trace,
                endpoint="/ws/chat",
                latency_ms=latency_ms,
                query=query,
                status_code=200,
                cached=False,
            )

            # Emit completion event with validated structured model
            await websocket.send_json({
                "event": "complete",
                "response": response_obj.model_dump(),
            })

    except WebSocketDisconnect:
        # Task 11 Defense: Cleanly handle abrupt disconnects without crashing the server
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected cleanly (trace: {trace_id}). Server loop unaffected.")
    except Exception as exc:
        manager.disconnect(websocket)
        logger.error(f"Unexpected WebSocket error: {exc}", exc_info=True)
