"""
Logging configuration and error hierarchy for the format converter.

This module provides:
- Structured logging setup with console and file handlers
- Custom exception hierarchy for different error types
- Error categorization (user vs technical errors)
"""

import logging
import sys
from typing import Optional, Dict, Any, Iterator
from contextlib import contextmanager
from dataclasses import dataclass


class ConverterError(Exception):
    """Base error for all converter operations."""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)

    def __str__(self) -> str:
        if self.suggestion:
            return f"{self.message} (Suggestion: {self.suggestion})"
        return self.message


class UserError(ConverterError):
    """Error caused by user input/action."""

    pass


class SystemError(ConverterError):
    """Error caused by system/environment issues."""

    def __init__(
        self,
        message: str,
        technical_details: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        self.technical_details = technical_details
        super().__init__(message, suggestion)


class ConversionError(ConverterError):
    """Error during conversion process."""

    pass


class DependencyError(SystemError):
    """Error when required dependency is missing."""

    pass


class DiskSpaceError(SystemError):
    """Error when insufficient disk space."""

    pass


class FormatNotSupportedError(UserError):
    """Error when requested format is not supported."""

    pass


class FileNotFoundError_(ConverterError):
    """Error when source file not found."""

    pass


class TimeoutError_(ConverterError):
    """Error when operation times out."""

    pass


class InvalidInputError(UserError):
    """Error when user input is invalid."""

    pass


class AuthenticationError(UserError):
    """Error during authentication/authorization."""

    pass


class ProcessingTimeoutError(ConversionError):
    """Error when processing takes too long."""

    pass


@dataclass
class ProgressInfo:
    """Information about conversion progress."""

    current_step: str
    progress: float
    total_steps: Optional[int] = None
    eta_seconds: Optional[float] = None
    message: Optional[str] = None


class ProgressLogger:
    """Logger for conversion progress updates."""

    def __init__(self, logger: logging.Logger, total_steps: Optional[int] = None):
        self.logger = logger
        self.total_steps = total_steps
        self.current_step = 0

    def update(self, step_name: str, progress: float, message: Optional[str] = None) -> None:
        """Update progress for a step."""
        self.current_step += 1
        if self.total_steps:
            progress = min(100, (self.current_step / self.total_steps) * 100)

        eta = self._calculate_eta(progress)

        if progress >= 100:
            self.logger.info("✓ Conversion complete")
        else:
            eta_str = f" (ETA: ~{eta / 60:.1f}m)" if eta else ""
            msg = f"[{self.current_step}/{self.total_steps or '?'}] {step_name} - Progress: {progress:.1f}%{eta_str}"
            if message:
                msg += f" - {message}"
            self.logger.info(msg)

    def _calculate_eta(self, progress: float) -> Optional[float]:
        """Calculate estimated time remaining."""
        if self.current_step == 0 or progress <= 0:
            return None
        if progress >= 100:
            return 0.0

        # Simple ETA calculation
        elapsed = (self.current_step / self.total_steps) * progress if self.total_steps else 0
        if elapsed <= 0:
            return None

        remaining_percent = 100 - progress
        remaining_steps = (remaining_percent / progress) * self.current_step if progress > 0 else 0

        if self.total_steps:
            remaining = self.total_steps - self.current_step
        else:
            remaining = remaining_steps

        return (remaining / self.current_step) * elapsed if self.current_step > 0 else None


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Set up logging configuration for the converter.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        format_string: Optional custom format string

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("converter")
    logger.setLevel(level)
    logger.handlers.clear()

    fmt = format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (e.g., 'server', 'deps')

    Returns:
        Logger instance for the module
    """
    return logging.getLogger(f"converter.{name}")


def log_conversion_error(
    logger: logging.Logger, error: Exception, include_traceback: bool = True
) -> None:
    """Log an error with appropriate formatting.

    Args:
        logger: Logger instance
        error: Exception to log
        include_traceback: Whether to include stack trace
    """
    logger.error(f"Error occurred: {error}")

    if isinstance(error, ConverterError) and error.suggestion:
        logger.info(f"Suggestion: {error.suggestion}")

    if isinstance(error, SystemError) and error.technical_details:
        logger.debug(f"Technical details: {error.technical_details}")

    if include_traceback:
        import traceback

        logger.debug("\n".join(traceback.format_exception(type(error), error, error.__traceback__)))


root_logger = setup_logging()


def log_conversion_start(
    logger: logging.Logger, source_file: str, target_format: str, **kwargs: Dict[str, Any]
) -> None:
    """Log the start of a conversion operation.

    Args:
        logger: Logger instance
        source_file: Path to source file
        target_format: Target format
        **kwargs: Additional metadata
    """
    logger.info("=" * 60)
    logger.info(f"Starting conversion: {source_file} -> {target_format}")
    for key, value in kwargs.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)


def log_conversion_complete(
    logger: logging.Logger,
    success: bool,
    duration_seconds: float,
    output_file: Optional[str] = None,
    **kwargs: Dict[str, Any],
) -> None:
    """Log the completion of a conversion operation.

    Args:
        logger: Logger instance
        success: Whether conversion succeeded
        duration_seconds: Duration in seconds
        output_file: Path to output file (if success)
        **kwargs: Additional metadata
    """
    status = "✓ SUCCESS" if success else "✗ FAILED"
    logger.info("=" * 60)
    logger.info(f"{status} - Conversion completed in {duration_seconds:.2f}s")
    if output_file:
        logger.info(f"  Output: {output_file}")
    for key, value in kwargs.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)


def capture_warnings() -> Iterator[list]:
    """Context manager to capture logging warnings.

    Yields:
        List of captured warning messages.
    """
    captured = []

    def warning_handler(msg, *args, **kwargs):
        captured.append(str(msg))

    logging.captureWarnings(True)
    original_warning = logging.warn
    logging.warn = warning_handler

    try:
        yield captured
    finally:
        logging.captureWarnings(False)
        logging.warn = original_warning


@contextmanager
def capture_warnings() -> Iterator[list]:
    """Context manager to capture logging warnings.

    Yields:
        List of captured warning messages.
    """
    captured = []

    def warning_handler(msg, *args, **kwargs):
        captured.append(str(msg))

    logging.captureWarnings(True)
    original_warning = logging.warn
    logging.warn = warning_handler

    try:
        yield captured
    finally:
        logging.captureWarnings(False)
        logging.warn = original_warning


def log_conversion_start(
    logger: logging.Logger, source_file: str, target_format: str, **kwargs: Dict[str, Any]
) -> None:
    """Log the start of a conversion operation.

    Args:
        logger: Logger instance
        source_file: Path to source file
        target_format: Target format
        **kwargs: Additional metadata
    """
    logger.info("=" * 60)
    logger.info(f"Starting conversion: {source_file} -> {target_format}")
    for key, value in kwargs.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)


def log_conversion_complete(
    logger: logging.Logger,
    success: bool,
    duration_seconds: float,
    output_file: Optional[str] = None,
    **kwargs: Dict[str, Any],
) -> None:
    """Log the completion of a conversion operation.

    Args:
        logger: Logger instance
        success: Whether conversion succeeded
        duration_seconds: Duration in seconds
        output_file: Path to output file (if success)
        **kwargs: Additional metadata
    """
    status = "✓ SUCCESS" if success else "✗ FAILED"
    logger.info("=" * 60)
    logger.info(f"{status} - Conversion completed in {duration_seconds:.2f}s")
    if output_file:
        logger.info(f"  Output: {output_file}")
    for key, value in kwargs.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)


def log_error(logger: logging.Logger, error: Exception, include_traceback: bool = True) -> None:
    """Log an error with appropriate formatting.

    Args:
        logger: Logger instance
        error: Exception to log
        include_traceback: Whether to include stack trace
    """
    logger.error(f"Error occurred: {error}")

    if isinstance(error, ConverterError) and error.suggestion:
        logger.info(f"Suggestion: {error.suggestion}")

    if isinstance(error, SystemError) and error.technical_details:
        logger.debug(f"Technical details: {error.technical_details}")

    if include_traceback:
        import traceback

        logger.debug("\n".join(traceback.format_exception(type(error), error, error.__traceback__)))
