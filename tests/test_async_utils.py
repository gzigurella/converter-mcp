"""Unit tests for async utilities module."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.converter.async_utils import (
    ConcurrencyLimiter,
    SubprocessError,
    SubprocessTimeoutError,
    TempFileManager,
    cleanup_orphaned_processes,
    kill_process_tree,
    safe_subprocess,
)


class TestConcurrencyLimiter:
    """Test cases for ConcurrencyLimiter."""

    @pytest.mark.asyncio
    async def test_limit_concurrent_operations(self):
        """Test that limiter respects max concurrent operations."""
        limiter = ConcurrencyLimiter(max_concurrent=2)
        active_count = 0
        max_active = 0

        async def worker():
            nonlocal active_count, max_active
            async with limiter:
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.1)
                active_count -= 1

        await asyncio.gather(*[worker() for _ in range(5)])

        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Test manual acquire and release."""
        limiter = ConcurrencyLimiter(max_concurrent=1)
        await limiter.acquire()
        limiter.release()

        await limiter.acquire()
        limiter.release()


class TestSafeSubprocess:
    """Test cases for safe_subprocess."""

    @pytest.mark.asyncio
    async def test_successful_subprocess(self):
        """Test successful subprocess execution."""
        returncode, stdout, stderr = await safe_subprocess(["echo", "hello"], timeout=5)

        assert returncode == 0
        assert "hello" in stdout
        assert stderr == ""

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self):
        """Test that subprocess timeout raises SubprocessTimeoutError."""
        with pytest.raises(SubprocessTimeoutError) as exc_info:
            await safe_subprocess(["sleep", "10"], timeout=1)

        assert "sleep" in str(exc_info.value).lower()
        assert "1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subprocess_with_nonzero_exit(self):
        """Test that non-zero exit raises SubprocessError by default."""
        with pytest.raises(SubprocessError) as exc_info:
            await safe_subprocess(["sh", "-c", "exit 1"], timeout=5)

        assert "1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_subprocess_ignore_nonzero_exit(self):
        """Test that non-zero exit is not raised when check_returncode=False."""
        returncode, stdout, stderr = await safe_subprocess(
            ["sh", "-c", "exit 1"], timeout=5, check_returncode=False
        )

        assert returncode == 1

    @pytest.mark.asyncio
    async def test_subprocess_stderr_captured(self):
        """Test that stderr is captured."""
        returncode, stdout, stderr = await safe_subprocess(
            ["sh", "-c", "echo error >&2"], timeout=5
        )

        assert "error" in stderr

    @pytest.mark.asyncio
    async def test_no_output_capture(self):
        """Test subprocess without output capture."""
        returncode, stdout, stderr = await safe_subprocess(
            ["true"], timeout=5, capture_output=False
        )

        assert returncode == 0
        assert stdout == ""
        assert stderr == ""


class TestTempFileManager:
    """Test cases for TempFileManager."""

    def test_create_and_cleanup_file(self):
        """Test temp file creation and cleanup."""
        with TempFileManager() as manager:
            temp_file = manager.create_file()
            assert temp_file.exists()

            with open(temp_file, "w") as f:
                f.write("test content")

            assert temp_file.read_text() == "test content"

        assert not temp_file.exists()

    def test_create_and_cleanup_directory(self):
        """Test temp directory creation and cleanup."""
        with TempFileManager() as manager:
            temp_dir = manager.create_dir()
            assert temp_dir.exists()
            assert temp_dir.is_dir()

            test_file = temp_dir / "test.txt"
            test_file.write_text("test")

        assert not temp_dir.exists()

    def test_multiple_temp_files(self):
        """Test multiple temp files in the same manager."""
        with TempFileManager() as manager:
            files = [manager.create_file() for _ in range(3)]
            for f in files:
                assert f.exists()

        for f in files:
            assert not f.exists()

    def test_custom_prefix_suffix(self):
        """Test custom prefix and suffix for temp files."""
        with TempFileManager(prefix="test_", suffix=".tmp") as manager:
            temp_file = manager.create_file()
            assert temp_file.name.startswith("test_")
            assert temp_file.name.endswith(".tmp")

    def test_cleanup_exception_handling(self):
        """Test that cleanup handles exceptions gracefully."""
        with TempFileManager() as manager:
            temp_file = manager.create_file()
            temp_file.unlink()

        manager.cleanup()


class TestKillProcessTree:
    """Test cases for kill_process_tree."""

    @pytest.mark.asyncio
    async def test_kill_nonexistent_process(self):
        """Test killing a nonexistent process."""
        use_high_pid = 9999999
        await kill_process_tree(use_high_pid)


class TestCleanupOrphanedProcesses:
    """Test cases for cleanup_orphaned_processes."""

    @pytest.mark.asyncio
    async def test_cleanup_with_pkill_available(self):
        """Test cleanup when pkill is available."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock(return_value=0)
            mock_proc.returncode = 0
            mock_subprocess.return_value = mock_proc

            await cleanup_orphaned_processes(pattern="test")

            mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_pkill(self):
        """Test cleanup when pkill is not available."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            await cleanup_orphaned_processes()


class TestSubprocessError:
    """Test cases for SubprocessError."""

    def test_error_message(self):
        """Test SubprocessError message formatting."""
        error = SubprocessError(["echo", "test"], 1, "stderr output")
        assert "1" in str(error)
        assert "stderr output" in str(error)

    def test_error_without_stderr(self):
        """Test SubprocessError without stderr."""
        error = SubprocessError(["echo", "test"], 1)
        assert "1" in str(error)


class TestSubprocessTimeoutError:
    """Test cases for SubprocessTimeoutError."""

    def test_timeout_error_message(self):
        """Test SubprocessTimeoutError message formatting."""
        error = SubprocessTimeoutError(["sleep", "10"], 5)
        assert "5" in str(error)
        assert "sleep" in str(error)
