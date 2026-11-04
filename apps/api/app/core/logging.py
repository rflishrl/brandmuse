import hashlib
import json
import logging
import sys
from typing import Any


def hash_session_id(session_id: str | None) -> str:
    """Hash session ID for privacy-compliant logging."""
    if not session_id:
        return "none"
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured application logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add contextual attributes if provided in record
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "session_hash"):
            log_data["session_hash"] = record.session_hash

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured JSON logging for the application."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers = [handler]

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)


logger = logging.getLogger("brandmuse")
