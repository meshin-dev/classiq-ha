"""Application settings loaded from environment variables with defaults."""

import os


def str_to_int(s: str, default: int) -> int:
    """Convert string to integer with default fallback."""
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


APP_NAME = os.getenv("APP_NAME", "classiq")

# Redis/cache settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = str_to_int(os.getenv("REDIS_PORT"), 6379)
REDIS_DB = str_to_int(os.getenv("REDIS_DB"), 0)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
REDIS_RESULT_TTL = str_to_int(os.getenv("REDIS_RESULT_TTL"), 3600)

# Broker settings (in milliseconds)
BROKER_TIME_LIMIT_MS = str_to_int(os.getenv("BROKER_TIME_LIMIT_MS"), 120000)
BROKER_MAX_RETRIES = str_to_int(os.getenv("BROKER_MAX_RETRIES"), 3)

# Qiskit settings
QC_TASK_TIME_LIMIT_MS = str_to_int(os.getenv("QC_TASK_TIME_LIMIT_MS"), 300000)
QC_TASK_MAX_RETRIES = str_to_int(os.getenv("QC_TASK_MAX_RETRIES"), 3)
QC_TASK_DEFAULT_SHOTS = str_to_int(os.getenv("QC_TASK_DEFAULT_SHOTS"), 1024)

# API settings
API_HOST = str(os.getenv("API_HOST")).strip() or "0.0.0.0"
API_PORT = str_to_int(os.getenv("API_PORT"), 8000)
