# Architectural & Engineering Decisions (ADR)
## Naukri.com Recruitment Domain Support Agent

> **PURPOSE & DIRECTIVE FOR AI ASSISTANTS:**
> This document records every non-obvious architectural, algorithmic, and framework design decision made across the repository.
> Each entry follows a strict two-line format: **(1) The non-obvious choice made over alternatives and why**, and **(2) The critical failure prevented, instructing future AI models not to undo this reasoning.**

---

### 1. Deterministic Foundation & Telemetry

**1. Mock LLM Subclassing vs. Litellm Proxies**
- We chose to subclass CrewAI's `BaseLLM` (`crewai.llms.base_llm.BaseLLM`) over mocking litellm endpoints or intercepting HTTP requests because CrewAI natively invokes `BaseLLM.call()` directly without external litellm dependencies.
- Undoing this by attempting to mock litellm causes silent crashes and introduces unwanted network socket initialization.

**2. Import-Time Telemetry Suppression vs. Runtime Main Flags**
- We chose to suppress telemetry (`CREWAI_DISABLE_TELEMETRY=true`, `OTEL_SDK_DISABLED=true`) at the very top of `config.py` rather than inside `main()` or CLI runners because CrewAI and OpenTelemetry spawn background exporter threads immediately upon module import.
- Undoing this by moving suppression flags into function bodies causes telemetry pings to leak before flags are applied.

**3. Output Parsing vs. Raw System Prompt Inspection**
- We chose to parse only the model-generated response buffer rather than searching the full conversation prompt for `"Observation:"` because CrewAI's built-in ReAct template literally contains the text `"Observation: the result of the action"`.
- Undoing this causes the parser to match system instructions on turn 1 and return placeholder template text as the final answer.

---

### 2. Multi-Agent Orchestration & Governance

**4. Argument-Schema Tool Dispatch vs. Name Substring Matching**
- We chose to dispatch tools based on declared Pydantic schemas (`"record_id" in tool.args`) or strict string equality rather than checking substrings like `"lookup" in tool.name` because tools named `rag_lookup` were otherwise misclassified as candidate application lookups.
- Undoing this by reintroducing substring matching silently routes recruitment policy questions to the database tool.

**5. Strict Least Autonomy Tool Isolation vs. Shared Tool Lists**
- We chose to bind `check_job_application_status` solely to `LookupAgent` and forbid all tools on `ComposerAgent` because separating database privileges prevents prompt-injected policy inquiries from extracting candidate records.
- Undoing this by giving tools to the Composer or Retrieval agent violates the four-layer AI governance model and raises `PermissionError`.

**6. Medium-to-High Risk Classification vs. Low-Risk Tier**
- We chose to classify the system as `"Medium-to-High Risk"` rather than `"Low Risk"` because it retrieves candidate compensation details and provides binding employment policy answers influencing hiring and separation outcomes.
- Undoing this by downgrading to low risk undermines compliance with enterprise HR governance standards.

---

### 3. RAG, Embeddings & Vector Search

**7. Local SentenceTransformers vs. External Cloud Embeddings**
- We chose `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors) over OpenAI or Cohere APIs because it runs locally on CPU with zero cost, zero API keys, and 100% offline reproducibility.
- Undoing this by integrating cloud embeddings breaks the mandatory zero-network offline capstone requirement.

**8. Sentence-Based Chunking vs. Fixed-Size Chunking**
- We chose sentence-based chunking over fixed-size chunking (200 characters / 40 overlap) for production RAG because it preserves natural grammatical clauses, achieving superior retrieval precision (0.933 vs. 0.733).
- Undoing this by reverting to fixed-size chunks cuts policy rules mid-sentence and degrades answer completeness.

**9. Empirical Cosine Calibration (0.60) vs. Tutorial Defaults (0.50/0.70)**
- We chose an empirical similarity threshold of $\tau_{\text{RAG}} = 0.60$ over arbitrary presets (0.50 or 0.70) because measured in-scope queries cluster at 0.68–0.88 while out-of-scope queries cluster at 0.38–0.54.
- Undoing this by adopting generic presets either causes false-positive hallucinations on recipes/stocks (at 0.50) or falsely rejects legitimate policy queries (at 0.70).

---

### 4. Mathematical Logic & Data Engineering

**10. Continuous Escalation Formula vs. Bare Boolean OR**
- We chose the formula $\text{score} = 0.5 \times \text{flag} + 0.5 \times (\text{days} / 30)$ with threshold $\tau_{\text{esc}} = 0.65$ over a bare boolean OR (`flag or days > 15`) because priority applications must stall for at least 9 days before triggering human recruiter escalation.
- Undoing this by writing simple OR logic causes freshly submitted priority applications (Day 0) to prematurely escalate.

**11. Seed-Based Dataset Regeneration vs. Manual Record Editing**
- We chose to tune generator weights and seeds (`seed=42`) in `dataset.py` over manually editing rows in `job_applications.json` because manual edits violate reproducibility standards.
- Undoing this by hardcoding or hand-editing records breaks deterministic evaluation verification across different environments.

---

### 5. Guardrails, Memory & Security

**12. Fixed-Format Phone Masking vs. Free-Text NER Masking**
- We chose to mask only Indian phone numbers (`+91...`, `0...`, 10-digit) to `[PHONE_MASKED]` while treating names and salaries as fabricated examples because phone numbers have deterministic regex patterns that execute safely without cloud NER APIs.
- Undoing this by attempting ungrounded free-text name masking under `MOCK_LLM` produces frequent false positives on job titles and policies.

**13. In-Logger Pre-Disk Scrubbing vs. Gateway-Only Filtering**
- We chose to hook PII masking directly inside `observability/logger.py` rather than relying solely on API gateway middleware because error traces, internal agent logs, and WebSocket messages would otherwise bypass gateway filters and write cleartext PII to disk.
- Undoing this by removing logger-level scrubbing allows unmasked candidate contact numbers to leak into persistent JSON-Lines audit logs.

**14. Session-Scoped In-Memory History vs. Database Persistence**
- We chose LangChain's in-memory session history (`InMemoryChatMessageHistory`) over persistent databases (Redis / SQLite) because multi-turn state only needs to survive within active user dialogue turns per task specification.
- Undoing this by requiring external database services introduces unnecessary operational infrastructure and breaks the standalone deployment guarantee.

---

### 6. Secondary Review & AutoGen Integration

**15. `RoundRobinGroupChat(max_turns=2)` vs. `MaxMessageTermination(2)`**
- We chose `RoundRobinGroupChat(max_turns=2)` over `MaxMessageTermination(2)` or non-existent `max_iterations` because AutoGen counts the initiating task prompt as message 1, causing `MaxMessageTermination(2)` to terminate after only a single agent speaks.
- Undoing this by setting termination to 2 prevents the `FinalEditor` agent from ever executing its compliance review turn.

**16. Explicit Custom Message Type Registration vs. Standard Envelopes**
- We chose to pass `custom_message_types=[StructuredMessage[ReviewVerdict]]` during AutoGen team construction because AutoGen v0.2+ crashes with `ValueError: Message type not registered` if an agent outputs a typed Pydantic contract not declared on the team.
- Undoing this by omitting `custom_message_types` crashes the secondary review stage immediately upon editor output.

---

### 7. Production Serving, Caching & Resilience

**17. Ingress Character Ceiling (1,000 chars) vs. LLM Token Truncation**
- We chose to reject queries exceeding 1,000 characters with `HTTP 413` at the FastAPI ingress layer rather than truncating tokens downstream because it intercepts DoS payloads before allocating memory for dense embeddings or agent threads.
- Undoing this by moving length validation into the LLM allows oversized payloads to consume expensive vector compute and memory.

**18. Graceful `WebSocketDisconnect` Handling vs. Exception Propagation**
- We chose to wrap the WebSocket event loop in an explicit `try...except WebSocketDisconnect` handler because browser tab closures are expected client events that would otherwise crash ASGI worker threads.
- Undoing this by allowing disconnect exceptions to bubble up pollutes server logs and terminates connection teardown handlers.

**19. Normalized Query Caching vs. Semantic Embedding Cache**
- We chose canonical string normalization (lowercase, trim whitespace, strip terminal punctuation) over semantic embedding vector caching because it delivers deterministic $O(1)$ sub-millisecond retrieval without false-positive semantic drift.
- Undoing this by using raw query strings causes redundant LLM executions on identical questions with trailing punctuation or spacing differences.

**20. Unified `SupportAgentResponse` Contract vs. Endpoint-Specific Models**
- We chose a single unified Pydantic schema with typed `Literal` intents and `trace_id` for both REST and WebSocket endpoints over disparate response models because a shared contract simplifies client integrations and guarantees end-to-end trace attribution.
- Undoing this by returning free-form dictionaries or multiple schemas breaks frontend contracts and WebSocket deserialization.
