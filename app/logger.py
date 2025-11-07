"""Logger configuration for the application."""

import logging
import os
import sys

from app.settings import APP_NAME

try:
    from rich.logging import RichHandler  # type: ignore

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def setup_logger(name: str = APP_NAME) -> logging.Logger:
    """Configure application logger with rich in development and JSON in production."""
    logger_instance = logging.getLogger(name)
    if logger_instance.handlers:  # Already configured
        return logger_instance

    env = os.getenv("ENVIRONMENT", "development").lower()
    log_level = logging.INFO if env == "production" else logging.DEBUG
    logger_instance.setLevel(log_level)

    if env == "production":
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
    else:
        if RICH_AVAILABLE:
            handler = RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_time=True,
                show_level=True,
                show_path=True,
            )
        else:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)

    handler.setLevel(log_level)
    logger_instance.addHandler(handler)
    return logger_instance


logger = setup_logger()
