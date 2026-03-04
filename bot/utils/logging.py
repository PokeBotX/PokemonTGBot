"""Structured logging configuration with structlog."""
import logging
import os
import structlog


def setup_logging() -> None:
    """Configure structured logging with structlog."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Map string log level to logging module constants
    log_level_value = getattr(logging, log_level, logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level_value),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Call on module import
setup_logging()
