# app/core/logging.py
import logging
import os
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"

def setup_logging(level: Optional[str] = None) -> None:
    """
    Initialize root logging once. Safe to call multiple times.
    Priority for level:
      1) explicit `level` arg
      2) env LOG_LEVEL (e.g., DEBUG, INFO, WARNING)
      3) default INFO
    """
    if getattr(setup_logging, "_configured", False):
        if level:
            set_level(level)
        return

    log_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear default handlers (e.g., from uvicorn in some setups)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT))
    root.addHandler(handler)

    setup_logging._configured = True  # type: ignore[attr-defined]

def set_level(level: str) -> None:
    """Dynamically change the root log level at runtime."""
    logging.getLogger().setLevel(level.upper())

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger. Use like:
        from app.core.logging import get_logger
        log = get_logger(__name__)
        log.info("Hello")
    """
    # Ensure logging is initialized if someone forgets to call setup explicitly
    if not getattr(setup_logging, "_configured", False):
        setup_logging()
    return logging.getLogger(name if name else __name__)
