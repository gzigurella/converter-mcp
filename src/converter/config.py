"""Configuration management for the converter server."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ConverterConfig:
    """Configuration settings for the converter."""

    max_concurrent: int = field(default_factory=lambda: min(4, os.cpu_count() or 4))
    default_output_dir: Optional[Path] = None
    min_disk_space_mb: int = 100
    default_quality: str = "medium"
    video_timeout: int = 3600
    audio_timeout: int = 1800
    ebook_timeout: int = 600
    image_timeout: int = 300

    temp_dir: Optional[Path] = None

    log_level: str = "INFO"
    log_file: Optional[Path] = None

    def __post_init__(self):
        if self.temp_dir is None:
            self.temp_dir = Path(os.environ.get("CONVERTER_TEMP_DIR", ""))

        if isinstance(self.default_output_dir, str):
            self.default_output_dir = Path(self.default_output_dir)

        if isinstance(self.temp_dir, str):
            self.temp_dir = Path(self.temp_dir)

        if isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

    @classmethod
    def from_env(cls) -> "ConverterConfig":
        """Load configuration from environment variables."""
        return cls(
            max_concurrent=int(
                os.environ.get("CONVERTER_MAX_CONCURRENT", min(4, os.cpu_count() or 4))
            ),
            default_output_dir=Path(p) if (p := os.environ.get("CONVERTER_OUTPUT_DIR")) else None,
            min_disk_space_mb=int(os.environ.get("CONVERTER_MIN_DISK_SPACE_MB", 100)),
            default_quality=os.environ.get("CONVERTER_DEFAULT_QUALITY", "medium"),
            video_timeout=int(os.environ.get("CONVERTER_VIDEO_TIMEOUT", 3600)),
            audio_timeout=int(os.environ.get("CONVERTER_AUDIO_TIMEOUT", 1800)),
            ebook_timeout=int(os.environ.get("CONVERTER_EBOOK_TIMEOUT", 600)),
            image_timeout=int(os.environ.get("CONVERTER_IMAGE_TIMEOUT", 300)),
            log_level=os.environ.get("CONVERTER_LOG_LEVEL", "INFO"),
            log_file=Path(p) if (p := os.environ.get("CONVERTER_LOG_FILE")) else None,
        )

    def get_timeout_for_format(self, format_name: str) -> int:
        """Get timeout for a specific format category."""
        format_lower = format_name.lower()

        if format_lower in ("mp4", "avi", "mov", "webm", "mkv"):
            return self.video_timeout
        elif format_lower in ("mp3", "wav", "flac", "aac", "ogg"):
            return self.audio_timeout
        elif format_lower in ("epub", "pdf", "mobi", "azw3"):
            return self.ebook_timeout
        else:
            return self.image_timeout


config = ConverterConfig.from_env()
