"""Dependency verification module for converter-mcp.

This module provides functions to verify that required system dependencies are installed
and available for the conversion operations.
"""

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Dict, Tuple


class DependencyError(RuntimeError):
    """Raised when a required dependency is missing or unavailable."""

    pass


async def check_ffmpeg() -> Tuple[bool, str]:
    """Check if FFmpeg is installed and return version information.

    Returns:
        Tuple of (is_installed: bool, message: str)
    """
    if not shutil.which("ffmpeg"):
        return False, (
            "FFmpeg not found. Install with:\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  Fedora/RHEL: sudo dnf install ffmpeg\n"
            "  macOS: brew install ffmpeg\n"
            "  Windows: Download from https://ffmpeg.org/download.html"
        )

    # Run ffmpeg -version and parse version information
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    # Get the first line which contains the version info
    version_line = stdout.decode().split("\n")[0]

    return True, version_line


async def check_calibre() -> Tuple[bool, str]:
    """Check if Calibre ebook-convert is available.

    Returns:
        Tuple of (is_installed: bool, message: str)
    """
    if not shutil.which("ebook-convert"):
        return False, (
            "Calibre not found. Install from:\n"
            "  https://calibre-ebook.com/download_linux\n"
            "  Ubuntu/Debian: sudo apt install calibre\n"
            "  Fedora/RHEL: sudo dnf install calibre\n"
            "  macOS: brew install --cask calibre"
        )

    # Check version by running ebook-convert --version
    proc = await asyncio.create_subprocess_exec(
        "ebook-convert",
        "--version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()

    return True, stdout.decode().strip()


async def check_python_version() -> Tuple[bool, str]:
    """Check if Python version meets requirements.

    Returns:
        Tuple of (is_compatible: bool, message: str)
    """
    py_version = sys.version_info
    py_ok = py_version >= (3, 9)

    # Handle both NamedTuple and tuple formats
    if hasattr(py_version, "major"):
        message = f"Python {py_version.major}.{py_version.minor}.{py_version.micro}"
    else:
        message = f"Python {py_version[0]}.{py_version[1]}.{py_version[2]}"

    if not py_ok:
        message += f" - Requires Python 3.9+"

    return py_ok, message


async def verify_dependencies() -> Dict[str, Dict]:
    """Verify all system dependencies and return status.

    Raises:
        DependencyError: If any critical dependency is missing

    Returns:
        Dictionary with dependency status for:
        - ffmpeg: installed status and message
        - calibre: installed status and message
        - python: version compatibility and message
    """
    results = {}

    # Check FFmpeg
    ffmpeg_ok, ffmpeg_msg = await check_ffmpeg()
    results["ffmpeg"] = {"installed": ffmpeg_ok, "message": ffmpeg_msg}

    # Check Calibre
    calibre_ok, calibre_msg = await check_calibre()
    results["calibre"] = {"installed": calibre_ok, "message": calibre_msg}

    # Check Python version
    py_ok, py_msg = await check_python_version()
    results["python"] = {"compatible": py_ok, "message": py_msg}

    # Raise error if any critical dependency missing
    if not ffmpeg_ok:
        raise DependencyError(f"FFmpeg required: {ffmpeg_msg}")

    if not calibre_ok:
        raise DependencyError(f"Calibre required: {calibre_msg}")

    if not py_ok:
        raise DependencyError(f"Python version too old: {py_msg}")

    return results


async def get_dependency_summary() -> Dict[str, str]:
    """Get a human-readable summary of dependencies.

    Returns:
        Dictionary with dependency name as key and status as value.
        Example: {"ffmpeg": "✓ Installed", "calibre": "✗ Not found", ...}
    """
    results = await verify_dependencies()
    summary = {}

    for dep, info in results.items():
        if dep == "python":
            status = "✓ Compatible" if info["compatible"] else "✗ Not compatible"
        else:
            status = "✓ Installed" if info["installed"] else "✗ Not found"
        summary[dep] = status

    return summary
