import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    """
    Configures structured logging for the application.
    Sets log level from settings and attaches standardized stream handlers.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Base logging format
    log_format = settings.LOG_FORMAT

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Standardize third-party logger levels
    logging.getLogger("uvicorn.access").setLevel(log_level)
    logging.getLogger("uvicorn.error").setLevel(log_level)
    logging.getLogger("fastapi").setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured named logger instance.
    """
    return logging.getLogger(name)
