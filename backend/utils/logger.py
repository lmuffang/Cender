"""Structured logging setup."""
import logging
import sys
from typing import Any

from config import settings


def setup_logger(name: str = "cender") -> logging.Logger:
    """
    Set up structured logger.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter based on config
    if settings.log_format == "json":
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d"
            )
        except ImportError:
            # Fallback to standard formatter if pythonjsonlogger not available
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# Global logger instance
logger = setup_logger()

