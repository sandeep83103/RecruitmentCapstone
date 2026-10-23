# Naukri.com Recruitment Domain Support Agent — Step-by-Step Usage Guide

This guide provides end-to-end instructions for installing, configuring, executing, and interacting with the **Naukri.com Recruitment Domain Support Agent** across all standalone modules, multi-agent pipelines, FastAPI endpoints, WebSocket streaming, and automated evaluation suites.

---

## Table of Contents
1. [Prerequisites & System Requirements](#1-prerequisites--system-requirements)
2. [Environment Setup & Installation](#2-environment-setup--installation)
3. [Running the Automated Test Suite (All 48 Tests)](#3-running-the-automated-test-suite-all-48-tests)
4. [Running the FastAPI Production Web Server](#4-running-the-fastapi-production-web-server)
5. [Interacting with the REST API (curl & Python)](#5-interacting-with-the-rest-api-curl--python)
6. [Interacting with the Streaming WebSocket API](#6-interacting-with-the-streaming-websocket-api)
7. [Running Standalone Verification Demos (Phase-by-Phase)](#7-running-standalone-verification-demos-phase-by-phase)
   - [Phase 2: Dataset, Indexing & RAG Core](#phase-2-dataset-indexing--rag-core)
   - [Phase 3: Multi-Agent Crew, Memory & Guardrails](#phase-3-multi-agent-crew-memory--guardrails)
   - [Phase 4: Observability & 4-Metric Evaluation Suite](#phase-4-observability--4-metric-evaluation-suite)
   - [Phase 5: AutoGen Review Team, Governance & Caching](#phase-5-autogen-review-team-governance--caching)
8. [Inspecting Structured Audit Logs](#8-inspecting-structured-audit-logs)
9. [Troubleshooting & Common Questions](#9-troubleshooting--common-questions)

---

## 1. Prerequisites & System Requirements

- **Operating System:** Windows 10/11, macOS (Intel or Apple Silicon), or Linux (Ubuntu 20.04+)
- **Python Version:** Python `3.10`, `3.11`, `3.12`, or `3.14` installed and added to `PATH`.
- **Git:** Git CLI installed.
- **Hardware:** Minimum 4 GB RAM (8 GB recommended for local vector embeddings).
- **API Keys / Cost:** **Zero external API keys required.** The system operates completely offline in deterministic `MOCK_LLM` mode with local vector embeddings via `sentence-transformers`.

---

## 2. Environment Setup & Installation

### Step 2.1: Clone the Repository
Open PowerShell or your preferred terminal and clone the repository:
```bash
git clone https://github.com/sandeep83103/RecruitmentCapstone.git
cd RecruitmentCapstone
```

### Step 2.2: Create and Activate Virtual Environment

#### On Windows (PowerShell):
```powershell
# Create virtual environment
python -m venv .venv

# If script execution is restricted in PowerShell, run this once in your session:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

#### On Windows (Command Prompt - cmd.exe):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2.3: Upgrade Package Manager & Install Dependencies
Install all required production dependencies pinned in `requirements.txt`:
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2.4: Verify Environment Configuration
The project includes a root `.env` file that suppresses external telemetry. Verify its presence or create it if missing:
```ini
# .env
CREWAI_DISABLE_TELEMETRY=true
OTEL_SDK_DISABLED=true
MOCK_LLM=true
```

---

## 3. Running the Automated Test Suite (All 48 Tests)

The test suite covers unit, integration, guardrail, governance, and API tests across all 5 project phases.

### Run All Tests with Verbose Output
```bash
pytest tests -v
```

### Run Tests by Specific Module
- **Mock LLM Core:**
  ```bash
  pytest tests/test_mock_llm.py -v
  ```
- **RAG & Seeded Dataset:**
  ```bash
  pytest tests/test_phase2_rag.py -v
  ```
- **CrewAI Multi-Agent & Guardrails:**
  ```bash
  pytest tests/test_phase3_multiagent.py -v
  ```
- **FastAPI REST, WebSocket & Logging:**
  ```bash
  pytest tests/test_api.py -v
  ```
- **AutoGen Review, Governance & Response Caching:**
  ```bash
  pytest tests/test_phase5_governance.py -v
  ```

**Expected Outcome:** `48 passed (100% pass rate)`.

---

## 4. Running the FastAPI Production Web Server

Launch the Uvicorn ASGI server to host both the REST API and the real-time WebSocket endpoints:

```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
```

Once running, interactive documentation is available in your browser:
- **Interactive Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Specification:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 5. Interacting with the REST API (curl & Python)

### 5.1 Service Health Check (`GET /health`)
Check service operational status:
```bash
curl -X GET http://127.0.0.1:8000/health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "Naukri.com Recruitment Support Agent",
  "offline_mode": true
}
```

---

### 5.2 Asking a Recruitment Policy Question (`POST /ask`)
Inquire about notice period, probation, internal transfers, remote work, or referral bonuses:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What is the standard probation period duration and review timeline?\"}"
```
**Response:**
```json
{
  "trace_id": "848d7d91-cb3a-4be7-8cfb-66d4826b6e41",
  "query": "What is the standard probation period duration and review timeline?",
  "intent": "policy_query",
  "final_answer": "Policy Guidelines: The standard probation duration for all new hires is 6 months starting from the date of joining. A formal 30-day performance review milestone is conducted between the employee and line manager.",
  "sources": [
    "08_probation_period.md"
  ],
  "escalation_recommended": false,
  "review_status": "approved",
  "cached": false,
  "latency_ms": 27.8,
  "audit_reason": "Policy compliance verified. Answer is fully grounded with zero unverified claims."
}
```

---

### 5.3 Candidate Application Status Lookup (`POST /ask`)
Lookup an existing job application (e.g., `APP-1001` or `APP-1011`):
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Please check the status of candidate application APP-1011.\"}"
```
**Response:**
```json
{
  "trace_id": "e9638c0f-3151-40eb-ba9c-3571d87a7e1f",
  "query": "Please check the status of candidate application APP-1011.",
  "intent": "status_lookup",
  "final_answer": "Application APP-1011 (Divya Rao) is currently in 'Screening' stage (Data Analyst). Expected CTC: INR 1,360,000. Escalation Score: 0.73 (HR Recruiter Alert Triggered).",
  "sources": [
    "APP-1011"
  ],
  "escalation_recommended": true,
  "review_status": "approved",
  "cached": false,
  "latency_ms": 23.4,
  "audit_reason": "Policy compliance verified. Answer is fully grounded with zero unverified claims."
}
```

---

### 5.4 Multi-Turn Continuity with `session_id`
Provide a `session_id` to maintain conversation memory across turns:

#### Turn 1:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Check status of application APP-1001.\", \"session_id\": \"recruiter_alice\"}"
```

#### Turn 2 (Pronoun Resolution):
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"What was its expected salary?\", \"session_id\": \"recruiter_alice\"}"
```
**Response:**
The system uses `session_memory.py` to resolve *"its"* to candidate `Aarav Sharma (APP-1001)` and returns `INR 470,000`.

---

### 5.5 Ingesting a New Policy Document (`POST /add-document`)
Upload a new policy to chunk, embed, and index into ChromaDB:
```bash
curl -X POST http://127.0.0.1:8000/add-document \
  -H "Content-Type: application/json" \
  -d "{\"title\": \"13_relocation_policy.md\", \"content\": \"Employees relocating across cities are entitled to relocation allowances up to INR 50,000 with mandatory receipt submissions.\"}"
```
**Response:**
```json
{
  "title": "13_relocation_policy.md",
  "status": "indexed",
  "fixed_chunks_added": 1,
  "sentence_chunks_added": 1,
  "trace_id": "7585a9bc-993d-4c31-9a7e-12fa8398b71d"
}
```

---

### 5.6 Python REST Client Script Example
Run this standalone script to query the running API:
```python
import requests

API_URL = "http://127.0.0.1:8000/ask"

payload = {
    "query": "What is the policy regarding remote work and work from home?",
    "session_id": "demo_session_01"
}

response = requests.post(API_URL, json=payload)
data = response.json()

print(f"Status Code : {response.status_code}")
print(f"Intent      : {data['intent']}")
print(f"Answer      : {data['final_answer']}")
print(f"Sources     : {data['sources']}")
print(f"Review      : {data['review_status']}")
print(f"Latency     : {data['latency_ms']} ms")
```

---

## 6. Interacting with the Streaming WebSocket API

The WebSocket endpoint (`/ws/chat`) streams tokens in real time with structured events:
- `{"event": "start", "trace_id": "..."}`
- `{"event": "chunk", "text": "..."}`
- `{"event": "complete", "response": { ... validated SupportAgentResponse ... }}`
- `{"event": "error", "message": "..."}`

### Python WebSocket Client Example
Save and run the following client script:

```python
import asyncio
import json
import websockets

async def chat_stream():
    uri = "ws://127.0.0.1:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        # Send inquiry
        request = {
            "query": "Can an employee buyout their notice period?",
            "session_id": "ws_client_session"
        }
        await websocket.send(json.dumps(request))
        print("Connected to WebSocket. Streaming tokens:\n")

        # Receive streaming events
        while True:
            try:
                raw_message = await websocket.recv()
                event = json.loads(raw_message)
                
                event_type = event.get("event")
                if event_type == "start":
                    print(f"[EVENT: START] Trace ID: {event.get('trace_id')}\n> ", end="", flush=True)
                elif event_type == "chunk":
                    print(event.get("text", ""), end="", flush=True)
                elif event_type == "complete":
                    print("\n\n[EVENT: COMPLETE]")
                    print(f"Review Status: {event['response']['review_status']}")
                    print(f"Sources: {event['response']['sources']}")
                    break
                elif event_type == "error":
                    print(f"\n[EVENT: ERROR] {event.get('message')}")
                    break
            except websockets.exceptions.ConnectionClosed:
                print("\n[DISCONNECTED]")
                break

if __name__ == "__main__":
    asyncio.run(chat_stream())
```

---

## 7. Running Standalone Verification Demos (Phase-by-Phase)

Every phase includes standalone scripts that demonstrate the exact requirements, mathematical formulas, and architectural invariants without launching a web server.

### Phase 2: Dataset, Indexing & RAG Core

1. **Deterministic Job-Application Dataset Generation:**
   ```bash
   python dataset.py
   ```
   *Validates:* 45 records, 5 categories ($\ge 3$), 5 statuses ($\ge 1$), and $22.2\%$ priority flags (strictly within $10\%–30\%$).

2. **ChromaDB Indexing (12 Policy Markdown Files):**
   ```bash
   python rag/vector_store.py
   ```
   *Validates:* Indexes all 12 policy files from `knowledge_base/` into `naukri_fixed_chunks` and `naukri_sentence_chunks`.

3. **Grounded RAG Retrieval & Calibrated Fallback ($\tau_{\text{RAG}} = 0.60$):**
   ```bash
   python rag/retrieval.py
   ```
   *Validates:* 5 in-scope policy answers retrieved; out-of-scope question triggers fallback refusal notice.

4. **Chunking Strategy Precision & Recall Evaluation:**
   ```bash
   python rag/eval_chunking.py
   ```
   *Validates:* Tabulates per-query Precision & Recall for Fixed-Size vs. Sentence-Based Chunking and outputs the engineering recommendation.

---

### Phase 3: Multi-Agent Crew, Memory & Guardrails

1. **Application Lookup Tool & Formulaic Escalation Score ($\tau_{\text{esc}} = 0.65$):**
   ```bash
   python tools/application_lookup.py
   ```
   *Validates:* Calculates $0.5 \times \text{flag} + 0.5 \times (\text{recency} / 30)$ and triggers recruiter alert when $\ge 0.65$.

2. **CrewAI 3-Agent Multi-Agent Orchestration:**
   ```bash
   python crew/recruitment_crew.py
   ```
   *Validates:* Policy Researcher, Application Specialist, and Response Composer execute sequentially via `crew.kickoff()`.

3. **In-Memory Multi-Turn Session Memory:**
   ```bash
   python memory/session_memory.py
   ```
   *Validates:* Multi-turn conversation retains context; fresh reset session flags lack of context.

4. **Multi-Tier Guardrails Suite:**
   ```bash
   python guardrails/pii_masker.py
   ```
   *Validates:* Phone number masked, prompt injection blocked, and ungrounded answer refused.

---

### Phase 4: Observability & 4-Metric Evaluation Suite

1. **Structured Logging & Pre-Disk PII Redaction Demo:**
   ```bash
   python observability/logger.py
   ```
   *Validates:* Logs formatted JSONL entries to `logs/support_agent.jsonl` with zero cleartext phone PII.

2. **15-Query 4-Dimensional LLM-as-a-Judge Evaluation Benchmark:**
   ```bash
   python evaluation/judge_suite.py
   ```
   *Validates:* Evaluates 15 benchmark queries across Accuracy (90.0%), Grounding (100.0%), Completeness (92.8%), and Safety (100.0%) for a 95.7% composite average.

---

### Phase 5: AutoGen Review Team, Governance & Caching

1. **AutoGen 2-Agent Secondary Review Team:**
   ```bash
   python autogen_review/review_team.py
   ```
   *Validates:* Case 1 approves clean draft unchanged; Case 2 catches and revises hallucinated claims; Case 3 validates `custom_message_types=[StructuredMessage[ReviewVerdict]]` registration.

2. **Runtime Character Budget Controller ($\le 1,000$ characters):**
   ```bash
   python governance/budget_controller.py
   ```
   *Validates:* Compliant queries pass; queries $> 1,000$ characters are rejected with HTTP 413 / `RuntimeBudgetExceeded`.

3. **Principle of Least Autonomy (Tool Isolation):**
   ```bash
   python governance/least_autonomy_validator.py
   ```
   *Validates:* Tool privileges are strictly bound; unauthorized tool binding raises `PermissionError`.

4. **Normalized Query Response Cache:**
   ```bash
   python cache/response_cache.py
   ```
   *Validates:* Cold query takes full pipeline ($\sim 14\text{ s}$); identical normalized query hits in-memory cache in $0.025\text{ ms}$ ($> 500,000\times$ speedup).

---

## 8. Inspecting Structured Audit Logs

All REST and WebSocket requests are logged to `logs/support_agent.jsonl` in ELK-compatible JSON-Lines format.

### View the Recent Log Entries
#### On Windows (PowerShell):
```powershell
Get-Content logs/support_agent.jsonl -Tail 10
```

#### On Linux / macOS:
```bash
tail -n 10 logs/support_agent.jsonl
```

### Verify Zero Cleartext Phone Numbers on Disk
Run this one-liner to verify that no Indian telephone numbers exist in the log file:
```bash
python -c "from observability.logger import verify_no_unmasked_phone_pii; print('PII Clean:', verify_no_unmasked_phone_pii())"
```
**Expected Output:** `PII Clean: True`.

---

## 9. Troubleshooting & Common Questions

### Q1: `Activate.ps1 cannot be loaded because running scripts is disabled`
**Solution:** PowerShell restricts script execution by default. Run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Q2: Do I need an OpenAI, Anthropic, or HuggingFace API key?
**Answer:** **No.** The project is engineered with a deterministic `MOCK_LLM` engine and local embedding models. It requires zero API keys, incurs zero monetary cost, and can run in completely air-gapped environments.

### Q3: How do I reset or clear the response cache?
**Answer:** The response cache is an in-memory LRU cache managed by `GLOBAL_RESPONSE_CACHE` in [cache/response_cache.py](file:///d:/Final%20Capstone%20Project/Recruitment/cache/response_cache.py). Restarting the FastAPI server automatically clears the cache, or you can invoke `GLOBAL_RESPONSE_CACHE.clear()`.

### Q4: How do I truncate the structured log file for testing?
**Answer:** Run:
```bash
python -c "from observability.logger import DEFAULT_LOGGER; DEFAULT_LOGGER.clear_logs(); print('Logs cleared.')"
```

### Q5: How do I re-index the ChromaDB knowledge base?
**Answer:**
```bash
python rag/vector_store.py
```
This re-loads all markdown documents from `knowledge_base/` and updates the ChromaDB vector collections under `chroma_storage/`.

---

**End of Usage Guide** — For questions, architectural details, and governance policies, refer to [README.md](file:///d:/Final%20Capstone%20Project/Recruitment/README.md) and [Docs/architecture.md](file:///d:/Final%20Capstone%20Project/Recruitment/Docs/architecture.md).
