"""Resource monitoring and cleanup utilities."""

import asyncio
import logging
import os
import psutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitor system resources during conversions."""

    def __init__(self, min_disk_space_mb: int = 100):
        self.min_disk_space_mb = min_disk_space_mb

    def get_disk_space(self, path: Path) -> dict:
        """Get disk space information for a path."""
        if path.is_file():
            path = path.parent

        usage = psutil.disk_usage(str(path))
        return {
            "total_gb": usage.total / (1024**3),
            "used_gb": usage.used / (1024**3),
            "free_gb": usage.free / (1024**3),
            "free_mb": usage.free / (1024**2),
            "percent_used": usage.percent,
        }

    def check_disk_space(self, path: Path, required_mb: Optional[int] = None) -> bool:
        """Check if there's enough disk space."""
        required = required_mb or self.min_disk_space_mb
        space = self.get_disk_space(path)

        if space["free_mb"] < required:
            raise RuntimeError(
                f"Insufficient disk space: {space['free_mb']:.0f}MB free, {required}MB required"
            )
        return True

    def get_memory_usage(self) -> dict:
        """Get current memory usage."""
        process = psutil.Process()
        mem = process.memory_info()
        return {
            "rss_mb": mem.rss / (1024**2),
            "vms_mb": mem.vms / (1024**2),
            "percent": process.memory_percent(),
        }

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=0.1)

    async def detect_zombies(self) -> list[int]:
        """Detect zombie processes."""
        zombies = []
        for proc in psutil.process_iter(["pid", "status", "name"]):
            try:
                if proc.info["status"] == psutil.STATUS_ZOMBIE:
                    zombies.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return zombies

    async def cleanup_temp_files(self, directory: Path, pattern: str = "converter_*") -> int:
        """Clean up temporary files in a directory."""
        if not directory.exists():
            return 0

        cleaned = 0
        for path in directory.glob(pattern):
            try:
                if path.is_file():
                    path.unlink()
                    cleaned += 1
                elif path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to cleanup {path}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} temp files")

        return cleaned


monitor = ResourceMonitor()
