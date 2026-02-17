"""Queue management for conversion operations."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Status of a conversion job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ConversionJob:
    """Represents a conversion job in the queue."""

    id: str
    source: Path
    target_format: str
    output_path: Optional[Path]
    quality: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: float = 0.0

    def to_dict(self) -> dict:
        """Convert job to dictionary for serialization."""
        return {
            "id": self.id,
            "source": str(self.source),
            "target_format": self.target_format,
            "output_path": str(self.output_path) if self.output_path else None,
            "quality": self.quality,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "progress": self.progress,
        }


class ConversionQueue:
    """Manages a queue of conversion jobs."""

    def __init__(self, max_concurrent: int = 4):
        self._queue: asyncio.Queue[ConversionJob] = asyncio.Queue()
        self._jobs: dict[str, ConversionJob] = {}
        self._max_concurrent = max_concurrent
        self._active_jobs: set[str] = set()
        self._lock = asyncio.Lock()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    async def submit(
        self,
        source: Path,
        target_format: str,
        output_path: Optional[Path] = None,
        quality: str = "medium",
    ) -> str:
        """Submit a new conversion job."""
        job = ConversionJob(
            id=str(uuid.uuid4()),
            source=source,
            target_format=target_format,
            output_path=output_path,
            quality=quality,
        )

        async with self._lock:
            self._jobs[job.id] = job
            await self._queue.put(job)

        logger.info(f"Job {job.id} submitted: {source} -> {target_format}")
        return job.id

    def get_job(self, job_id: str) -> Optional[ConversionJob]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[ConversionJob]:
        """Get all jobs."""
        return list(self._jobs.values())

    def get_active_count(self) -> int:
        """Get number of active jobs."""
        return len(self._active_jobs)

    async def cancel(self, job_id: str) -> bool:
        """Cancel a job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                logger.info(f"Job {job_id} cancelled")
                return True
        return False

    async def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> ConversionJob:
        """Wait for a job to complete."""
        start = datetime.now()

        while True:
            job = self._jobs.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            if timeout:
                elapsed = (datetime.now() - start).total_seconds()
                if elapsed >= timeout:
                    raise asyncio.TimeoutError(f"Timeout waiting for job {job_id}")

            await asyncio.sleep(0.1)


queue = ConversionQueue()
