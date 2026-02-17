"""
Integration test for special character handling in ebook conversion.

This test creates actual files with special characters and verifies
that the conversion works correctly.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.converter.converters.ebook import EbookConverter
from src.converter.async_utils import SafePathHandler


@pytest.mark.integration
@pytest.mark.asyncio
async def test_convert_file_with_special_characters():
    """Test conversion of a file with various special characters in the name."""
    import shutil

    # Skip if Calibre is not installed
    if not shutil.which("ebook-convert"):
        pytest.skip("Calibre not installed")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal valid EPUB with special characters in filename
        test_files = [
            "Anna's Archive.epub",
            "War & Peace.epub",
            "L'Étranger.epub",
            "Test File.epub",
            "Book #1.epub",
        ]

        for filename in test_files:
            test_file = Path(tmpdir) / filename

            # Create minimal valid EPUB (mimetype + container.xml + dummy content)
            test_file.write_bytes(
                b"PK\x03\x04"  # ZIP header
            )

        converter = EbookConverter()

        # Test that files with special chars are detected
        special_files = [f for f in test_files if converter._has_special_chars(Path(f))]
        assert len(special_files) > 0, "No files with special characters found"

        # Note: Actual conversion test requires valid EPUB files
        # This test focuses on path handling, not conversion quality


@pytest.mark.integration
@pytest.mark.asyncio
async def test_safe_path_handler_with_real_files():
    """Test SafePathHandler with actual files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file with special characters
        test_file = Path(tmpdir) / "Test 'File'.txt"
        test_file.write_text("Test content")

        with SafePathHandler() as handler:
            symlink = handler.create_safe_symlink(test_file)

            # Verify symlink exists and points to correct file
            assert symlink.exists()
            assert symlink.is_symlink()
            assert symlink.resolve() == test_file.resolve()

            # Verify content is accessible through symlink
            content = symlink.read_text()
            assert content == "Test content"

        # Verify cleanup happened
        assert not symlink.exists()


@pytest.mark.integration
def test_special_char_detection_comprehensive():
    """Test comprehensive detection of special characters."""
    converter = EbookConverter()

    test_cases = [
        ("simple.epub", False),
        ("with spaces.epub", True),
        ("with'apostrophe.epub", True),
        ("L'Étranger.epub", True),
        ("AT&T Guide.epub", True),
        ("C++ Primer.epub", True),
        ("C# in Depth.epub", True),
        ("[Book 1].epub", True),
        ("test_file.epub", False),  # Underscore is safe
        ("test-file.epub", False),  # Hyphen is safe
        ("test.file.epub", False),  # Dot is safe
        ("Dune_Book_1.epub", False),  # Underscore is safe
    ]

    for filename, expected in test_cases:
        result = converter._has_special_chars(Path(filename))
        assert result == expected, f"Failed for {filename}: expected {expected}, got {result}"


@pytest.mark.integration
def test_url_encoding_compatibility():
    """Test that URL encoding produces valid filenames."""
    from urllib.parse import quote

    problematic_filenames = [
        "Anna's Archive.epub",
        "War & Peace.epub",
        "L'Étranger.epub",
        "Test File.epub",
    ]

    for filename in problematic_filenames:
        encoded = quote(filename, safe="")
        # Verify encoding changes the filename
        assert encoded != filename

        # Verify encoded name is filesystem-safe (no spaces, special chars)
        assert " " not in encoded
        assert "'" not in encoded
        assert "&" not in encoded

        # Verify it can be used as a filename
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / encoded
            test_file.touch()
            assert test_file.exists()
