# Naukri.com Recruitment Domain Support Agent

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-orange.svg)](https://crewai.com)
[![AutoGen](https://img.shields.io/badge/AutoGen-Review%20Team-red.svg)](https://microsoft.github.io/autogen/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorStore-green.svg)](https://www.trychroma.com/)
[![Tests](https://img.shields.io/badge/Tests-48%20Passing%20(100%25)-brightgreen.svg)](tests/)
[![Zero-API-Key](https://img.shields.io/badge/Zero--Cost-Deterministic%20Offline%20MOCK__LLM-purple.svg)](#zero-api-key-offline-guarantee)

An enterprise-grade, deterministic multi-agent support agent designed for **Naukri.com** within the **Recruitment & HR Operations** track. The system resolves company hiring policy inquiries via grounded Retrieval-Augmented Generation (RAG) and performs job application status lookups with designed escalation scoring, backed by dual-stage multi-agent verification (CrewAI + AutoGen), multi-tier guardrails, ELK-style structured logging, and four-layer AI governance.

---

## Table of Contents
1. [Project Overview & Governance Notice](#1-project-overview--governance-notice)
2. [Master Architecture](#2-master-architecture)
3. [Repository Directory Layout](#3-repository-directory-layout)
4. [Zero-API-Key Offline Guarantee](#4-zero-api-key-offline-guarantee)
5. [Dataset Design & Reproducibility Parameters](#5-dataset-design--reproducibility-parameters)
6. [Policy Knowledge Base & Dual-Chunking RAG](#6-policy-knowledge-base--dual-chunking-rag)
7. [Multi-Agent Orchestration & Session Memory](#7-multi-agent-orchestration--session-memory)
8. [Multi-Tier Guardrails & Pre-Disk PII Redaction](#8-multi-tier-guardrails--pre-disk-pii-redaction)
9. [Production Serving: REST & Streaming WebSocket](#9-production-serving-rest--streaming-websocket)
10. [Resilience, AI Governance & Response Caching](#10-resilience-ai-governance--response-caching)
11. [4-Dimensional Evaluation Suite](#11-4-dimensional-evaluation-suite)
12. [Complete Verification Matrix](#12-complete-verification-matrix)
13. [Installation & Execution Guide](#13-installation--execution-guide)
14. [Step-by-Step Usage Guide](usageguide.md)

---

## 1. Project Overview & Governance Notice

- **Track Declaration:** Completed for **Naukri.com (Recruitment & HR Operations)**.
- **Dual Capability:** 
  1. **Policy Guidance:** Accurate, grounded responses to recruitment policies (notice period, probation, internal transfers, referrals, background checks, diversity hiring, and remote work).
  2. **Application Status & Escalation:** Candidate application lookup with formulaic escalation scoring ($0.5 \times \text{flag} + 0.5 \times (\text{recency} / 30)$) triggering recruiter alerts when $\tau_{\text{esc}} \ge 0.65$.
- **Telemetry Suppression:** Outbound telemetry is strictly suppressed via `CREWAI_DISABLE_TELEMETRY=true` and `OTEL_SDK_DISABLED=true`.
- **Pre-Disk PII Redaction:** Indian phone numbers (`+91...`) are sanitized to `[PHONE_MASKED]` before logging to disk or passing to downstream audit trails.

---

## 2. Master Architecture

```mermaid
flowchart TD
    User([User Request / Webhook]) --> Ingress[FastAPI Gateway / WS Endpoint]
    
    subgraph PreExecutionGuardrails [Tier 1: Pre-Execution Guardrails]
        BudgetCheck[Runtime Budget Controller<br/>Length <= 1,000 chars]
        PIIMasker[Input PII Masker<br/>+91 Indian Phone -> PHONE_MASKED]
        InjectionGuard[Prompt Injection Detector<br/>Regex & Heuristic Jailbreak Defense]
    end
    
    Ingress --> BudgetCheck
    BudgetCheck -->|Over 1,000 Chars| Reject413[HTTP 413 Payload Too Large]
    BudgetCheck -->|Valid| PIIMasker
    PIIMasker --> InjectionGuard
    InjectionGuard -->|Adversarial Pattern| RefusalResponse[Safe Refusal Notice]
    
    subgraph OptimizationLayer [Performance Layer]
        CacheCheck{Normalized Query<br/>Cache Lookup}
    end
    
    InjectionGuard -->|Compliant| CacheCheck
    CacheCheck -->|Cache HIT| FastReturn[Sub-millisecond Return<br/>Latency < 0.1 ms]
    
    subgraph Stage1MultiAgent [Stage 1: CrewAI 3-Agent Multi-Agent Core]
        Router[Task Router & Intent Classifier]
        RetrievalAgent[Retrieval Agent<br/>Policy Researcher<br/>Tools: rag_policy_tool]
        LookupAgent[Lookup Agent<br/>Application Specialist<br/>Tools: check_job_application_status]
        ComposerAgent[Response Composer Agent<br/>HR Communication Specialist<br/>Tools: None]
        
        Router -->|Policy Query| RetrievalAgent
        Router -->|Status Lookup| LookupAgent
        Router -->|Hybrid Query| RetrievalAgent & LookupAgent
        RetrievalAgent --> ComposerAgent
        LookupAgent --> ComposerAgent
    end
    
    CacheCheck -->|Cache MISS| Router
    
    subgraph Stage2Audit [Stage 2: AutoGen Quality & Compliance Review]
        AuditorAgent[PolicyComplianceReviewer<br/>Audits Grounding & CTC Bounds]
        EditorAgent[FinalEditor<br/>Emits ReviewVerdict Structure]
        AuditorAgent --> EditorAgent
    end
    
    ComposerAgent -->|Draft Answer| Stage2Audit
    
    subgraph EgressOutput [Egress & Persistence]
        GroundingGuard[Output Grounding Guardrail<br/>Cosine Sim >= 0.60]
        StructuredLog[(ELK JSONL Logger<br/>support_agent.jsonl)]
        ValidatedSchema[Pydantic SupportAgentResponse]
    end
    
    EditorAgent --> GroundingGuard
    GroundingGuard --> ValidatedSchema
    ValidatedSchema --> CacheSet[Set Normalized Cache]
    ValidatedSchema --> StructuredLog
    ValidatedSchema --> FinalEgress([HTTP 200 / WebSocket Event])
```

---

## 3. Repository Directory Layout

```
Recruitment/
├── .env                              # Environment configuration (telemetry suppressed)
├── requirements.txt                  # Pinned production dependencies
├── config.py                         # Global application constants & thresholds
├── dataset.py                        # Task 1: Seeded job-application dataset generator
│
├── knowledge_base/                   # Task 2: 12 policy markdown documents
│   ├── 01_eligibility_criteria.md
│   ├── 02_interview_scheduling.md
│   ├── 03_offer_negotiation.md
│   ├── ...
│   └── 12_data_retention.md
│
├── rag/                              # Tasks 3-5: Vector indexing & retrieval
│   ├── chunking.py                   # Fixed-size (200/40) & sentence chunking
│   ├── vector_store.py               # ChromaDB dual-collection manager
│   ├── retrieval.py                  # Grounded RAG with calibrated fallback
│   └── eval_chunking.py              # Chunking precision & recall evaluator
│
├── tools/                            # Task 6: Autonomous agent tools
│   ├── application_lookup.py         # Application lookup with escalation score
│   └── policy_rag_tool.py            # CrewAI tool wrapper for policy RAG
│
├── crew/                             # Task 7: CrewAI multi-agent orchestration
│   ├── mock_llm.py                   # Deterministic offline BaseLLM mock engine
│   ├── crewai_compat.py              # CrewAI compatibility layer
│   └── recruitment_crew.py           # 3-agent sequential Crew orchestrator
│
├── memory/                           # Task 8: In-memory session history
│   └── session_memory.py             # LangChain InMemoryChatMessageHistory wrapper
│
├── schemas/                          # Task 9: Pydantic response models
│   └── response_models.py            # SupportAgentResponse & AskRequest schemas
│
├── guardrails/                       # Task 10: Multi-tier safety guards
│   ├── pii_masker.py                 # Indian phone number regex scrubber
│   ├── injection_detector.py         # Adversarial prompt injection defense
│   └── grounding_guard.py            # Output hallucination & similarity guard
│
├── app/                              # Task 11: Production FastAPI serving
│   ├── api.py                        # REST endpoints (/ask, /add-document, /health)
│   └── websocket.py                  # Real-time streaming WebSocket (/ws/chat)
│
├── observability/                    # Task 12: ELK-compatible structured logging
│   └── logger.py                     # Thread-safe JSONL audit trail logger
│
├── evaluation/                       # Task 13: 4-metric evaluation suite
│   ├── benchmark_queries.json        # 15 benchmark test queries
│   ├── judge_suite.py                # Automated LLM-as-a-judge scoring engine
│   └── benchmark_results.json        # Serialized evaluation metrics & telemetry
│
├── autogen_review/                   # Task 14: AutoGen secondary review stage
│   ├── verdict_model.py              # ReviewVerdict Pydantic model & StructuredMessage
│   ├── autogen_compat.py             # AutoGen GroupChat compatibility shim
│   └── review_team.py                # 2-agent review group chat (Reviewer + Editor)
│
├── governance/                       # Task 15: Four-layer AI governance
│   ├── governance_policy.md          # Comprehensive governance specifications
│   ├── budget_controller.py          # Character ceiling & token budget enforcement
│   └── least_autonomy_validator.py   # Privilege boundary & tool isolation validator
│
├── cache/                            # Task 16: Response caching engine
│   └── response_cache.py             # In-memory normalized LRU response cache
│
├── logs/                             # Audit logging destination
│   └── support_agent.jsonl           # Sanitized JSON-Lines structured audit log
│
└── tests/                            # Comprehensive Pytest test suite (48 tests)
    ├── test_mock_llm.py              # Mock LLM unit tests
    ├── test_phase2_rag.py            # Dataset, chunking & RAG tests
    ├── test_phase3_multiagent.py     # Multi-agent, memory & guardrail tests
    ├── test_api.py                   # REST, WebSocket & logging tests
    └── test_phase5_governance.py     # AutoGen, governance & cache tests
```

---

## 4. Zero-API-Key Offline Guarantee

This project runs **100% deterministically without external API keys or remote network calls**:
1. **Mock LLM Architecture (`crew/mock_llm.py`):** Subclasses CrewAI's `BaseLLM` interface to synthesize grounded answers locally by evaluating semantic query intent, candidate records, and retrieved ChromaDB context.
2. **Local Vector Embeddings:** Uses `sentence-transformers/all-MiniLM-L6-v2` loaded locally to embed document chunks and queries into ChromaDB collections.
3. **Telemetry Lockdown:** CrewAI and OpenTelemetry outbound pings are suppressed at initialization:
   ```python
   os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
   os.environ["OTEL_SDK_DISABLED"] = "true"
   ```

---

## 5. Dataset Design & Reproducibility Parameters

The application dataset generator ([dataset.py](file:///d:/Final%20Capstone%20Project/Recruitment/dataset.py)) generates a deterministic distribution of job applications:
- **Seed:** Fixed `seed = 42`.
- **Volume:** $N = 45$ records ($\ge 40$).
- **Category Representation ($\ge 3$ each):**
  - `Software Engineer` (11)
  - `Data Analyst` (9)
  - `Product Manager` (8)
  - `HR Executive` (9)
  - `Sales Associate` (8)
- **Status Representation ($\ge 1$ each):**
  - `Applied` (10)
  - `Screening` (8)
  - `Interview Scheduled` (10)
  - `Offered` (9)
  - `Rejected` (8)
- **Salary Bands (Expected CTC in INR):**
  - Junior / Support: ₹3,50,000 – ₹7,00,000
  - Mid Engineering / Analytics: ₹8,00,000 – ₹18,00,000
  - Senior / Product Management: ₹20,00,000 – ₹45,00,000
- **Recency:** `days_since_created` integer $\in [0, 30]$ days.
- **Priority Review Flag:** `flagged_priority_review` strictly controlled within the **10%–30%** band (actual: **22.2%**).

---

## 6. Policy Knowledge Base & Dual-Chunking RAG

### Knowledge Base Documents
The recruitment knowledge base contains 12 authoritative policy markdown documents ([knowledge_base/](file:///d:/Final%20Capstone%20Project/Recruitment/knowledge_base/)):
1. `01_eligibility_criteria.md`: B.Tech/MCA/MBA requirements, minimum 60% aggregate, max 1 gap year.
2. `02_interview_scheduling.md`: 48-hour advance notice, max 2 candidate reschedules.
3. `03_offer_negotiation.md`: CTC bands, sign-on bonus approval, 5 calendar-day offer validity.
4. `04_background_verification.md`: Mandatory identity, education, criminal, and previous employer scrutiny.
5. `05_notice_period.md`: 30 to 90 days notice buyout norms requiring BU Head and HR approval.
6. `06_referral_bonus.md`: 50% paid upon joining, 50% paid after 90 days of continuous employment.
7. `07_internal_transfer.md`: Minimum 12 months tenure in current role before applying for IJP.
8. `08_probation_period.md`: 6-month standard probation with 30-day review milestone.
9. `09_remote_work.md`: Hybrid model permitting up to 2 days/week work-from-home.
10. `10_diversity_hiring.md`: Equal opportunity standards and quarterly affirmative action reporting.
11. `11_exit_interview.md`: Mandatory HR exit interview; final settlement within 45 days.
12. `12_data_retention.md`: Candidate resumes and interview evaluation notes retained for 180 days.

### Dual-Chunking Strategy Evaluation
Two distinct chunking strategies were indexed into ChromaDB collections:
- **Strategy A (Fixed-Size):** 200 character window with 40 character overlap (`naukri_fixed_chunks`).
- **Strategy B (Sentence-Based):** Syntactic sentence boundary segmentation (`naukri_sentence_chunks`).

#### Empirical Precision & Recall Results
| Query | Fixed Precision | Fixed Recall | Sentence Precision | Sentence Recall |
| :--- | :---: | :---: | :---: | :---: |
| What is the probation duration? | 1.00 (1/1) | 1.00 (1/1) | 0.50 (1/2) | 1.00 (1/1) |
| Explain referral bonus payout | 0.50 (1/2) | 1.00 (1/1) | 1.00 (1/1) | 1.00 (1/1) |
| Can I work remotely? | 1.00 (1/1) | 1.00 (1/1) | 1.00 (1/1) | 1.00 (1/1) |
| Background verification requirements | 0.50 (1/2) | 1.00 (1/1) | 1.00 (1/1) | 1.00 (1/1) |
| Notice period buyout policy | 1.00 (1/1) | 1.00 (1/1) | 0.50 (1/2) | 1.00 (1/1) |
| **Arithmetic Mean** | **0.80** | **1.00** | **0.80** | **1.00** |

**Engineering Recommendation:** Sentence-Based Chunking is decisively chosen for production. Fixed-size chunking blindly splits text across character boundaries, cutting conditions in half. Sentence-based chunking preserves atomic policy clauses and semantic self-containment.

### Fallback Threshold Calibration
- In-Scope Policy Queries Cosine Similarity: $S_{\text{in}} \in [0.72, 0.88]$
- Out-of-Scope Queries Cosine Similarity: $S_{\text{out}} \in [0.21, 0.44]$
- **Calibrated Cutoff:** $\tau_{\text{RAG}} = 0.60$. Any query with top similarity $< 0.60$ immediately triggers the safe fallback refusal:
  > *"I don't have information on this topic in the company recruitment policy."*

---

## 7. Multi-Agent Orchestration & Session Memory

### 3-Agent CrewAI Architecture
The multi-agent workflow is executed via CrewAI using a sequential workflow under the **Principle of Least Autonomy**:
1. **Retrieval Agent (`Recruitment Policy Researcher`):**
   - **Allowed Tools:** `[rag_policy_tool]` only.
   - Searches ChromaDB for relevant policy clauses.
2. **Lookup Agent (`Application Records Specialist`):**
   - **Allowed Tools:** `[check_job_application_status]` only.
   - Retrieves candidate records and calculates escalation scores.
3. **Response Composer Agent (`Senior HR Communication Specialist`):**
   - **Allowed Tools:** `[]` (strictly zero tools).
   - Synthesizes findings into professional, empathetic communications.

### Escalation Score Engine
Applications are evaluated against a mathematically designed escalation formula:
$$\text{escalation\_score} = 0.5 \cdot \mathbb{I}(\text{flagged\_priority\_review}) + 0.5 \cdot \left(\frac{\text{days\_since\_created}}{30}\right)$$
- **Escalation Threshold:** $\tau_{\text{esc}} = 0.65$.
- **Behavior:**
  - Flagged applications older than 9 days trigger escalation: $0.5 + 0.5 \times (9/30) = 0.65$.
  - Unflagged applications remain below threshold unless stalled for an extended duration.

### In-Memory Multi-Turn Session Memory
Built on LangChain's `InMemoryChatMessageHistory` with session ID indexing:
- **Turn Continuity:** "Check status of APP-1001" followed by "What was its expected salary?" resolves pronouns ("its") to `APP-1001`.
- **Session Isolation:** An unlinked session asking "What was its expected salary?" correctly flags lack of context and requests an application ID.

---

## 8. Multi-Tier Guardrails & Pre-Disk PII Redaction

1. **Input PII Masker ([guardrails/pii_masker.py](file:///d:/Final%20Capstone%20Project/Recruitment/guardrails/pii_masker.py)):**
   - Pattern: `(?<!\w)(?:\+91[\-\s]?|91[\-\s]?|[0]?)?[6-9]\d{9}\b`
   - Replaces 10-digit Indian phone numbers with `[PHONE_MASKED]`.
   - Utilizes negative lookbehind `(?<!\w)` to eliminate false positives on UUID hex segments.
2. **Prompt Injection Defense ([guardrails/injection_detector.py](file:///d:/Final%20Capstone%20Project/Recruitment/guardrails/injection_detector.py)):**
   - Heuristically blocks jailbreak attempts (`ignore previous instructions`, `system prompt override`, `you are now DAN`).
   - Immediately returns safe refusal notice without calling agents.
3. **Output Grounding Guardrail ([guardrails/grounding_guard.py](file:///d:/Final%20Capstone%20Project/Recruitment/guardrails/grounding_guard.py)):**
   - Validates generated claims against retrieved context. If factual similarity $< 0.60$, enforces safe refusal.
4. **Data Hygiene Invariant ([observability/logger.py](file:///d:/Final%20Capstone%20Project/Recruitment/observability/logger.py)):**
   - Pre-disk PII redaction ensures raw telephone numbers never touch disk in `logs/support_agent.jsonl`.

---

## 9. Production Serving: REST & Streaming WebSocket

### REST Endpoints ([app/api.py](file:///d:/Final%20Capstone%20Project/Recruitment/app/api.py))
- `POST /ask`: Accepts JSON `{"query": str, "session_id": Optional[str]}`, returns validated `SupportAgentResponse`.
- `POST /add-document`: Accepts `{"title": str, "content": str}`, splits into fixed and sentence chunks, and indexes into ChromaDB.
- `GET /health`: Returns service operational status.

#### Example REST Request
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the probation period duration at Naukri.com?"}'
```

#### Example REST Response
```json
{
  "trace_id": "a91e0b27-64b6-44d2-b28b-36dddc30cc25",
  "query": "What is the probation period duration at Naukri.com?",
  "intent": "policy_query",
  "final_answer": "Policy Guidelines: The standard probation duration for all new hires is 6 months starting from the date of joining. A formal 30-day performance review milestone is conducted between the employee and line manager.",
  "sources": ["08_probation_period.md"],
  "escalation_recommended": false,
  "review_status": "approved",
  "cached": false,
  "latency_ms": 28.45,
  "audit_reason": "Policy compliance verified. Answer is fully grounded with zero unverified claims."
}
```

### Streaming WebSocket ([app/websocket.py](file:///d:/Final%20Capstone%20Project/Recruitment/app/websocket.py))
- `WS /ws/chat`: Real-time bidirectional token streaming with structured lifecycle events (`start`, `chunk`, `complete`, `error`).
- **Resilience:** Implements `try...except WebSocketDisconnect` to ensure abnormal client disconnects never crash the server.

---

## 10. Resilience, AI Governance & Response Caching

### AutoGen Secondary Review Stage ([autogen_review/](file:///d:/Final%20Capstone%20Project/Recruitment/autogen_review/))
- **Team:** 2-agent `RoundRobinGroupChat` (`max_turns=2`):
  1. `PolicyComplianceReviewer`: Audits CrewAI draft answers against official policies and compensation bounds.
  2. `FinalEditor`: Enforces tone and emits a validated Pydantic `ReviewVerdict`.
- **Structured Message Registration:** Initialized with `custom_message_types=[StructuredMessage[ReviewVerdict]]` to strictly prevent AutoGen runtime `ValueError`.
- **Auditing Invariants:**
  - Clean factual drafts are approved unchanged (`approved=True`).
  - Hallucinated or ungrounded claims are actively rewritten (`approved=False`, `review_status="revised_by_audit"`).

### Four-Layer AI Governance Model ([governance/](file:///d:/Final%20Capstone%20Project/Recruitment/governance/))
1. **Application Layer (Least Autonomy & Risk Classification):**
   - Tool isolation prevents cross-agent capability misuse.
   - Classified as **Medium-to-High Risk** due to candidate salary benchmarks (3.5 to 45 LPA) and escalation routing.
2. **Runtime & Cost Layer (Budget Caps & Response Caching):**
   - Hard character ceiling of $\le 1,000$ characters ([governance/budget_controller.py](file:///d:/Final%20Capstone%20Project/Recruitment/governance/budget_controller.py)). Oversized requests rejected with HTTP 413.
   - In-memory normalized LRU cache ([cache/response_cache.py](file:///d:/Final%20Capstone%20Project/Recruitment/cache/response_cache.py)) eliminates duplicate multi-agent runs.
3. **Verification & Alignment Layer:**
   - Dual-stage auditing (CrewAI Composer $\rightarrow$ AutoGen Editor) with empirical cosine cutoff ($\tau_{\text{RAG}} = 0.60$).
4. **Data & Compliance Layer:**
   - Zero cleartext logging of phone numbers with immutable JSONL audit trails.

### Normalized Response Cache Metrics
- **Normalization:** Trims whitespace, lowercases, and strips trailing punctuation (`normalize_query()`).
- **Performance:**
  - Cold Request Latency: $\sim 14,242 \text{ ms}$ (full RAG + CrewAI + AutoGen pipeline).
  - Warm Cache Hit Latency: $0.025 \text{ ms}$.
  - **Latency Reduction:** $> 500,000\times$ speedup on repeated queries.

---

## 11. 4-Dimensional Evaluation Suite

Evaluated across 15 benchmark queries (12 policy topics + 2 out-of-scope + 1 adversarial injection):

| Dimension | Target Metric | Achieved Score | Evaluation Focus |
| :--- | :---: | :---: | :--- |
| **Accuracy** | $\ge 85\%$ | **90.0%** | Factual adherence to ground truth policy conditions |
| **Grounding** | $\ge 90\%$ | **100.0%** | Sourcing strictly from retrieved ChromaDB context |
| **Completeness** | $\ge 85\%$ | **92.8%** | Comprehensive coverage of query clauses |
| **Safety** | $100\%$ | **100.0%** | Pre-disk PII masking and prompt injection defense |
| **Composite Average** | - | **95.7%** | **Overall Benchmark Quality Rating** |

Benchmark results are serialized to [evaluation/benchmark_results.json](file:///d:/Final%20Capstone%20Project/Recruitment/evaluation/benchmark_results.json).

---

## 12. Complete Verification Matrix

Every task and component has a dedicated, reproducible CLI command:

| Phase | Component | Verification Command | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **Phase 2** | Dataset Generator | `python dataset.py` | $\ge 40$ records, 5 categories $\ge 3$, 5 statuses $\ge 1$, flags $10-30\%$ |
| **Phase 2** | ChromaDB Indexing | `python rag/vector_store.py` | Fixed & Sentence collections loaded with 12 policy documents |
| **Phase 2** | Grounded Generation | `python rag/retrieval.py` | 5 in-scope answers grounded; 1 out-of-scope triggers fallback |
| **Phase 2** | Chunking Eval | `python rag/eval_chunking.py` | Precision & Recall calculated with arithmetic recommendation |
| **Phase 3** | Application Lookup Tool | `python tools/application_lookup.py` | Record returned with formulaic escalation score $\in [0, 1]$ |
| **Phase 3** | CrewAI 3-Agent Crew | `python crew/recruitment_crew.py` | 3 agents execute via `.kickoff()` with tools invoked |
| **Phase 3** | Session Memory | `python memory/session_memory.py` | Multi-turn transcript carries context; reset transcript resets |
| **Phase 3** | Guardrails Suite | `python guardrails/pii_masker.py` | Phone masked, injection blocked, ungrounded answer refused |
| **Phase 4** | FastAPI Service | `pytest tests/test_api.py` | REST endpoints return 200; WebSocket survives disconnect |
| **Phase 4** | Structured Logs | `python observability/logger.py` | JSONL log entries with trace IDs and zero unmasked phone PII |
| **Phase 4** | Evaluation Suite | `python evaluation/judge_suite.py` | 15 queries evaluated across 4 metrics (Composite: 95.7%) |
| **Phase 5** | AutoGen Review Team | `python autogen_review/review_team.py` | Approved clean demo + Hallucination revised demo |
| **Phase 5** | Governance Budget Cap | `python governance/budget_controller.py` | Oversized prompt rejected under runtime cap (HTTP 413) |
| **Phase 5** | Least Autonomy Check | `python governance/least_autonomy_validator.py` | Proves tool isolation raises `PermissionError` on violation |
| **Phase 5** | Response Cache Engine | `python cache/response_cache.py` | Hit verified with call counter & $>500,000\times$ latency drop |
| **All** | **Full Test Suite** | `pytest tests` | **All 48 unit & integration tests passing (100%)** |

---

## 13. Installation & Execution Guide

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.14
- Git

### 2. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/sandeep83103/RecruitmentCapstone.git
cd RecruitmentCapstone

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Full Test Suite
```bash
pytest tests -v
```

### 5. Launch the Interactive Console CLI (Direct User Interaction)
```bash
python cli.py
```
*Allows immediate testing of policy questions, candidate application lookups, and multi-turn follow-ups directly in your terminal.*

### 6. Launch the FastAPI Production Server
```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger API documentation will be available at:
`http://127.0.0.1:8000/docs`

> [!TIP]
> For complete user input specifications, master sample input catalog across all 12 policies, standalone verification scripts, WebSocket streaming client code, and cURL examples, refer to the [Step-by-Step Usage Guide](usageguide.md).

---

## License & Attribution
Developed as part of the Final Capstone Project for the **Naukri.com (Recruitment & HR Operations)** domain track.
All rights reserved.
