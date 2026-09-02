import os

VELA_AGENT_BASE_URL = os.getenv(
    "VELA_AGENT_BASE_URL", "http://localhost:8000/api/v1"
)
# vela-agent v0.9+ JWT (service account for adapter calls)
VELA_AGENT_USERNAME = os.getenv("VELA_AGENT_USERNAME", "admin")
VELA_AGENT_PASSWORD = os.getenv("VELA_AGENT_PASSWORD", "admin123")
# Optional static token — skips login when set
VELA_AGENT_TOKEN = os.getenv("VELA_AGENT_TOKEN", "").strip()
WORKER_HOST = os.getenv("WORKER_HOST", "0.0.0.0")
WORKER_PORT = int(os.getenv("WORKER_PORT", "8100"))

# Enterprise shared knowledge bases bound to every duty Agent on create
SHARED_KB_IDS = [
    x.strip() for x in os.getenv("SHARED_KB_IDS", "").split(",") if x.strip()
]

# Model service for COMPOSITE entry agents (fallback: first available)
ENTRY_MODEL_SERVICE_ID = os.getenv("ENTRY_MODEL_SERVICE_ID", "").strip()

# Task runner polling
POLL_INTERVAL_INITIAL = float(os.getenv("POLL_INTERVAL_INITIAL", "2.0"))
POLL_INTERVAL_MAX = float(os.getenv("POLL_INTERVAL_MAX", "10.0"))
POLL_TIMEOUT_SECONDS = int(os.getenv("POLL_TIMEOUT_SECONDS", "3600"))

# Webhook retry: delays in minutes
WEBHOOK_RETRY_DELAYS_MIN = [1, 5, 30, 120, 360]

# Push scheduler interval (seconds)
PUSH_LOOP_INTERVAL = float(os.getenv("PUSH_LOOP_INTERVAL", "60"))
