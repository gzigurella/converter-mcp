"""
Tests for progress reporting module.

Tests ProgressReporter, ProgressTracker, and related utilities.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from src.converter.progress import (
    ProgressStage,
    ProgressInfo,
    ProgressReporter,
    ProgressTracker,
    create_progress_callback,
    get_progress_reporter,
    set_progress_reporter,
)


class TestProgressStage:
    """Test cases for ProgressStage enum."""

    def test_stage_values(self):
        """Test that all expected stages exist."""
        assert ProgressStage.INIT.value == "init"
        assert ProgressStage.PROCESSING.value == "processing"
        assert ProgressStage.FINALIZING.value == "finalizing"
        assert ProgressStage.COMPLETE.value == "complete"
        assert ProgressStage.ERROR.value == "error"

    def test_stage_is_string(self):
        """Test that stages can be used as strings."""
        assert str(ProgressStage.INIT) == "ProgressStage.INIT"
        assert ProgressStage.PROCESSING.value in ("processing",)


class TestProgressInfo:
    """Test cases for ProgressInfo dataclass."""

    def test_progress_info_creation(self):
        """Test basic ProgressInfo creation."""
        info = ProgressInfo(job_id="test-job")
        assert info.job_id == "test-job"
        assert info.stage == ProgressStage.INIT
        assert info.progress == 0.0
        assert info.total == 100.0
        assert info.message == ""
        assert info.metadata == {}

    def test_progress_info_with_values(self):
        """Test ProgressInfo with custom values."""
        info = ProgressInfo(
            job_id="custom-job",
            stage=ProgressStage.PROCESSING,
            progress=50.0,
            total=200.0,
            message="Halfway there",
            metadata={"format": "mp4"},
        )
        assert info.job_id == "custom-job"
        assert info.stage == ProgressStage.PROCESSING
        assert info.progress == 50.0
        assert info.total == 200.0
        assert info.message == "Halfway there"
        assert info.metadata == {"format": "mp4"}

    def test_elapsed_seconds(self):
        """Test elapsed time calculation."""
        info = ProgressInfo(job_id="test")
        time.sleep(0.1)
        assert info.elapsed_seconds >= 0.1
        assert info.elapsed_seconds < 1.0

    def test_percent_complete(self):
        """Test percentage calculation."""
        info = ProgressInfo(job_id="test", progress=50.0, total=100.0)
        assert info.percent_complete == 50.0

        info = ProgressInfo(job_id="test", progress=25.0, total=50.0)
        assert info.percent_complete == 50.0

        # Test capping at 100%
        info = ProgressInfo(job_id="test", progress=150.0, total=100.0)
        assert info.percent_complete == 100.0

    def test_percent_complete_zero_total(self):
        """Test percentage when total is zero."""
        info = ProgressInfo(job_id="test", progress=50.0, total=0.0)
        assert info.percent_complete == 0.0

    def test_is_complete(self):
        """Test completion check."""
        info = ProgressInfo(job_id="test", stage=ProgressStage.PROCESSING)
        assert not info.is_complete

        info = ProgressInfo(job_id="test", stage=ProgressStage.COMPLETE)
        assert info.is_complete

        info = ProgressInfo(job_id="test", stage=ProgressStage.ERROR)
        assert info.is_complete

    def test_to_dict(self):
        """Test serialization to dictionary."""
        info = ProgressInfo(
            job_id="test",
            stage=ProgressStage.PROCESSING,
            progress=75.0,
            total=100.0,
            message="Processing",
        )
        d = info.to_dict()
        assert d["job_id"] == "test"
        assert d["stage"] == "processing"
        assert d["progress"] == 75.0
        assert d["total"] == 100.0
        assert d["percent_complete"] == 75.0
        assert d["message"] == "Processing"
        assert "elapsed_seconds" in d
        assert d["metadata"] == {}


class TestProgressReporter:
    """Test cases for ProgressReporter."""

    @pytest.fixture
    def reporter(self):
        """Create a fresh ProgressReporter for each test."""
        return ProgressReporter()

    @pytest.fixture
    def callback(self):
        """Create a mock callback for testing."""
        return MagicMock()

    def test_reporter_creation(self, reporter):
        """Test basic reporter creation."""
        assert reporter._callback is None
        assert reporter._mcp_context is None
        assert reporter._active_jobs == {}

    def test_reporter_with_callback(self, callback):
        """Test reporter with callback."""
        reporter = ProgressReporter(callback=callback)
        assert reporter._callback == callback

    @pytest.mark.asyncio
    async def test_start_job(self, reporter):
        """Test starting a new job."""
        info = await reporter.start_job("job-1", message="Starting")

        assert info.job_id == "job-1"
        assert info.stage == ProgressStage.INIT
        assert info.message == "Starting"
        assert "job-1" in reporter._active_jobs

    @pytest.mark.asyncio
    async def test_update_progress(self, reporter):
        """Test updating job progress."""
        await reporter.start_job("job-1")
        info = await reporter.update_progress(
            "job-1",
            progress=50.0,
            stage=ProgressStage.PROCESSING,
            message="Halfway",
        )

        assert info is not None
        assert info.progress == 50.0
        assert info.stage == ProgressStage.PROCESSING
        assert info.message == "Halfway"

    @pytest.mark.asyncio
    async def test_update_progress_unknown_job(self, reporter):
        """Test updating progress for unknown job."""
        info = await reporter.update_progress("unknown-job", progress=50.0)
        assert info is None

    @pytest.mark.asyncio
    async def test_complete_job_success(self, reporter):
        """Test completing a job successfully."""
        await reporter.start_job("job-1")
        info = await reporter.complete_job("job-1", success=True, message="Done")

        assert info is not None
        assert info.stage == ProgressStage.COMPLETE
        assert info.progress == info.total
        assert info.message == "Done"
        assert "job-1" not in reporter._active_jobs

    @pytest.mark.asyncio
    async def test_complete_job_failure(self, reporter):
        """Test completing a job with failure."""
        await reporter.start_job("job-1")
        info = await reporter.complete_job("job-1", success=False, message="Failed")

        assert info is not None
        assert info.stage == ProgressStage.ERROR
        assert info.message == "Failed"

    @pytest.mark.asyncio
    async def test_complete_job_default_messages(self, reporter):
        """Test default completion messages."""
        await reporter.start_job("job-1")
        info = await reporter.complete_job("job-1", success=True)
        assert info.message == "Conversion complete"

        await reporter.start_job("job-2")
        info = await reporter.complete_job("job-2", success=False)
        assert info.message == "Conversion failed"

    @pytest.mark.asyncio
    async def test_set_stage(self, reporter):
        """Test setting job stage."""
        await reporter.start_job("job-1")
        info = await reporter.set_stage("job-1", ProgressStage.FINALIZING, message="Finishing")

        assert info is not None
        assert info.stage == ProgressStage.FINALIZING
        assert info.message == "Finishing"

    @pytest.mark.asyncio
    async def test_get_job(self, reporter):
        """Test getting job info."""
        await reporter.start_job("job-1")
        info = reporter.get_job("job-1")
        assert info is not None
        assert info.job_id == "job-1"

        info = reporter.get_job("unknown")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_all_jobs(self, reporter):
        """Test getting all active jobs."""
        await reporter.start_job("job-1")
        await reporter.start_job("job-2")

        jobs = reporter.get_all_jobs()
        assert len(jobs) == 2
        assert "job-1" in jobs
        assert "job-2" in jobs

    @pytest.mark.asyncio
    async def test_callback_invocation(self, callback):
        """Test that callback is invoked on progress updates."""
        reporter = ProgressReporter(callback=callback)

        # Complete job immediately to trigger notification
        await reporter.start_job("job-1")
        # Force past the minimum threshold
        await asyncio.sleep(0.1)
        await reporter.complete_job("job-1")

        # Callback should have been called
        assert callback.call_count >= 1

    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test with async callback."""
        call_log = []

        async def async_callback(info):
            call_log.append(info.job_id)

        reporter = ProgressReporter(callback=async_callback)
        await reporter.start_job("job-1")
        await reporter.complete_job("job-1")

        assert "job-1" in call_log

    @pytest.mark.asyncio
    async def test_mcp_context_integration(self):
        """Test integration with MCP context."""
        mock_context = AsyncMock()
        reporter = ProgressReporter(mcp_context=mock_context)

        await reporter.start_job("job-1")
        await reporter.complete_job("job-1")

        # MCP context report_progress should be called
        assert mock_context.report_progress.call_count >= 1

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callback errors don't break reporting."""

        def bad_callback(info):
            raise RuntimeError("Callback error")

        reporter = ProgressReporter(callback=bad_callback)

        # Should not raise
        await reporter.start_job("job-1")
        await reporter.complete_job("job-1")

        assert "job-1" not in reporter._active_jobs


class TestProgressTracker:
    """Test cases for ProgressTracker context manager."""

    @pytest.fixture
    def reporter(self):
        """Create a reporter for testing."""
        return ProgressReporter()

    @pytest.mark.asyncio
    async def test_context_manager_success(self, reporter):
        """Test tracker as context manager with success."""
        async with ProgressTracker(reporter, "job-1", total_steps=10) as tracker:
            assert reporter.get_job("job-1") is not None
            assert reporter.get_job("job-1").stage == ProgressStage.INIT

        # After context, job should be completed
        assert reporter.get_job("job-1") is None  # Removed after completion

    @pytest.mark.asyncio
    async def test_context_manager_exception(self, reporter):
        """Test tracker handles exceptions."""
        try:
            async with ProgressTracker(reporter, "job-1") as tracker:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Job should be marked as error
        assert reporter.get_job("job-1") is None

    @pytest.mark.asyncio
    async def test_advance_progress(self, reporter):
        """Test advancing progress."""
        async with ProgressTracker(reporter, "job-1", total_steps=10) as tracker:
            await tracker.advance(5)
            info = reporter.get_job("job-1")
            assert info.progress == 50.0  # 5/10 = 50%

    @pytest.mark.asyncio
    async def test_advance_capped_at_total(self, reporter):
        """Test advance doesn't exceed total."""
        async with ProgressTracker(reporter, "job-1", total_steps=10) as tracker:
            await tracker.advance(15)  # More than total
            info = reporter.get_job("job-1")
            assert info.progress == 100.0

    @pytest.mark.asyncio
    async def test_set_progress(self, reporter):
        """Test setting specific progress."""
        async with ProgressTracker(reporter, "job-1") as tracker:
            await tracker.set_progress(75.0)
            info = reporter.get_job("job-1")
            assert info.progress == 75.0

    @pytest.mark.asyncio
    async def test_set_progress_clamped(self, reporter):
        """Test progress is clamped to 0-100."""
        async with ProgressTracker(reporter, "job-1") as tracker:
            await tracker.set_progress(150.0)
            info = reporter.get_job("job-1")
            assert info.progress == 100.0

            await tracker.set_progress(-10.0)
            info = reporter.get_job("job-1")
            assert info.progress == 0.0


class TestProgressUtilities:
    """Test cases for utility functions."""

    def test_create_progress_callback(self):
        """Test progress callback factory."""
        callback = create_progress_callback(prefix="Test: ")
        assert callable(callback)

        info = ProgressInfo(
            job_id="job-1",
            stage=ProgressStage.PROCESSING,
            progress=50.0,
            message="Processing",
        )

        # Should not raise
        callback(info)

    def test_get_progress_reporter(self):
        """Test global reporter getter."""
        reporter1 = get_progress_reporter()
        reporter2 = get_progress_reporter()
        assert reporter1 is reporter2

    def test_set_progress_reporter(self):
        """Test setting global reporter."""
        new_reporter = ProgressReporter()
        set_progress_reporter(new_reporter)

        reporter = get_progress_reporter()
        assert reporter is new_reporter

        # Reset to default
        set_progress_reporter(None)


class TestConcurrentProgress:
    """Test concurrent progress reporting."""

    @pytest.mark.asyncio
    async def test_concurrent_jobs(self):
        """Test tracking multiple concurrent jobs."""
        reporter = ProgressReporter()

        # Start multiple jobs
        await reporter.start_job("job-1")
        await reporter.start_job("job-2")
        await reporter.start_job("job-3")

        # Update them concurrently
        await asyncio.gather(
            reporter.update_progress("job-1", progress=30.0),
            reporter.update_progress("job-2", progress=60.0),
            reporter.update_progress("job-3", progress=90.0),
        )

        # Verify each job has correct progress
        assert reporter.get_job("job-1").progress == 30.0
        assert reporter.get_job("job-2").progress == 60.0
        assert reporter.get_job("job-3").progress == 90.0

    @pytest.mark.asyncio
    async def test_job_isolation(self):
        """Test that job progress doesn't interfere."""
        reporter = ProgressReporter()

        await reporter.start_job("job-1", metadata={"format": "mp4"})
        await reporter.start_job("job-2", metadata={"format": "webm"})

        await reporter.update_progress("job-1", progress=50.0, metadata={"size": 1000})

        # Job 2 should not have job 1's metadata
        job2 = reporter.get_job("job-2")
        assert "size" not in job2.metadata
        assert job2.metadata == {"format": "webm"}
