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
from src.converter.async_utils import SafePathHandler


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

    def test_has_special_chars(self):
        """Test detection of special characters in paths."""
        converter = EbookConverter()

        # Simple filename - no special chars
        simple = Path("/tmp/test.epub")
        assert not converter._has_special_chars(simple)

        # Filename with apostrophe
        apostrophe = Path("/tmp/Anna's Book.epub")
        assert converter._has_special_chars(apostrophe)

        # Filename with spaces
        spaces = Path("/tmp/My Book.epub")
        assert converter._has_special_chars(spaces)

        # Filename with unicode
        unicode = Path("/tmp/L'Étranger.epub")
        assert converter._has_special_chars(unicode)

        # Filename with ampersand
        ampersand = Path("/tmp/AT&T Guide.epub")
        assert converter._has_special_chars(ampersand)

    def test_ensure_safe_source(self):
        """Test safe path handling for special characters."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.epub"
            test_file.touch()

            converter = EbookConverter()

            # Test with normal filename (no special chars)
            safe_path, created = converter._ensure_safe_source(test_file)
            assert not created
            assert safe_path == test_file

            # Test with special characters
            special_file = Path(tmpdir) / "Anna's Book.epub"
            special_file.touch()

            safe_path, created = converter._ensure_safe_source(special_file)
            assert created
            assert safe_path != special_file
            assert safe_path.is_symlink()

            # Cleanup should remove symlink
            converter.cleanup()
            assert not safe_path.exists()

    def test_safe_path_handler(self):
        """Test SafePathHandler utility."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test file.epub"
            test_file.touch()

            with SafePathHandler() as handler:
                # Create symlink
                symlink = handler.create_safe_symlink(test_file)
                assert symlink.exists()
                assert symlink.is_symlink()

                # Read through symlink should work
                assert symlink.resolve() == test_file

            # After context exit, symlink should be cleaned up
            assert not symlink.exists()
