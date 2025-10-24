"""Structured logging configuration for Conductor."""

import structlog
import logging
import sys
from typing import Any, Dict

def configure_logging(log_level: str = "INFO", enable_json: bool = True):
    """
    Configure structured logging for Conductor.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARN, ERROR)
        enable_json: Whether to use JSON formatting
    """
    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        stream=sys.stdout,
        format="%(message)s"
    )
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
        
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class ConductorLogger:
    """Structured logger for Conductor with context."""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        
    def bind_context(self, **kwargs) -> 'ConductorLogger':
        """Bind context variables to logger."""
        return ConductorLogger(self.logger.bind(**kwargs))
        
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, **kwargs)
        
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, **kwargs)
        
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, **kwargs)
        
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, **kwargs)
        
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, **kwargs)


def get_logger(name: str) -> ConductorLogger:
    """Get a structured logger instance."""
    return ConductorLogger(name)
