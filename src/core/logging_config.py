"""
APOLLO Centralized Logging Configuration

Provides deterministic, reproducible logging for the APOLLO screening system.
All logs are timestamped and non-random for auditability.
"""
import logging
import sys
from datetime import datetime
from typing import Optional


class DeterministicFormatter(logging.Formatter):
    """
    Custom formatter that ensures deterministic log output.
    Uses ISO format timestamps for reproducibility.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().isoformat() + "Z"
        level = record.levelname
        logger = record.name
        message = record.getMessage()
        
        return f"[{timestamp}] [{level}] [{logger}] {message}"


def setup_logging(level: int = logging.INFO, debug_mode: bool = False) -> logging.Logger:
    """
    Configure APOLLO logging with deterministic output.
    
    Args:
        level: Logging level (default INFO)
        debug_mode: Enable DEBUG level logging
    
    Returns:
        Configured logger instance
    """
    if debug_mode:
        level = logging.DEBUG
    
    logger = logging.getLogger("apollo")
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(DeterministicFormatter())
    
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger for APOLLO components.
    
    Args:
        name: Optional logger name (defaults to "apollo")
    
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"apollo.{name}")
    return logging.getLogger("apollo")


INGESTION_LOGGER = get_logger("ingestion")
METADATA_LOGGER = get_logger("metadata")
PARSER_LOGGER = get_logger("parser")
SCREENING_LOGGER = get_logger("screening")
PROVENANCE_LOGGER = get_logger("provenance")