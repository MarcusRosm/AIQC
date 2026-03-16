"""
Structured logging configuration for the QA Platform.

Provides a factory that returns stdlib loggers with a consistent JSON-like
format. Import `get_logger` wherever a module-level logger is needed.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

_FMT: Final[str] = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
_DATE_FMT: Final[str] = "%Y-%m-%dT%H:%M:%S"

_configured: bool = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger. Call once at startup."""
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Ensures root is configured with defaults."""
    configure_logging()
    return logging.getLogger(name)
