"""
Tests for audio converter.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.converter.converters.audio import (
    AudioConverter,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)


class TestAudioConverter:
    """Tests for AudioConverter class."""

    def test_is_format_supported_input(self):
        """Test input format support check."""
        assert AudioConverter.is_format_supported("mp3") is True
        assert AudioConverter.is_format_supported("wav") is True
        assert AudioConverter.is_format_supported("mid") is False

    def test_is_format_supported_output(self):
        """Test output format support check."""
        assert AudioConverter.is_format_supported("flac", for_output=True) is True
        assert AudioConverter.is_format_supported("ra", for_output=True) is False

    def test_get_supported_formats(self):
        """Test getting supported formats."""
        input_formats, output_formats = AudioConverter.get_supported_formats()
        assert "mp3" in input_formats
        assert "flac" in output_formats

    def test_build_ffmpeg_command(self):
        """Test FFmpeg command building."""
        converter = AudioConverter()
        cmd = converter._build_ffmpeg_command(
            Path("/tmp/test.wav"),
            Path("/tmp/test.mp3"),
            "libmp3lame",
            "192k",
            44100,
            "mp3",
        )

        assert "ffmpeg" in cmd
        assert "-i" in cmd
        assert "/tmp/test.wav" in cmd
        assert "/tmp/test.mp3" in cmd
        assert "-acodec" in cmd

    @pytest.mark.asyncio
    async def test_convert_unsupported_format(self):
        """Test conversion with unsupported format raises error."""
        converter = AudioConverter()

        with pytest.raises(Exception) as exc_info:
            await converter.convert("test.mp3", "mid")

        assert "not supported" in str(exc_info.value).lower()
