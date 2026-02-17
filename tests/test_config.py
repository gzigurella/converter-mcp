"""Tests for configuration management."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from src.converter.config import ConverterConfig, config


class TestConverterConfig:
    """Tests for ConverterConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        cfg = ConverterConfig()

        assert cfg.default_quality == "medium"
        assert cfg.min_disk_space_mb == 100
        assert cfg.video_timeout == 3600
        assert cfg.audio_timeout == 1800
        assert cfg.ebook_timeout == 600
        assert cfg.image_timeout == 300
        assert cfg.log_level == "INFO"

    def test_max_concurrent_defaults_to_cpu_count(self):
        """Test max_concurrent defaults based on CPU count."""
        cfg = ConverterConfig()

        expected = min(4, os.cpu_count() or 4)
        assert cfg.max_concurrent == expected

    def test_custom_values(self):
        """Test custom configuration values."""
        cfg = ConverterConfig(
            max_concurrent=8,
            default_quality="high",
            min_disk_space_mb=500,
            video_timeout=7200,
        )

        assert cfg.max_concurrent == 8
        assert cfg.default_quality == "high"
        assert cfg.min_disk_space_mb == 500
        assert cfg.video_timeout == 7200

    def test_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CONVERTER_MAX_CONCURRENT": "8",
                "CONVERTER_DEFAULT_QUALITY": "high",
                "CONVERTER_MIN_DISK_SPACE_MB": "200",
                "CONVERTER_VIDEO_TIMEOUT": "7200",
                "CONVERTER_LOG_LEVEL": "DEBUG",
            },
        ):
            cfg = ConverterConfig.from_env()

            assert cfg.max_concurrent == 8
            assert cfg.default_quality == "high"
            assert cfg.min_disk_space_mb == 200
            assert cfg.video_timeout == 7200
            assert cfg.log_level == "DEBUG"

    def test_get_timeout_for_format(self):
        """Test timeout resolution for different formats."""
        cfg = ConverterConfig(
            video_timeout=3600,
            audio_timeout=1800,
            ebook_timeout=600,
            image_timeout=300,
        )

        assert cfg.get_timeout_for_format("mp4") == 3600
        assert cfg.get_timeout_for_format("webm") == 3600
        assert cfg.get_timeout_for_format("mp3") == 1800
        assert cfg.get_timeout_for_format("flac") == 1800
        assert cfg.get_timeout_for_format("epub") == 600
        assert cfg.get_timeout_for_format("pdf") == 600
        assert cfg.get_timeout_for_format("jpg") == 300
        assert cfg.get_timeout_for_format("png") == 300

    def test_global_config_instance(self):
        """Test global config instance exists."""
        assert config is not None
        assert isinstance(config, ConverterConfig)

    def test_path_conversion(self, tmp_path):
        """Test path string conversion."""
        output_dir = str(tmp_path / "output")
        log_file = str(tmp_path / "converter.log")

        cfg = ConverterConfig(
            default_output_dir=output_dir,
            log_file=log_file,
        )

        assert cfg.default_output_dir == Path(output_dir)
        assert cfg.log_file == Path(log_file)
