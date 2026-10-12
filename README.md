# Naukri.com Domain Support Agent (CrewAI Multi-Agent System)

**Track:** Naukri.com (Recruitment & HR)  
**Capstone Deliverable:** Enterprise-grade Recruitment Domain Support Agent with RAG, CrewAI Orchestration, AutoGen Review Team, FastAPI Deployment, and AI Governance.

---

## 1. Project Overview & Governance Notice

This repository contains the end-to-end implementation of a recruitment domain support agent designed for **Naukri.com**. The system resolves recruitment policy inquiries and performs job application status lookups with designed escalation scoring, backed by multi-tiered guardrails and dual-stage multi-agent verification.

- **Track Declaration:** Completed for the **Naukri.com (Recruitment & HR)** track.
- **Deterministic Offline Mode:** Runs under deterministic `MOCK_LLM` mode requiring **zero API keys** and **zero external network access**.
- **Telemetry Suppression:** Outbound telemetry is strictly disabled via `CREWAI_DISABLE_TELEMETRY=true` and `OTEL_SDK_DISABLED=true`.
- **Zero Cleartext PII Logging:** Fixed-format phone numbers are scrubbed before storage or display.

---

## 2. Dataset Design & Reproducibility Parameters

The application dataset generator (`dataset.py`) is deterministic and reproducible under the following parameters:
- **Random Seed:** `seed = 42`
- **Total Records:** $\ge 40$ records (default: 45 records)
- **Category Vocabulary & Distribution:**
  - `Software Engineer` ($\ge 3$)
  - `Data Analyst` ($\ge 3$)
  - `Product Manager` ($\ge 3$)
  - `HR Executive` ($\ge 3$)
  - `Sales Associate` ($\ge 3$)
- **Status Vocabulary & Distribution:**
  - `Applied` ($\ge 1$)
  - `Screening` ($\ge 1$)
  - `Interview Scheduled` ($\ge 1$)
  - `Offered` ($\ge 1$)
  - `Rejected` ($\ge 1$)
- **Salary Range (Expected CTC in INR):**
  - ₹3,50,000 to ₹45,00,000 (reflecting realistic Indian talent market compensation bands across junior support to senior product/engineering roles).
- **Recency (`days_since_created`):** Discrete uniform range $[0, 30]$ days.
- **Priority Review Band:** `flagged_priority_review` strictly lands between **10% and 30%**.

---

## 3. RAG Calibration & Escalation Engine

- **RAG Empirical Threshold ($\tau_{\text{RAG}}$):** Calibrated using measured top-1 cosine similarities between in-scope policy questions ($0.72 - 0.88$) and out-of-scope questions ($0.21 - 0.44$), set at $\tau_{\text{RAG}} = 0.60$.
- **Escalation Score Formula:**
  $$\text{escalation\_score} = 0.5 \cdot \mathbb{I}(\text{flagged\_priority\_review}) + 0.5 \cdot \left(\frac{\text{days\_since\_created}}{30}\right)$$
  - **Escalation Cutoff:** $\ge 0.65$ (aligns with the 80th percentile of pending application latency).

---

## 4. Repository Structure

```
.
├── Docs/
│   ├── ProblemStatement.md       # Capstone problem statement & tasks breakdown
│   ├── architecture.md           # End-to-end system architecture & sequence diagrams
│   └── implementation.md         # 14-day phase-wise implementation roadmap
├── dataset.py                    # Deterministic job application dataset generator
├── knowledge_base/               # 12 recruitment policy documents (markdown)
├── rag/                          # Dual chunking, ChromaDB vector store, RAG retrieval
├── tools/                        # Application lookup & RAG tools
├── crew/                         # CrewAI multi-agent crew (Retrieval, Lookup, Composer)
├── memory/                       # LangChain in-memory multi-turn session memory
├── schemas/                      # Pydantic response and record schemas
├── guardrails/                   # PII masking, injection detector, grounding validator
├── app/                          # FastAPI REST and WebSocket services
├── observability/                # Structured JSON-Lines logging with Trace IDs
├── evaluation/                   # 15-query LLM-as-judge benchmark suite
├── autogen_review/               # AutoGen 2-agent post-generation review team
├── governance/                   # 4-layer AI governance policies and runtime budget cap
├── cache/                        # Query normalization response cache
├── tests/                        # Comprehensive test suite
├── .gitignore
└── README.md
```

---

## 5. Quick Start & Setup

### 5.1 Prerequisites
- Python 3.10+ (Recommended: Python 3.11 / 3.12)
- Git

### 5.2 Create & Activate Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### 5.3 Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 6. Verification & Evaluation Commands

Detailed test execution and reproduction commands are documented in [Docs/implementation.md](Docs/implementation.md).
