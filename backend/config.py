"""Settings read from environment variables (.env). The API key never leaves the backend."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
RESULTS_DIR = ROOT / "results"
FRONTEND_DIR = ROOT / "frontend"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai").rstrip("/")

STUDENT_NAME = os.getenv("STUDENT_NAME", "Your Name")
ROLL_NUMBER = os.getenv("ROLL_NUMBER", "Your Roll No.")

MODELS = [
    {"key": "jev", "name": "Jev 1.13", "category": "System-1 decision model",
     "id": os.getenv("MODEL_JEV", "typesafe/jev-1.13"), "api": "decisions"},
    {"key": "luna", "name": "OpenAI GPT-6 Luna Decisions", "category": "System-1 decision model",
     "id": os.getenv("MODEL_LUNA", "openai/gpt-6-luna-decisions"), "api": "decisions"},
    {"key": "clef", "name": "Cloudflare Clef", "category": "System-1 decision model",
     "id": os.getenv("MODEL_CLEF", "cloudflare/clef"), "api": "decisions"},
    {"key": "opus", "name": os.getenv("MODEL_OPUS_NAME", "Claude Opus 5.5"),
     "category": os.getenv("MODEL_OPUS_CATEGORY", "Frontier LLM"),
     "id": os.getenv("MODEL_OPUS", "anthropic/claude-opus-5.5"), "api": "chat"},
]

MOVE_LIMIT = _int("MOVE_LIMIT", 30)            # max turns per model per puzzle
MAX_CALLS = _int("MAX_CALLS", 64)              # hard cap on paid API calls per run
REQUEST_TIMEOUT = _float("REQUEST_TIMEOUT", 180)  # seconds, same for every model
RETRIES = _int("RETRIES", 0)                   # same retry policy for every model
HISTORY_LEN = _int("HISTORY_LEN", 6)           # recent moves shown to every model
SEED = _int("SEED", 2026)
CONCURRENCY = _int("CONCURRENCY", 12)
OPUS_REASONING_EFFORT = os.getenv("OPUS_REASONING_EFFORT", "medium")  # low|medium|high|none
OPUS_MAX_TOKENS = _int("OPUS_MAX_TOKENS", 8000)
OPUS_RESPONSE_FORMAT = os.getenv("OPUS_RESPONSE_FORMAT", "json_schema")  # json_schema|json_object|none

# Test sets: (name, number of puzzles, min scramble length, max scramble length)
PROFILES = {
    "mock": {
        "label": "Mock (offline, 0 API calls)",
        "live": False,
        "sets": [("warmup", 1, 3, 4), ("primary", 5, 4, 5), ("extension", 1, 15, 20)],
        "max_calls": None,
    },
    "budget": {
        "label": f"Budget ({_int('BUDGET_PUZZLES', 3)} primary puzzles, hard cap {MAX_CALLS} calls)",
        "live": True,
        "sets": [("primary", _int("BUDGET_PUZZLES", 3), 4, 4)],
        "max_calls": MAX_CALLS,
    },
    "full": {
        "label": "Full protocol (2 warm-up + 5 primary + 2 extension, up to ~1000 calls)",
        "live": True,
        "sets": [("warmup", 2, 3, 4), ("primary", 5, 4, 5), ("extension", 2, 15, 20)],
        "max_calls": _int("FULL_MAX_CALLS", 1100),
    },
}
