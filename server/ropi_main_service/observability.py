import json
import logging
import os


DEFAULT_LOG_LEVEL = str(os.getenv("ROPI_LOG_LEVEL", "INFO")).upper()


def configure_logging(level: str | None = None):
    resolved_level = str(level or DEFAULT_LOG_LEVEL).upper()
    numeric_level = getattr(logging, resolved_level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def log_event(logger: logging.Logger, level: int, event: str, **fields):
    payload = {"event": event, **fields}
    logger.log(
        level,
        json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True),
    )


__all__ = ["configure_logging", "log_event"]
