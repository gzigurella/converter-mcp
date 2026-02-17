"""
Tests for video converter.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.converter.converters.video import (
    VideoConverter,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)


class TestVideoConverter:
    """Tests for VideoConverter class."""

    def test_is_format_supported_input(self):
        """Test input format support check."""
        assert VideoConverter.is_format_supported("mp4") is True
        assert VideoConverter.is_format_supported("avi") is True
        assert VideoConverter.is_format_supported("rm") is False

    def test_is_format_supported_output(self):
        """Test output format support check."""
        assert VideoConverter.is_format_supported("webm", for_output=True) is True
        assert VideoConverter.is_format_supported("flv", for_output=True) is False

    def test_get_supported_formats(self):
        """Test getting supported formats."""
        input_formats, output_formats = VideoConverter.get_supported_formats()
        assert "mp4" in input_formats
        assert "webm" in output_formats

    def test_build_ffmpeg_command(self):
        """Test FFmpeg command building."""
        converter = VideoConverter()
        cmd = converter._build_ffmpeg_command(
            Path("/tmp/test.mp4"),
            Path("/tmp/test.webm"),
            "libvpx-vp9",
            "libopus",
            {"crf": "28", "preset": "faster"},
        )

        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "/tmp/test.mp4" in cmd
        assert "/tmp/test.webm" in cmd

    @pytest.mark.asyncio
    async def test_convert_unsupported_format(self):
        """Test conversion with unsupported format raises error."""
        converter = VideoConverter()

        with pytest.raises(Exception) as exc_info:
            await converter.convert("test.mp4", "rm")

        assert "not supported" in str(exc_info.value).lower()
