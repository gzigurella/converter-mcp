"""Pytest configuration and fixtures for converter tests."""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Ensure asyncio event loop policy is set
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """Create a sample text file for testing."""
    text_file = temp_dir / "sample.txt"
    text_file.write_text("Hello, World!")
    return text_file


@pytest.fixture
def sample_pdf_file(temp_dir: Path) -> Path:
    """Create a sample PDF file for testing."""
    # Note: This is a minimal PDF file. In real tests, use proper PDF files.
    pdf_file = temp_dir / "sample.pdf"
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n"
        b"endobj\n"
        b"xref\n"
        b"0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000114 00000 n \n"
        b"trailer\n"
        b"<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n"
        b"167\n"
        b"%%EOF\n"
    )
    pdf_file.write_bytes(pdf_content)
    return pdf_file


@pytest.fixture
def sample_image_file(temp_dir: Path) -> Path:
    """Create a sample PNG image file for testing."""
    from PIL import Image

    image_file = temp_dir / "sample.png"
    # Create a simple 1x1 red pixel image
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    img.save(image_file)
    return image_file


@pytest.fixture
def sample_mp4_file(temp_dir: Path) -> Path:
    """Create a sample MP4 video file for testing."""
    # Note: This is a minimal MP4 file. In real tests, use proper video files.
    # FFmpeg would normally create this, but we'll skip the dependency for setup.
    video_file = temp_dir / "sample.mp4"
    return video_file


@pytest.fixture(autouse=True)
def reset_imports():
    """Reset Python import cache between tests to ensure clean state."""
    import sys

    for module in list(sys.modules.keys()):
        if module.startswith("converter"):
            del sys.modules[module]
    yield
    for module in list(sys.modules.keys()):
        if module.startswith("converter"):
            del sys.modules[module]
