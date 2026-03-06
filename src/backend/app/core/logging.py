"""
Structured logging setup.

Configures logging for the application:
- JSON format for production (machine-parseable)
- Pretty format for development (human-readable)
- Request ID tracking for correlating log entries
"""

import logging
import sys


# Development format: colored, human-readable
_DEV_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"

# Production format: JSON-like structured log line
_PROD_FORMAT = (
    '{"time":"%(asctime)s","level":"%(levelname)s",'
    '"logger":"%(name)s","message":"%(message)s"}'
)


def setup_logging(log_level: str = "info") -> None:
    """Configure application logging.

    Sets up structured logging with the appropriate format based on
    the environment. Should be called once during application startup.

    - When log_level is "debug", uses a pretty human-readable format
      suitable for local development.
    - Otherwise, uses a JSON-structured format suitable for production
      log aggregation systems.

    Also aligns uvicorn's own loggers to the same level so that
    access and error logs are consistent.

    Args:
        log_level: The minimum log level to emit. One of:
                   "debug", "info", "warning", "error", "critical".
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    is_dev = log_level.lower() == "debug"
    fmt = _DEV_FORMAT if is_dev else _PROD_FORMAT

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    # Remove any existing handlers to avoid duplicates on re-init
    root.handlers.clear()
    root.addHandler(handler)

    # Align uvicorn loggers so access/error logs respect our level
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(uvicorn_logger_name)
        uv_logger.setLevel(level)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a named logger instance.

    Convenience function that returns a logger with the given name.
    All modules should use this for consistent logger creation.

    Args:
        name: The logger name, typically __name__ of the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
