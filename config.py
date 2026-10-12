"""
Configuration Module for Naukri.com Domain Support Agent.
Enforces zero-network telemetry suppression and deterministic environment parameters.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# Enforce Outbound Telemetry Suppression Immediately at Import
# ------------------------------------------------------------------------------
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Load local environment variables if available
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# ------------------------------------------------------------------------------
# Core System Constants & Governance Parameters
# ------------------------------------------------------------------------------
TRACK_NAME = "Naukri.com (Recruitment & HR)"
MOCK_LLM_ENABLED = os.getenv("MOCK_LLM", "true").lower() == "true"
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

# Paths
DOCS_DIR = BASE_DIR / "Docs"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE_PATH = LOGS_DIR / "support_agent.jsonl"
CHROMA_PERSIST_DIR = BASE_DIR / "chroma_storage"

# Ensure runtime directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Empirically Calibrated Thresholds
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.60"))
ESCALATION_THRESHOLD = float(os.getenv("ESCALATION_THRESHOLD", "0.65"))

# Runtime Governance Constraints
MAX_QUERY_CHARACTER_LIMIT = 1000
RISK_CLASSIFICATION = "Medium-to-High"

# Network & Serving
API_HOST = os.getenv("HOST", "127.0.0.1")
API_PORT = int(os.getenv("PORT", "8000"))
