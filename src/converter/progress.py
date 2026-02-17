"""
Progress reporting for MCP Context integration.

Provides progress callback system for converters with structured
reporting stages and MCP Context integration.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Any
from weakref import WeakSet

from .logging_config import get_logger

logger = get_logger("progress")


class ProgressStage(str, Enum):
    """Progress stages for conversion operations."""

    INIT = "init"
    PROCESSING = "processing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ProgressInfo:
    """Progress information for a conversion operation."""

    job_id: str
    stage: ProgressStage = ProgressStage.INIT
    progress: float = 0.0  # 0.0 to 100.0
    total: float = 100.0
    message: str = ""
    start_time: float = field(default_factory=time.monotonic)
    metadata: dict = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        """Time elapsed since operation started."""
        return time.monotonic() - self.start_time

    @property
    def percent_complete(self) -> float:
        """Percentage complete (0-100)."""
        if self.total == 0:
            return 0.0
        return min(100.0, (self.progress / self.total) * 100.0)

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.stage in (ProgressStage.COMPLETE, ProgressStage.ERROR)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "job_id": self.job_id,
            "stage": self.stage.value,
            "progress": self.progress,
            "total": self.total,
            "percent_complete": self.percent_complete,
            "message": self.message,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "metadata": self.metadata,
        }


# Type alias for progress callbacks
ProgressCallback = Callable[[ProgressInfo], None]
AsyncProgressCallback = Callable[[ProgressInfo], Any]  # Can be async or sync


class ProgressReporter:
    """
    Manages progress reporting for conversion operations.

    Supports both sync and async callbacks, MCP Context integration,
    and concurrent operation tracking.
    """

    # Minimum duration (seconds) before progress reporting kicks in
    MIN_PROGRESS_THRESHOLD = 1.0

    def __init__(
        self,
        callback: Optional[AsyncProgressCallback] = None,
        mcp_context: Optional[Any] = None,
    ):
        """
        Initialize progress reporter.

        Args:
            callback: Optional callback function for progress updates
            mcp_context: Optional MCP Context for report_progress() calls
        """
        self._callback = callback
        self._mcp_context = mcp_context
        self._active_jobs: dict[str, ProgressInfo] = {}
        self._lock = asyncio.Lock()

    async def start_job(
        self,
        job_id: str,
        message: str = "Starting conversion",
        metadata: Optional[dict] = None,
    ) -> ProgressInfo:
        """
        Start tracking a new conversion job.

        Args:
            job_id: Unique identifier for the job
            message: Initial status message
            metadata: Optional metadata for the job

        Returns:
            ProgressInfo for the new job
        """
        async with self._lock:
            info = ProgressInfo(
                job_id=job_id,
                stage=ProgressStage.INIT,
                progress=0.0,
                total=100.0,
                message=message,
                metadata=metadata or {},
            )
            self._active_jobs[job_id] = info
            await self._notify(info)
            return info

    async def update_progress(
        self,
        job_id: str,
        progress: float,
        stage: Optional[ProgressStage] = None,
        message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[ProgressInfo]:
        """
        Update progress for a job.

        Args:
            job_id: Job identifier
            progress: Current progress value (0-total)
            stage: Optional new stage
            message: Optional status message
            metadata: Optional metadata to merge

        Returns:
            Updated ProgressInfo or None if job not found
        """
        async with self._lock:
            info = self._active_jobs.get(job_id)
            if info is None:
                logger.warning(f"Progress update for unknown job: {job_id}")
                return None

            info.progress = progress
            if stage is not None:
                info.stage = stage
            if message is not None:
                info.message = message
            if metadata is not None:
                info.metadata.update(metadata)

            await self._notify(info)
            return info

    async def complete_job(
        self,
        job_id: str,
        success: bool = True,
        message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[ProgressInfo]:
        """
        Mark a job as complete.

        Args:
            job_id: Job identifier
            success: Whether the job succeeded
            message: Optional final message
            metadata: Optional final metadata

        Returns:
            Final ProgressInfo or None if job not found
        """
        async with self._lock:
            info = self._active_jobs.get(job_id)
            if info is None:
                logger.warning(f"Complete for unknown job: {job_id}")
                return None

            info.stage = ProgressStage.COMPLETE if success else ProgressStage.ERROR
            info.progress = info.total
            if message is not None:
                info.message = message
            elif success:
                info.message = "Conversion complete"
            else:
                info.message = "Conversion failed"
            if metadata is not None:
                info.metadata.update(metadata)

            await self._notify(info)

            # Remove completed job after notification
            final_info = info
            del self._active_jobs[job_id]
            return final_info

    async def set_stage(
        self,
        job_id: str,
        stage: ProgressStage,
        message: Optional[str] = None,
    ) -> Optional[ProgressInfo]:
        """
        Set the stage for a job without updating progress.

        Args:
            job_id: Job identifier
            stage: New stage
            message: Optional status message

        Returns:
            Updated ProgressInfo or None if job not found
        """
        async with self._lock:
            info = self._active_jobs.get(job_id)
            if info is None:
                return None

            info.stage = stage
            if message is not None:
                info.message = message

            await self._notify(info)
            return info

    def get_job(self, job_id: str) -> Optional[ProgressInfo]:
        """Get current progress info for a job."""
        return self._active_jobs.get(job_id)

    def get_all_jobs(self) -> dict[str, ProgressInfo]:
        """Get all active jobs."""
        return self._active_jobs.copy()

    async def _notify(self, info: ProgressInfo) -> None:
        """
        Notify callback and MCP context of progress update.

        Internal method - must be called with lock held.
        """
        # Skip notification if operation is too fast
        if info.elapsed_seconds < self.MIN_PROGRESS_THRESHOLD and not info.is_complete:
            return

        # Call user callback
        if self._callback is not None:
            try:
                result = self._callback(info)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

        # Call MCP context report_progress if available
        if self._mcp_context is not None:
            try:
                # MCP Context has report_progress(progress, total) method
                await self._mcp_context.report_progress(
                    progress=int(info.progress),
                    total=int(info.total),
                )
            except Exception as e:
                logger.debug(f"MCP progress report error: {e}")


class ProgressTracker:
    """
    Context manager for tracking progress of an operation.

    Provides automatic progress updates and completion handling.
    """

    def __init__(
        self,
        reporter: ProgressReporter,
        job_id: str,
        total_steps: int = 100,
        message: str = "Processing",
    ):
        """
        Initialize progress tracker.

        Args:
            reporter: ProgressReporter instance
            job_id: Unique job identifier
            total_steps: Total number of steps for the operation
            message: Initial message
        """
        self._reporter = reporter
        self._job_id = job_id
        self._total_steps = total_steps
        self._message = message
        self._current_step = 0
        self._started = False

    async def __aenter__(self) -> "ProgressTracker":
        """Start tracking the operation."""
        await self._reporter.start_job(
            self._job_id,
            message=self._message,
        )
        self._started = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Complete the operation, handling any exceptions."""
        if not self._started:
            return

        if exc_type is not None:
            await self._reporter.complete_job(
                self._job_id,
                success=False,
                message=f"Failed: {exc_val}",
            )
        else:
            await self._reporter.complete_job(
                self._job_id,
                success=True,
                message=f"{self._message} complete",
            )

    async def advance(self, steps: int = 1, message: Optional[str] = None) -> None:
        """
        Advance progress by a number of steps.

        Args:
            steps: Number of steps to advance
            message: Optional new message
        """
        self._current_step = min(self._current_step + steps, self._total_steps)
        progress = (self._current_step / self._total_steps) * 100.0

        await self._reporter.update_progress(
            self._job_id,
            progress=progress,
            stage=ProgressStage.PROCESSING,
            message=message or self._message,
        )

    async def set_progress(self, percent: float, message: Optional[str] = None) -> None:
        """
        Set progress to a specific percentage.

        Args:
            percent: Progress percentage (0-100)
            message: Optional new message
        """
        await self._reporter.update_progress(
            self._job_id,
            progress=min(100.0, max(0.0, percent)),
            stage=ProgressStage.PROCESSING,
            message=message or self._message,
        )


def create_progress_callback(
    prefix: str = "",
) -> Callable[[ProgressInfo], None]:
    """
    Create a simple logging progress callback.

    Args:
        prefix: Prefix for log messages

    Returns:
        Callback function suitable for ProgressReporter
    """

    def callback(info: ProgressInfo) -> None:
        msg = f"{prefix}{info.job_id}: {info.stage.value} - {info.percent_complete:.1f}%"
        if info.message:
            msg += f" ({info.message})"
        logger.info(msg)

    return callback


# Global progress reporter for simple use cases
_global_reporter: Optional[ProgressReporter] = None


def get_progress_reporter() -> ProgressReporter:
    """Get the global progress reporter instance."""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = ProgressReporter(callback=create_progress_callback())
    return _global_reporter


def set_progress_reporter(reporter: ProgressReporter) -> None:
    """Set the global progress reporter instance."""
    global _global_reporter
    _global_reporter = reporter
