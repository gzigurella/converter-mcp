"""
Tests for converter router.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.converter.converters.router import (
    ConverterRouter,
    router,
)


class TestConverterRouter:
    """Tests for ConverterRouter class."""

    def test_get_converter_type_image(self):
        """Test image converter type detection."""
        assert ConverterRouter.get_converter_type("jpg", "png") == "image"
        assert ConverterRouter.get_converter_type("gif", "webp") == "image"

    def test_get_converter_type_video(self):
        """Test video converter type detection."""
        assert ConverterRouter.get_converter_type("mp4", "webm") == "video"
        assert ConverterRouter.get_converter_type("avi", "mp4") == "video"

    def test_get_converter_type_audio(self):
        """Test audio converter type detection."""
        assert ConverterRouter.get_converter_type("wav", "mp3") == "audio"
        assert ConverterRouter.get_converter_type("flac", "aac") == "audio"

    def test_get_converter_type_video_to_audio(self):
        """Test video to audio extraction detection."""
        assert ConverterRouter.get_converter_type("mp4", "mp3") == "video"

    def test_get_converter_type_ebook(self):
        """Test ebook converter type detection."""
        assert ConverterRouter.get_converter_type("epub", "pdf") == "ebook"
        assert ConverterRouter.get_converter_type("mobi", "epub") == "ebook"

    def test_get_converter_type_unsupported(self):
        """Test unsupported conversion raises error."""
        with pytest.raises(Exception) as exc_info:
            ConverterRouter.get_converter_type("jpg", "epub")

        assert "not supported" in str(exc_info.value).lower()

    def test_get_supported_conversions(self):
        """Test getting all supported conversions."""
        router = ConverterRouter()
        conversions = router.get_supported_conversions()

        assert "image" in conversions
        assert "video" in conversions
        assert "audio" in conversions
        assert "ebook" in conversions

    def test_is_conversion_supported(self):
        """Test conversion support check."""
        router = ConverterRouter()

        assert router.is_conversion_supported("jpg", "png") is True
        assert router.is_conversion_supported("mp4", "mp3") is True
        assert router.is_conversion_supported("jpg", "epub") is False

    def test_converter_properties(self):
        """Test converter lazy loading."""
        router = ConverterRouter()

        assert router.image is not None
        assert router.video is not None
        assert router.audio is not None
        assert router.ebook is not None

    def test_global_router(self):
        """Test global router instance."""
        assert router is not None
        assert isinstance(router, ConverterRouter)
