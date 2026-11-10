import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Deliberate allowlist: no exception text, request bodies, headers or query strings.
        data: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for key in (
            "correlation_id",
            "status_code",
            "method",
            "route",
            "error_type",
            "trace_id",
            "span_id",
            "duration_ms",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


def configure_logging() -> None:
    logger = logging.getLogger("orqentra")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
