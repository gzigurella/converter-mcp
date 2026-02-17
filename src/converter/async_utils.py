"""Async utilities for subprocess management and resource cleanup."""

import asyncio
import logging
import os
import signal
import tempfile
import threading
from pathlib import Path
from typing import Callable, Awaitable
from urllib.parse import quote

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    """Semaphore-based concurrency control for conversions."""

    def __init__(self, max_concurrent: int = 4):
        self._max_concurrent = max_concurrent
        self._local = threading.local()

    async def acquire(self):
        """Acquire the semaphore."""
        sem = self._get_semaphore()
        await sem.acquire()
        return self

    def release(self):
        """Release the semaphore."""
        sem = self._get_semaphore()
        sem.release()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.release()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get semaphore for current event loop."""
        import threading

        try:
            loop = asyncio.get_running_loop()
            loop_id = id(loop)
            if not hasattr(self._local, "semaphores"):
                self._local.semaphores = {}
            if loop_id not in self._local.semaphores:
                self._local.semaphores[loop_id] = asyncio.Semaphore(self._max_concurrent)
            return self._local.semaphores[loop_id]
        except RuntimeError:
            return asyncio.Semaphore(self._max_concurrent)


class SubprocessTimeoutError(RuntimeError):
    """Raised when a subprocess times out."""

    def __init__(self, cmd: list[str], timeout: int):
        self.cmd = cmd
        self.timeout = timeout
        super().__init__(f"Subprocess timed out after {timeout}s: {' '.join(cmd)}")


class SubprocessError(RuntimeError):
    """Raised when a subprocess exits with non-zero status."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str = ""):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        msg = f"Subprocess failed with code {returncode}: {' '.join(cmd)}"
        if stderr:
            msg += f"\nstderr: {stderr}"
        super().__init__(msg)


async def safe_subprocess(
    cmd: list[str],
    timeout: int = 1800,
    progress_callback: Callable[[float], Awaitable[None]] | None = None,
    check_returncode: bool = True,
    capture_output: bool = True,
) -> tuple[int, str, str]:
    """Run subprocess with timeout and zombie prevention.

    Args:
        cmd: Command and arguments as a list.
        timeout: Maximum time in seconds before the process is killed.
        progress_callback: Optional callback for progress updates (0.0 to 1.0).
        check_returncode: If True, raise SubprocessError on non-zero exit.
        capture_output: If True, capture stdout and stderr.

    Returns:
        Tuple of (returncode, stdout, stderr).

    Raises:
        SubprocessTimeoutError: If the process exceeds the timeout.
        SubprocessError: If check_returncode is True and process fails.
    """
    if capture_output:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        proc = await asyncio.create_subprocess_exec(*cmd)

    try:
        if capture_output:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            returncode = proc.returncode or 0
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""
        else:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            returncode = proc.returncode or 0
            stdout_str = ""
            stderr_str = ""
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(f"Process {cmd[0]} did not terminate after kill, PID: {proc.pid}")
        raise SubprocessTimeoutError(cmd, timeout) from None
    finally:
        if proc.returncode is None:
            try:
                await proc.wait()
            except Exception as e:
                logger.warning(f"Failed to wait for process {cmd[0]}: {e}")

    if check_returncode and returncode != 0:
        raise SubprocessError(cmd, returncode, stderr_str)

    return returncode, stdout_str, stderr_str


class TempFileManager:
    """Context manager for temp files with automatic cleanup."""

    def __init__(
        self,
        suffix: str = "",
        prefix: str = "converter_",
        dir_path: str | Path | None = None,
    ):
        self._suffix = suffix
        self._prefix = prefix
        self._dir_path = Path(dir_path) if dir_path else None
        self._temp_files: list[Path] = []
        self._temp_dirs: list[Path] = []

    def create_file(self) -> Path:
        """Create a new temp file and track it for cleanup."""
        fd, path = tempfile.mkstemp(
            suffix=self._suffix,
            prefix=self._prefix,
            dir=str(self._dir_path) if self._dir_path else None,
        )
        os.close(fd)
        temp_path = Path(path)
        self._temp_files.append(temp_path)
        return temp_path

    def create_dir(self) -> Path:
        """Create a new temp directory and track it for cleanup."""
        path = tempfile.mkdtemp(
            prefix=self._prefix,
            dir=str(self._dir_path) if self._dir_path else None,
        )
        temp_path = Path(path)
        self._temp_dirs.append(temp_path)
        return temp_path

    def cleanup(self):
        """Clean up all tracked temp files and directories."""
        for path in self._temp_files:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup file {path}: {e}")
        self._temp_files.clear()

        for path in self._temp_dirs:
            try:
                if path.exists():
                    for item in path.iterdir():
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            for sub_item in item.rglob("*"):
                                if sub_item.is_file():
                                    sub_item.unlink()
                            item.rmdir()
                    path.rmdir()
            except Exception as e:
                logger.warning(f"Failed to cleanup dir {path}: {e}")
        self._temp_dirs.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with guaranteed cleanup."""
        self.cleanup()
        return False


async def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children.

    Args:
        pid: Process ID to kill.
    """
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass

    try:
        await asyncio.sleep(0.5)
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


async def cleanup_orphaned_processes(pattern: str = "ffmpeg|ebook-convert"):
    """Attempt to clean up orphaned processes matching a pattern.

    This is a best-effort cleanup function that tries to find and
    terminate processes that may have been orphaned.

    Args:
        pattern: Regex pattern to match process names.
    """
    try:
        cmd = ["pkill", "-f", pattern]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        if proc.returncode == 0:
            logger.info(f"Cleaned up orphaned processes matching: {pattern}")
    except FileNotFoundError:
        logger.debug("pkill not available, skipping orphan cleanup")
    except Exception as e:
        logger.warning(f"Failed to cleanup orphaned processes: {e}")


import os as _os

_default_concurrent = min(4, _os.cpu_count() or 4)
concurrency_limiter = ConcurrencyLimiter(_default_concurrent)


class SafePathHandler:
    """Handle paths with special characters using temporary symlinks."""

    def __init__(self, temp_dir: Path | None = None):
        """Initialize SafePathHandler.

        Args:
            temp_dir: Optional temporary directory for symlinks.
                      If None, uses system temp directory.
        """
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="safe_path_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._created_symlinks: list[Path] = []

    def create_safe_symlink(self, original_path: Path | str) -> Path:
        """Create a symlink with URL-encoded name for safe handling.

        Args:
            original_path: Path to original file

        Returns:
            Path to the created symlink

        Raises:
            OSError: If symlink creation fails
        """
        original = Path(original_path).resolve()

        if not original.exists():
            raise FileNotFoundError(f"Original file not found: {original}")

        safe_name = quote(original.name, safe="")
        symlink_path = self.temp_dir / safe_name

        if symlink_path.exists():
            symlink_path.unlink()

        try:
            symlink_path.symlink_to(original)
            self._created_symlinks.append(symlink_path)
            logger.debug(f"Created safe symlink: {original} -> {symlink_path}")
            return symlink_path
        except OSError as e:
            logger.error(f"Failed to create symlink for {original}: {e}")
            raise

    def cleanup(self):
        """Clean up all created symlinks and temp directory."""
        for symlink in self._created_symlinks:
            try:
                if symlink.is_symlink():
                    symlink.unlink()
                    logger.debug(f"Removed symlink: {symlink}")
            except Exception as e:
                logger.warning(f"Failed to remove symlink {symlink}: {e}")

        self._created_symlinks.clear()

        try:
            if self.temp_dir.exists() and not any(self.temp_dir.iterdir()):
                self.temp_dir.rmdir()
                logger.debug(f"Removed temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove temp directory {self.temp_dir}: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
