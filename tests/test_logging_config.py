"""
Tests for logging configuration and error handling.

Covers:
- Logger configuration and levels
- Custom exception hierarchy
- Error categorization
"""

import logging
import pytest

from src.converter.logging_config import (
    ConverterError,
    UserError,
    SystemError,
    ConversionError,
    DependencyError,
    DiskSpaceError,
    FormatNotSupportedError,
    FileNotFoundError_,
    TimeoutError_,
    InvalidInputError,
    AuthenticationError,
    ProcessingTimeoutError,
    setup_logging,
    get_logger,
    log_error,
    log_conversion_start,
    log_conversion_complete,
    log_conversion_error,
    ProgressLogger,
    capture_warnings,
    FormatNotSupportedError,
)


class TestConverterError:
    """Tests for ConverterError base class."""

    def test_basic_error_message(self):
        """Test error with basic message."""
        error = ConverterError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.suggestion is None

    def test_error_with_suggestion(self):
        """Test error with helpful suggestion."""
        error = ConverterError("File not found", suggestion="Check the file path")
        assert "File not found" in str(error)
        assert "Check the file path" in str(error)
        assert error.suggestion == "Check the file path"


class TestUserError:
    """Tests for UserError class."""

    def test_user_error_basic(self):
        """Test basic user error."""
        error = UserError("Invalid input")
        assert isinstance(error, ConverterError)
        assert error.message == "Invalid input"

    def test_user_error_with_suggestion(self):
        """Test user error with suggestion."""
        error = UserError("Invalid format", suggestion="Use jpg, png, or webp")
        assert "Invalid format" in str(error)
        assert "Use jpg, png, or webp" in str(error)


class TestSystemError:
    """Tests for SystemError class."""

    def test_system_error_basic(self):
        """Test basic system error."""
        error = SystemError("Disk full")
        assert isinstance(error, ConverterError)
        assert error.message == "Disk full"

    def test_system_error_with_technical_details(self):
        """Test system error with technical details."""
        error = SystemError("FFmpeg crashed", technical_details="Exit code 139")
        assert error.technical_details == "Exit code 139"
        assert error.message == "FFmpeg crashed"


class TestSpecificErrors:
    """Tests for specific error types."""

    def test_conversion_error(self):
        """Test ConversionError."""
        error = ConversionError("Failed to convert")
        assert isinstance(error, ConverterError)

    def test_dependency_error(self):
        """Test DependencyError."""
        error = DependencyError("FFmpeg not found")
        assert isinstance(error, SystemError)
        assert isinstance(error, ConverterError)

    def test_disk_space_error(self):
        """Test DiskSpaceError."""
        error = DiskSpaceError("Insufficient disk space")
        assert isinstance(error, SystemError)

    def test_format_not_supported_error(self):
        """Test FormatNotSupportedError."""
        error = FormatNotSupportedError("SVG not supported")
        assert isinstance(error, UserError)

    def test_file_not_found_error(self):
        """Test FileNotFoundError_."""
        error = FileNotFoundError_("Source file missing")
        assert isinstance(error, ConverterError)

    def test_timeout_error(self):
        """Test TimeoutError_."""
        error = TimeoutError_("Conversion timed out")
        assert isinstance(error, ConverterError)


class TestLoggingSetup:
    """Tests for logging setup."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        logger = setup_logging()
        assert logger.name == "converter"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    def test_setup_logging_debug_level(self):
        """Test logging setup with DEBUG level."""
        logger = setup_logging(level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test_module")
        assert logger.name == "converter.test_module"

    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("module")
        logger2 = get_logger("module")
        assert logger1 is logger2


    """Tests for additional error classes."""

    def test_invalid_input_error(self):
        """Test InvalidInputError."""
        error = InvalidInputError("Invalid file path")
        assert isinstance(error, UserError)
        assert isinstance(error, ConverterError)

    def test_invalid_input_error_with_suggestion(self):
        """Test InvalidInputError with suggestion."""
        error = InvalidInputError("Invalid format", suggestion="Use JSON or XML")
        assert "Invalid format" in str(error)
        assert "Use JSON or XML" in str(error)

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Invalid credentials")
        assert isinstance(error, UserError)
        assert isinstance(error, ConverterError)

    def test_processing_timeout_error(self):
        """Test ProcessingTimeoutError."""
        error = ProcessingTimeoutError("Processing took too long")
        assert isinstance(error, ConversionError)
        assert isinstance(error, ConverterError)


class TestProgressLogger:
    """Tests for progress logging."""

    def test_progress_logger_initialization(self):
        """Test ProgressLogger initialization."""
        logger = get_logger("progress_test")
        progress_logger = ProgressLogger(logger, total_steps=5)

        assert progress_logger.total_steps == 5
        assert progress_logger.current_step == 0

    def test_progress_logger_no_total_steps(self):
        """Test ProgressLogger without total steps."""
        logger = get_logger("progress_test")
        progress_logger = ProgressLogger(logger)

        assert progress_logger.total_steps is None
        assert progress_logger.current_step == 0

    def test_progress_logger_update(self, caplog):
        """Test progress logger update."""
        logger = get_logger("progress_test")
        progress_logger = ProgressLogger(logger, total_steps=3)

        with caplog.at_level(logging.INFO):
            progress_logger.update("Step 1", 33.3)
        
        assert "Step 1" in caplog.text
        assert "33.3%" in caplog.text

    def test_progress_logger_complete(self, caplog):
        """Test progress logger completes all steps."""
        logger = get_logger("progress_test")
        progress_logger = ProgressLogger(logger, total_steps=3)

        with caplog.at_level(logging.INFO):
            progress_logger.update("Step 1", 33.3)
            progress_logger.update("Step 2", 66.7)
            progress_logger.update("Step 3", 100)
        
        assert "Step 1" in caplog.text
        assert "Step 2" in caplog.text
        assert "✓ Conversion complete" in caplog.text

    def test_progress_logger_message(self, caplog):
        """Test progress logger with message."""
        logger = get_logger("progress_test")
        progress_logger = ProgressLogger(logger, total_steps=2)

        with caplog.at_level(logging.INFO):
            progress_logger.update("Step 1", 50.0, "Processing file")
        
        assert "Step 1" in caplog.text
        assert "Processing file" in caplog.text


class TestLoggingHelpers:
    """Tests for logging helper functions."""

    def test_log_conversion_start(self, caplog):
        """Test log_conversion_start."""
        logger = get_logger("test_helper")
        with caplog.at_level(logging.INFO):
            log_conversion_start(logger, "input.pdf", "docx")
        
        assert "Starting conversion" in caplog.text
        assert "input.pdf" in caplog.text
        assert "docx" in caplog.text

    def test_log_conversion_complete_success(self, caplog):
        """Test log_conversion_complete for success."""
        logger = get_logger("test_helper")
        with caplog.at_level(logging.INFO):
            log_conversion_complete(logger, True, 1.5, "output.docx")
        
        assert "✓ SUCCESS" in caplog.text
        assert "1.50s" in caplog.text
        assert "output.docx" in caplog.text

    def test_log_conversion_complete_failure(self, caplog):
        """Test log_conversion_complete for failure."""
        logger = get_logger("test_helper")
        with caplog.at_level(logging.INFO):
            log_conversion_complete(logger, False, 1.5, output_file=None)
        
        assert "✗ FAILED" in caplog.text
        assert "1.50s" in caplog.text

    def test_log_conversion_error(self, caplog):
        """Test log_conversion_error."""
        logger = get_logger("test_helper")
        error = Exception("Invalid input")
        with caplog.at_level(logging.ERROR):
            log_conversion_error(logger, error)
        
        assert "Error occurred" in caplog.text
        assert "Invalid input" in caplog.text

    def test_log_conversion_error_system(self, caplog):
        """Test log_conversion_error for system error."""
        from src.converter.logging_config import SystemError
        logger = get_logger("test_helper")
        error = SystemError("System error")
        with caplog.at_level(logging.ERROR):
            log_conversion_error(logger, error)
        
        assert "Error occurred" in caplog.text
        assert "System error" in caplog.text


class TestWarningCapture:
    """Tests for warning capture functionality."""

    def test_capture_warnings_context_manager(self):
        """Test capture_warnings context manager."""
        with capture_warnings() as captured:
            # This should not trigger the capture
            pass

        # Captured list should be empty initially
        assert captured == []


class TestIntegration:
    """Integration tests for logging and error handling."""

    def test_full_conversion_workflow(self, caplog):
        """Test a complete conversion workflow with logging."""
        logger = get_logger("integration_test")

        with caplog.at_level(logging.INFO):
            log_conversion_start(logger, "input.pdf", "docx")

            progress_logger = ProgressLogger(logger, total_steps=3)

            progress_logger.update("Parsing PDF", 33.3, "Extracting content")
            progress_logger.update("Converting", 66.7, "Formatting document")
            # Finalizing step is skipped when progress reaches 100%

            log_conversion_complete(logger, True, 2.5, "output.docx")

        # Verify all steps were logged
        assert "Starting conversion" in caplog.text
        assert "Parsing PDF" in caplog.text
        assert "Converting" in caplog.text
        assert "✓ SUCCESS" in caplog.text

    def test_error_in_workflow(self, caplog):
        """Test workflow with an error."""
        logger = get_logger("integration_test")

        with caplog.at_level(logging.INFO):
            log_conversion_start(logger, "input.pdf", "docx")

            progress_logger = ProgressLogger(logger, total_steps=3)

            progress_logger.update("Parsing PDF", 33.3)
            progress_logger.update("Converting", 66.7)

            error = FormatNotSupportedError("PDF")
            log_conversion_error(logger, error)

        # Verify steps were logged
        assert "Starting conversion" in caplog.text
        assert "Parsing PDF" in caplog.text
        assert "Converting" in caplog.text
        assert "Error occurred" in caplog.text
