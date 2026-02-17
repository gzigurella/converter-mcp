"""Tests for resource monitoring."""

import pytest
from pathlib import Path
import tempfile

from src.converter.monitor import ResourceMonitor, monitor


class TestResourceMonitor:
    """Tests for ResourceMonitor class."""

    def test_monitor_creation(self):
        """Test creating a resource monitor."""
        mon = ResourceMonitor(min_disk_space_mb=200)

        assert mon.min_disk_space_mb == 200

    def test_get_disk_space(self):
        """Test getting disk space information."""
        mon = ResourceMonitor()

        with tempfile.TemporaryDirectory() as tmpdir:
            space = mon.get_disk_space(Path(tmpdir))

            assert "total_gb" in space
            assert "used_gb" in space
            assert "free_gb" in space
            assert "free_mb" in space
            assert space["free_mb"] > 0

    def test_check_disk_space_sufficient(self):
        """Test disk space check when sufficient."""
        mon = ResourceMonitor(min_disk_space_mb=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = mon.check_disk_space(Path(tmpdir), required_mb=1)

            assert result is True

    def test_check_disk_space_insufficient(self):
        """Test disk space check when insufficient."""
        mon = ResourceMonitor(min_disk_space_mb=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(RuntimeError) as exc_info:
                mon.check_disk_space(Path(tmpdir), required_mb=999999999)

            assert "Insufficient disk space" in str(exc_info.value)

    def test_get_memory_usage(self):
        """Test getting memory usage."""
        mon = ResourceMonitor()

        usage = mon.get_memory_usage()

        assert "rss_mb" in usage
        assert "vms_mb" in usage
        assert "percent" in usage
        assert usage["rss_mb"] > 0

    def test_get_cpu_usage(self):
        """Test getting CPU usage."""
        mon = ResourceMonitor()

        usage = mon.get_cpu_usage()

        assert isinstance(usage, float)
        assert 0 <= usage <= 100

    @pytest.mark.asyncio
    async def test_detect_zombies(self):
        """Test zombie process detection."""
        mon = ResourceMonitor()

        zombies = await mon.detect_zombies()

        assert isinstance(zombies, list)

    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self):
        """Test temp file cleanup."""
        mon = ResourceMonitor()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temp files
            for i in range(3):
                (Path(tmpdir) / f"converter_{i}.tmp").touch()

            cleaned = await mon.cleanup_temp_files(Path(tmpdir), pattern="converter_*.tmp")

            assert cleaned == 3

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_directory(self):
        """Test cleanup of nonexistent directory."""
        mon = ResourceMonitor()

        cleaned = await mon.cleanup_temp_files(Path("/nonexistent/path"))

        assert cleaned == 0

    def test_global_monitor_instance(self):
        """Test global monitor instance exists."""
        assert monitor is not None
        assert isinstance(monitor, ResourceMonitor)
