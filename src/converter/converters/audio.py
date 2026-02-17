"""
Audio converter using FFmpeg.

Supports conversions between common audio formats:
- MP3, WAV, FLAC, AAC, OGG, M4A
"""

import asyncio
from pathlib import Path
from typing import Optional

from ..async_utils import safe_subprocess, concurrency_limiter
from ..file_manager import FileManager
from ..logging_config import ConversionError, FormatNotSupportedError, get_logger

logger = get_logger("converters.audio")

SUPPORTED_INPUT_FORMATS = {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "aiff"}
SUPPORTED_OUTPUT_FORMATS = {"mp3", "wav", "flac", "aac", "ogg", "m4a"}

QUALITY_PRESETS = {
    "low": {"bitrate": "128k", "sample_rate": "44100"},
    "medium": {"bitrate": "192k", "sample_rate": "44100"},
    "high": {"bitrate": "320k", "sample_rate": "48000"},
}

CODEC_MAP = {
    "mp3": "libmp3lame",
    "wav": "pcm_s16le",
    "flac": "flac",
    "aac": "aac",
    "ogg": "libvorbis",
    "m4a": "aac",
}


class AudioConverter:
    """Convert audio files between formats using FFmpeg."""

    def __init__(self, file_manager: Optional[FileManager] = None):
        self.file_manager = file_manager or FileManager()

    @staticmethod
    def is_format_supported(format_name: str, for_output: bool = False) -> bool:
        """Check if a format is supported."""
        format_lower = format_name.lower()
        if for_output:
            return format_lower in SUPPORTED_OUTPUT_FORMATS
        return format_lower in SUPPORTED_INPUT_FORMATS

    @staticmethod
    def get_supported_formats() -> tuple[set, set]:
        """Get supported input and output formats."""
        return SUPPORTED_INPUT_FORMATS.copy(), SUPPORTED_OUTPUT_FORMATS.copy()

    async def convert(
        self,
        source_path: str | Path,
        target_format: str,
        output_path: Optional[Path] = None,
        quality: str = "medium",
        bitrate: Optional[str] = None,
        sample_rate: Optional[int] = None,
    ) -> Path:
        """
        Convert an audio file to the target format.

        Args:
            source_path: Path to source audio
            target_format: Target format (mp3, wav, flac, aac, ogg, m4a)
            output_path: Optional output path (auto-generated if not provided)
            quality: Quality preset (low, medium, high)
            bitrate: Optional bitrate override (e.g., "192k")
            sample_rate: Optional sample rate override (e.g., 44100)

        Returns:
            Path to the converted audio file

        Raises:
            FormatNotSupportedError: If format is not supported
            ConversionError: If conversion fails
        """
        source = Path(source_path)
        target_format = target_format.lower()

        if not self.is_format_supported(target_format, for_output=True):
            raise FormatNotSupportedError(
                f"Output format '{target_format}' is not supported",
                suggestion=f"Supported formats: {', '.join(sorted(SUPPORTED_OUTPUT_FORMATS))}",
            )

        if output_path is None:
            output_path = self.file_manager.resolve_output_path(source, target_format)

        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])
        codec = CODEC_MAP.get(target_format, "copy")

        actual_bitrate = bitrate or preset["bitrate"]
        actual_sample_rate = sample_rate or int(preset["sample_rate"])

        cmd = self._build_ffmpeg_command(
            source, output_path, codec, actual_bitrate, actual_sample_rate, target_format
        )

        async with concurrency_limiter:
            try:
                returncode, stdout, stderr = await safe_subprocess(cmd, timeout=1800)

                if returncode != 0:
                    raise ConversionError(
                        f"Audio conversion failed",
                        suggestion=f"Check if source file is valid. FFmpeg stderr: {stderr[-500:]}",
                    )

            except asyncio.TimeoutError:
                raise ConversionError(
                    "Audio conversion timed out", suggestion="Try a lower quality preset"
                )

        logger.info(f"Converted {source} -> {output_path}")
        return output_path

    def _build_ffmpeg_command(
        self,
        source: Path,
        output: Path,
        codec: str,
        bitrate: str,
        sample_rate: int,
        target_format: str,
    ) -> list[str]:
        """Build FFmpeg command for audio conversion."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-acodec",
            codec,
            "-b:a",
            bitrate,
            "-ar",
            str(sample_rate),
        ]

        if target_format == "mp3":
            cmd.extend(["-id3v2_version", "3"])

        cmd.append(str(output))
        return cmd

    async def get_audio_info(self, source_path: str | Path) -> dict:
        """
        Get information about an audio file using ffprobe.

        Args:
            source_path: Path to audio file

        Returns:
            Dictionary with audio information
        """
        source = Path(source_path)

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        ]

        returncode, stdout, stderr = await safe_subprocess(cmd, timeout=30)

        if returncode != 0:
            raise ConversionError(f"Failed to get audio info: {stderr}")

        import json

        return json.loads(stdout)
