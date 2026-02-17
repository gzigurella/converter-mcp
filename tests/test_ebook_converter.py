"""
Tests for ebook converter.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.converter.converters.ebook import (
    EbookConverter,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)


class TestEbookConverter:
    """Tests for EbookConverter class."""

    def test_is_format_supported_input(self):
        """Test input format support check."""
        assert EbookConverter.is_format_supported("epub") is True
        assert EbookConverter.is_format_supported("pdf") is True
        assert EbookConverter.is_format_supported("lit") is False

    def test_is_format_supported_output(self):
        """Test output format support check."""
        assert EbookConverter.is_format_supported("mobi", for_output=True) is True
        assert EbookConverter.is_format_supported("docx", for_output=True) is False

    def test_get_supported_formats(self):
        """Test getting supported formats."""
        input_formats, output_formats = EbookConverter.get_supported_formats()
        assert "epub" in input_formats
        assert "pdf" in output_formats

    def test_build_calibre_command(self):
        """Test Calibre command building."""
        converter = EbookConverter()
        cmd = converter._build_calibre_command(
            Path("/tmp/test.epub"),
            Path("/tmp/test.pdf"),
            "pdf",
            None,
            None,
            "a4",
            "36pt",
        )

        assert "ebook-convert" in cmd
        assert "/tmp/test.epub" in cmd
        assert "/tmp/test.pdf" in cmd

    @pytest.mark.asyncio
    async def test_convert_unsupported_format(self):
        """Test conversion with unsupported format raises error."""
        converter = EbookConverter()

        with pytest.raises(Exception) as exc_info:
            await converter.convert("test.epub", "docx")

        assert "not supported" in str(exc_info.value).lower()

    def test_parse_metadata(self):
        """Test metadata parsing."""
        converter = EbookConverter()
        output = "Title: Test Book\nAuthor: Test Author\nLanguage: en"

        metadata = converter._parse_metadata(output)

        assert metadata.get("title") == "Test Book"
        assert metadata.get("author") == "Test Author"
