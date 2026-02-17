"""Tests for conversion queue management."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from src.converter.queue import (
    ConversionQueue,
    ConversionJob,
    JobStatus,
    queue,
)


class TestConversionJob:
    """Tests for ConversionJob class."""

    def test_job_creation(self):
        """Test creating a conversion job."""
        job = ConversionJob(
            id="test-123",
            source=Path("/tmp/test.jpg"),
            target_format="png",
            output_path=Path("/tmp/test.png"),
            quality="medium",
        )

        assert job.id == "test-123"
        assert job.status == JobStatus.QUEUED
        assert job.quality == "medium"
        assert job.progress == 0.0

    def test_job_to_dict(self):
        """Test job serialization."""
        job = ConversionJob(
            id="test-456",
            source=Path("/tmp/test.mp4"),
            target_format="webm",
            output_path=Path("/tmp/test.webm"),
            quality="high",
        )

        data = job.to_dict()

        assert data["id"] == "test-456"
        assert data["status"] == "queued"
        assert data["target_format"] == "webm"
        assert data["quality"] == "high"
        assert "created_at" in data

    def test_job_status_values(self):
        """Test job status enum values."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"


class TestConversionQueue:
    """Tests for ConversionQueue class."""

    def test_queue_creation(self):
        """Test creating a conversion queue."""
        q = ConversionQueue(max_concurrent=4)

        assert q._max_concurrent == 4
        assert len(q._jobs) == 0

    @pytest.mark.asyncio
    async def test_submit_job(self):
        """Test submitting a job to the queue."""
        q = ConversionQueue()

        job_id = await q.submit(
            source=Path("/tmp/test.jpg"),
            target_format="png",
            quality="medium",
        )

        assert job_id is not None
        assert job_id in q._jobs
        assert q._jobs[job_id].status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_get_job(self):
        """Test retrieving a job by ID."""
        q = ConversionQueue()

        job_id = await q.submit(
            source=Path("/tmp/test.mp4"),
            target_format="webm",
            quality="low",
        )

        job = q.get_job(job_id)

        assert job is not None
        assert job.id == job_id

    @pytest.mark.asyncio
    async def test_get_all_jobs(self):
        """Test retrieving all jobs."""
        q = ConversionQueue()

        await q.submit(Path("/tmp/a.jpg"), "png")
        await q.submit(Path("/tmp/b.jpg"), "gif")

        jobs = q.get_all_jobs()

        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_cancel_queued_job(self):
        """Test cancelling a queued job."""
        q = ConversionQueue()

        job_id = await q.submit(Path("/tmp/test.jpg"), "png")

        result = await q.cancel(job_id)

        assert result is True
        assert q._jobs[job_id].status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self):
        """Test cancelling a non-existent job."""
        q = ConversionQueue()

        result = await q.cancel("nonexistent")

        assert result is False

    def test_get_active_count(self):
        """Test getting active job count."""
        q = ConversionQueue()

        assert q.get_active_count() == 0

    def test_global_queue_instance(self):
        """Test global queue instance exists."""
        assert queue is not None
        assert isinstance(queue, ConversionQueue)


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    @pytest.mark.asyncio
    async def test_status_progression(self):
        """Test job status can be updated."""
        q = ConversionQueue()

        job_id = await q.submit(Path("/tmp/test.jpg"), "png")
        job = q.get_job(job_id)

        assert job.status == JobStatus.QUEUED

        job.status = JobStatus.RUNNING
        assert job.status == JobStatus.RUNNING

        job.status = JobStatus.COMPLETED
        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_wait_for_completed_job(self):
        """Test waiting for a completed job."""
        q = ConversionQueue()

        job_id = await q.submit(Path("/tmp/test.jpg"), "png")
        job = q.get_job(job_id)
        job.status = JobStatus.COMPLETED

        result = await q.wait_for_job(job_id, timeout=1.0)

        assert result.status == JobStatus.COMPLETED
