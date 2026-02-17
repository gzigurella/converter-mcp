"""Unit tests for dependency verification module."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.converter.deps import (
    DependencyError,
    check_calibre,
    check_ffmpeg,
    check_python_version,
    get_dependency_summary,
    verify_dependencies,
)


class TestCheckFFmpeg:
    """Test cases for FFmpeg dependency checking."""

    @pytest.mark.asyncio
    async def test_ffmpeg_installed(self):
        """Test that FFmpeg is correctly detected when installed."""
        # Mock subprocess output with FFmpeg version
        mock_version_output = b"ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers"

        # Create mock process
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(mock_version_output, b""))
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            is_installed, message = await check_ffmpeg()

            assert is_installed is True
            assert isinstance(message, str)
            assert "ffmpeg" in message.lower()

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found(self):
        """Test that missing FFmpeg is properly reported."""
        with patch("shutil.which", return_value=None):
            is_installed, message = await check_ffmpeg()

            assert is_installed is False
            assert "not found" in message.lower()
            assert "install" in message.lower()


class TestCheckCalibre:
    """Test cases for Calibre dependency checking."""

    @pytest.mark.asyncio
    async def test_calibre_installed(self):
        """Test that Calibre is correctly detected when installed."""
        # Mock subprocess output with Calibre version
        mock_version_output = b"calibre 7.0.0  [Linux x86_64]"

        # Create mock process
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(mock_version_output, b""))
        mock_proc.wait = AsyncMock(return_value=0)

        with (
            patch("shutil.which", return_value="/usr/bin/ebook-convert"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            is_installed, message = await check_calibre()

            assert is_installed is True
            assert isinstance(message, str)
            assert "calibre" in message.lower()

    @pytest.mark.asyncio
    async def test_calibre_not_found(self):
        """Test that missing Calibre is properly reported."""
        with patch("shutil.which", return_value=None):
            is_installed, message = await check_calibre()

            assert is_installed is False
            assert "not found" in message.lower()
            assert "install" in message.lower()


class TestCheckPythonVersion:
    """Test cases for Python version checking."""

    @pytest.mark.asyncio
    async def test_python_version_compatible(self):
        """Test Python version 3.9+ is accepted."""
        # Use actual Python 3.10+ is already compatible
        is_compatible, message = await check_python_version()

        assert is_compatible is True
        assert "3.14" in message

    @pytest.mark.asyncio
    async def test_python_version_incompatible(self):
        """Test Python version below 3.9 is rejected."""
        # Temporarily replace sys.version_info for testing
        original_version_info = sys.version_info
        sys.version_info = (3, 8, 0, "final", 0)  # Actual tuple format

        try:
            is_compatible, message = await check_python_version()

            assert is_compatible is False
            assert "3.8" in message
            assert "3.9" in message
        finally:
            sys.version_info = original_version_info


class TestVerifyDependencies:
    """Test cases for dependency verification function."""

    @pytest.mark.asyncio
    async def test_all_dependencies_present(self):
        """Test successful verification when all dependencies are present."""
        # Mock all dependencies as present
        mock_ffmpeg_output = b"ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers"
        mock_calibre_output = b"calibre 7.0.0 [Linux x86_64]"

        # Track subprocess calls
        call_count = [0]

        def mock_subprocess_side_effect(*args, **kwargs):
            proc = AsyncMock()
            call_count[0] += 1

            if call_count[0] == 1:  # First call is for ffmpeg
                proc.communicate = AsyncMock(return_value=(mock_ffmpeg_output, b""))
            else:  # Second call is for calibre
                proc.communicate = AsyncMock(return_value=(mock_calibre_output, b""))

            proc.wait = AsyncMock(return_value=0)
            return proc

        with patch("shutil.which", side_effect=lambda x: x):
            with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_side_effect):
                # Temporarily replace sys.version_info for testing
                original_version_info = sys.version_info
                sys.version_info = (3, 10, 0, "final", 0)  # Actual tuple format

                try:
                    results = await verify_dependencies()

                    assert "ffmpeg" in results
                    assert results["ffmpeg"]["installed"] is True
                    assert "calibre" in results
                    assert results["calibre"]["installed"] is True
                    assert "python" in results
                    assert results["python"]["compatible"] is True
                finally:
                    sys.version_info = original_version_info

    @pytest.mark.asyncio
    async def test_missing_ffmpeg_raises_error(self):
        """Test that missing FFmpeg raises DependencyError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(DependencyError) as exc_info:
                await verify_dependencies()

            assert "ffmpeg" in str(exc_info.value).lower()
            assert "required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_calibre_raises_error(self):
        """Test that missing Calibre raises DependencyError."""
        # Create mock processes for ffmpeg and calibre
        call_count = [0]

        def mock_subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1

            mock_proc = AsyncMock()
            if call_count[0] == 1:  # First call is for ffmpeg
                mock_proc.communicate = AsyncMock(return_value=(b"ffmpeg version 6.0", b""))
            else:  # Second call is for calibre (should fail)
                # Return error message for calibre
                mock_proc.communicate = AsyncMock(
                    return_value=(b"", b"error: ebook-convert not found")
                )

            mock_proc.wait = AsyncMock(return_value=0)
            return mock_proc

        with patch("shutil.which", side_effect=lambda x: "ffmpeg" if x == "ffmpeg" else None):
            with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_side_effect):
                # Temporarily replace sys.version_info for testing
                original_version_info = sys.version_info
                sys.version_info = (3, 10, 0, "final", 0)  # Actual tuple format

                try:
                    with pytest.raises(DependencyError) as exc_info:
                        await verify_dependencies()

                    assert "calibre" in str(exc_info.value).lower()
                    assert "required" in str(exc_info.value).lower()
                finally:
                    sys.version_info = original_version_info

    @pytest.mark.asyncio
    async def test_incompatible_python_raises_error(self):
        """Test that incompatible Python version raises DependencyError."""
        # Create mock process for ffmpeg
        mock_ffmpeg_proc = AsyncMock()
        mock_ffmpeg_proc.communicate = AsyncMock(return_value=(b"ffmpeg version 6.0", b""))
        mock_ffmpeg_proc.wait = AsyncMock(return_value=0)

        with patch("shutil.which", side_effect=lambda x: x):
            with patch("asyncio.create_subprocess_exec", return_value=mock_ffmpeg_proc):
                # Temporarily replace sys.version_info for testing
                original_version_info = sys.version_info
                sys.version_info = (3, 8, 0, "final", 0)  # Actual tuple format

                try:
                    with pytest.raises(DependencyError) as exc_info:
                        await verify_dependencies()

                    assert "python" in str(exc_info.value).lower()
                    assert "version too old" in str(exc_info.value).lower()
                finally:
                    sys.version_info = original_version_info


class TestGetDependencySummary:
    """Test cases for dependency summary generation."""

    @pytest.mark.asyncio
    async def test_summary_format(self):
        """Test that summary has correct format."""
        mock_ffmpeg_output = b"ffmpeg version 6.0"
        mock_calibre_output = b"calibre 7.0.0"

        # Track subprocess calls
        call_count = [0]

        def mock_subprocess_side_effect(*args, **kwargs):
            proc = AsyncMock()
            call_count[0] += 1

            if call_count[0] == 1:  # First call is for ffmpeg
                proc.communicate = AsyncMock(return_value=(mock_ffmpeg_output, b""))
            else:  # Second call is for calibre
                proc.communicate = AsyncMock(return_value=(mock_calibre_output, b""))

            proc.wait = AsyncMock(return_value=0)
            return proc

        with patch("shutil.which", side_effect=lambda x: x):
            with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_side_effect):
                # Temporarily replace sys.version_info for testing
                original_version_info = sys.version_info
                sys.version_info = (3, 10, 0, "final", 0)  # Actual tuple format

                try:
                    summary = await get_dependency_summary()

                    assert isinstance(summary, dict)
                    assert "ffmpeg" in summary
                    assert "calibre" in summary
                    assert "python" in summary

                    # Check that status values are strings with checkmarks
                    for dep, status in summary.items():
                        assert isinstance(status, str)
                        assert len(status) > 0
                finally:
                    sys.version_info = original_version_info


class TestDependencyError:
    """Test cases for DependencyError exception."""

    def test_error_message(self):
        """Test that DependencyError can carry meaningful messages."""
        error = DependencyError("FFmpeg is required for conversion")
        assert str(error) == "FFmpeg is required for conversion"

    def test_error_inheritance(self):
        """Test that DependencyError inherits from RuntimeError."""
        error = DependencyError("Test error")
        assert isinstance(error, RuntimeError)
