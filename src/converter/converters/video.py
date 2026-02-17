"""
Video converter using FFmpeg.

Supports conversions between common video formats:
- MP4, AVI, MOV, WebM, MKV
"""

import asyncio
import re
import shutil
from pathlib import Path
from typing import Callable, Optional, Any

from ..async_utils import safe_subprocess, concurrency_limiter
from ..file_manager import FileManager
from ..logging_config import ConversionError, FormatNotSupportedError, get_logger
from ..progress import ProgressReporter, ProgressStage, get_progress_reporter

logger = get_logger("converters.video")

SUPPORTED_INPUT_FORMATS = {"mp4", "avi", "mov", "webm", "mkv", "wmv", "flv", "m4v"}
SUPPORTED_OUTPUT_FORMATS = {"mp4", "avi", "mov", "webm", "mkv"}

QUALITY_PRESETS = {
    "low": {"crf": "28", "preset": "faster"},
    "medium": {"crf": "23", "preset": "medium"},
    "high": {"crf": "18", "preset": "slow"},
}

CODEC_MAP = {
    "mp4": {"video": "libx264", "audio": "aac"},
    "webm": {"video": "libvpx-vp9", "audio": "libopus"},
    "avi": {"video": "mpeg4", "audio": "mp3"},
    "mov": {"video": "libx264", "audio": "aac"},
    "mkv": {"video": "libx264", "audio": "aac"},
}

_DURATION_REGEX = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})")
_TIME_REGEX = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")


class VideoConverter:
    """Convert videos between formats using FFmpeg."""

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
        codec: Optional[str] = None,
        audio_codec: Optional[str] = None,
        progress_callback: Optional[Callable[[float], Any]] = None,
        progress_reporter: Optional[ProgressReporter] = None,
        job_id: Optional[str] = None,
    ) -> Path:
        """
        Convert a video to the target format.

        Args:
            source_path: Path to source video
            target_format: Target format (mp4, avi, mov, webm, mkv)
            output_path: Optional output path (auto-generated if not provided)
            quality: Quality preset (low, medium, high)
            codec: Optional video codec override
            audio_codec: Optional audio codec override
            progress_callback: Optional callback(percent) for progress updates
            progress_reporter: Optional ProgressReporter for detailed progress
            job_id: Optional job ID for progress tracking

        Returns:
            Path to the converted video

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
        default_codecs = CODEC_MAP.get(target_format, CODEC_MAP["mp4"])

        video_codec = codec or default_codecs["video"]
        audio = audio_codec or default_codecs["audio"]

        cmd = self._build_ffmpeg_command(source, output_path, video_codec, audio, preset)

        # Initialize progress tracking
        use_progress = progress_callback is not None or progress_reporter is not None
        if use_progress and progress_reporter and job_id:
            await progress_reporter.start_job(
                job_id,
                message=f"Converting {source.name} to {target_format}",
                metadata={"source": str(source), "target_format": target_format},
            )
        elif progress_callback:
            progress_callback(0.0)

        async with concurrency_limiter:
            try:
                # Use progress monitoring version if callback provided
                if use_progress:
                    returncode, stdout, stderr = await self._run_with_progress(
                        cmd,
                        progress_callback=progress_callback,
                        progress_reporter=progress_reporter,
                        job_id=job_id,
                    )
                else:
                    returncode, stdout, stderr = await safe_subprocess(cmd, timeout=3600)

                if returncode != 0:
                    if progress_reporter and job_id:
                        await progress_reporter.complete_job(
                            job_id, success=False, message="Conversion failed"
                        )
                    raise ConversionError(
                        f"FFmpeg conversion failed",
                        suggestion=f"Check if source file is valid. FFmpeg stderr: {stderr[-500:]}",
                    )

            except asyncio.TimeoutError:
                if progress_reporter and job_id:
                    await progress_reporter.complete_job(
                        job_id, success=False, message="Conversion timed out"
                    )
                raise ConversionError(
                    "Video conversion timed out",
                    suggestion="Try a lower quality preset or smaller file",
                )

        # Complete progress tracking
        if progress_reporter and job_id:
            await progress_reporter.complete_job(
                job_id, success=True, message=f"Converted to {output_path.name}"
            )
        elif progress_callback:
            progress_callback(100.0)

        logger.info(f"Converted {source} -> {output_path}")
        return output_path

    def _build_ffmpeg_command(
        self,
        source: Path,
        output: Path,
        video_codec: str,
        audio_codec: str,
        preset: dict,
    ) -> list[str]:
        """Build FFmpeg command for conversion."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c:v",
            video_codec,
            "-crf",
            preset["crf"],
            "-preset",
            preset["preset"],
            "-c:a",
            audio_codec,
            str(output),
        ]
        return cmd

    async def _run_with_progress(
        self,
        cmd: list[str],
        progress_callback: Optional[Callable[[float], Any]] = None,
        progress_reporter: Optional[ProgressReporter] = None,
        job_id: Optional[str] = None,
        timeout: int = 3600,
    ) -> tuple[int, str, str]:
        """
        Run FFmpeg with progress monitoring via stderr parsing.

        Parses FFmpeg stderr output to extract duration and current time,
        calculating percentage complete for progress reporting.

        FFmpeg outputs progress to stderr in format:
        frame=  123 fps= 45 q=28.0 size=    1234kB time=00:00:05.00 bitrate= 2000.0kbits/s speed=2.00x

        Progress calculation:
        1. Extract total duration from "Duration: HH:MM:SS.ms" pattern
        2. Extract current time from "time=HH:MM:SS.ms" pattern
        3. Calculate percentage: (current_time / total_duration) * 100

        Args:
            cmd: FFmpeg command list to execute
            progress_callback: Optional callback(percent) for progress updates
            progress_reporter: Optional ProgressReporter for detailed progress
            job_id: Optional job ID for progress reporter
            timeout: Maximum execution time in seconds

        Returns:
            Tuple of (returncode, stdout, stderr)

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
            Exception: If FFmpeg process fails
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_chunks = []
        stderr_chunks = []
        total_duration = None

        try:
            while True:
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )

                    if stdout_data:
                        stdout_chunks.append(stdout_data)
                    if stderr_data:
                        stderr_text = stderr_data.decode("utf-8", errors="replace")
                        stderr_chunks.append(stderr_data)

                        if total_duration is None:
                            duration_match = _DURATION_REGEX.search(stderr_text)
                            if duration_match:
                                h, m, s, ms = map(int, duration_match.groups())
                                total_duration = h * 3600 + m * 60 + s + ms / 100

                        time_match = _TIME_REGEX.search(stderr_text)
                        if time_match and total_duration:
                            h, m, s, ms = map(int, time_match.groups())
                            current_time = h * 3600 + m * 60 + s + ms / 100
                            percent = min(100.0, (current_time / total_duration) * 100.0)

                            if progress_callback:
                                try:
                                    result = progress_callback(percent)
                                    if asyncio.iscoroutine(result):
                                        await result
                                except Exception as e:
                                    logger.debug(f"Progress callback error: {e}")

                            if progress_reporter and job_id:
                                await progress_reporter.update_progress(
                                    job_id, progress=percent, message=f"Processing: {percent:.1f}%"
                                )

                    if process.returncode is not None:
                        break

                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    raise

        except Exception:
            process.kill()
            await process.wait()
            raise

        stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")

        return process.returncode or 0, stdout, stderr

    async def extract_audio(
        self,
        source_path: str | Path,
        output_path: Optional[Path] = None,
        audio_format: str = "mp3",
        bitrate: str = "192k",
    ) -> Path:
        """
        Extract audio from a video file.

        Args:
            source_path: Path to source video
            output_path: Optional output path for audio file
            audio_format: Audio format (mp3, aac, wav, flac)
            bitrate: Audio bitrate

        Returns:
            Path to the extracted audio file
        """
        source = Path(source_path)

        if output_path is None:
            output_path = self.file_manager.resolve_output_path(source, audio_format)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-acodec",
            "libmp3lame" if audio_format == "mp3" else "copy",
            "-b:a",
            bitrate,
            str(output_path),
        ]

        async with concurrency_limiter:
            returncode, stdout, stderr = await safe_subprocess(cmd, timeout=1800)

            if returncode != 0:
                raise ConversionError(f"Audio extraction failed: {stderr[-200:]}")

        logger.info(f"Extracted audio from {source} -> {output_path}")
        return output_path
