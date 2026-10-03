"""JSON logging configuration for local services."""

import json
import logging
import os
from datetime import UTC, datetime

_CONTEXT_FIELDS = (
    "race_id",
    "car_id",
    "event_id",
    "topic",
    "partition",
    "offset",
    "car_count",
    "lap",
    "race_position",
    "error",
)


class JsonLogFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record and its known context fields.

        :param record: Log record to format.
        :return: JSON-encoded log entry.
        """
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = str(value) if field == "error" else value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> None:
    """Configure root logging as structured JSON on standard output."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())