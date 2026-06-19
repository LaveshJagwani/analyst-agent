import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# ── LangSmith Tracing ─────────────────────────────────────────────────────────
LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "analyst-agent")
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
TRACE_DIR = OUTPUT_DIR / "traces"

# Ensure output directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)
TRACE_DIR.mkdir(parents=True, exist_ok=True)

# ── Constraints ───────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 20
EXECUTION_TIMEOUT_SECONDS = 30
MIN_SAMPLE_SIZE = 10
CORRELATION_THRESHOLD = 0.3
P_VALUE_THRESHOLD = 0.05
RATE_LIMIT_DELAY = 2  # Gentle pacing for Groq free tier

# ── LLM ───────────────────────────────────────────────────────────────────────
MODEL_NAME = "llama-3.3-70b-versatile"


def wait_for_quota():
    """Pause execution to respect free tier rate limits."""
    import time
    if RATE_LIMIT_DELAY > 0:
        time.sleep(RATE_LIMIT_DELAY)


def get_llm(temperature: float = 0.1):
    """Return a configured Groq LLM instance."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in .env. Please get one from console.groq.com.")

    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=MODEL_NAME,
        temperature=temperature,
        max_retries=10,
        request_timeout=60,
    )
