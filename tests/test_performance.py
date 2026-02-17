"""
Performance tests for format conversion.

Benchmarks conversion speeds and validates concurrency limits.
Marked as 'slow' - run with: pytest -m slow tests/test_performance.py
"""

import asyncio
import statistics
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.converter.async_utils import ConcurrencyLimiter, concurrency_limiter
from src.converter.converters.image import ImageConverter
from src.converter.converters.router import ConverterRouter
from src.converter.file_manager import FileManager
from src.converter.queue import ConversionQueue, JobStatus

pytestmark = pytest.mark.slow


@pytest.fixture
def temp_dir():
    """Create a temporary directory for performance tests."""
    temp = tempfile.mkdtemp(prefix="converter_perf_")
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def sample_images(temp_dir):
    """Create sample images for performance testing."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    images = []
    for i in range(10):
        img_path = temp_dir / f"sample_{i}.png"
        img = Image.new("RGB", (500, 500), color=(i * 20, 100, 150))
        img.save(img_path, "PNG")
        img.close()
        images.append(img_path)

    return images


class TestConcurrencyLimits:
    """Test that concurrency limits are respected."""

    @pytest.mark.asyncio
    async def test_concurrency_limiter_basic(self):
        """Test basic concurrency limiter functionality."""
        limiter = ConcurrencyLimiter(max_concurrent=2)

        active_count = 0
        max_active = 0
        lock = asyncio.Lock()

        async def track_concurrency(task_id):
            nonlocal active_count, max_active

            async with limiter:
                async with lock:
                    active_count += 1
                    max_active = max(max_active, active_count)

                await asyncio.sleep(0.1)

                async with lock:
                    active_count -= 1

        await asyncio.gather(*[track_concurrency(i) for i in range(5)])

        assert max_active <= 2, f"Max concurrent exceeded: {max_active}"

    @pytest.mark.asyncio
    async def test_global_concurrency_limiter(self):
        """Test that global limiter is properly configured."""
        assert concurrency_limiter._max_concurrent >= 1
        assert concurrency_limiter._max_concurrent <= 4

    @pytest.mark.asyncio
    async def test_queue_respects_concurrency(self, sample_images, temp_dir):
        """Test that queue respects concurrency limits."""
        queue = ConversionQueue(max_concurrent=2)

        job_ids = []
        for img in sample_images[:6]:
            job_id = await queue.submit(source=img, target_format="jpg")
            job_ids.append(job_id)

        active_counts = []
        for _ in range(10):
            active = queue.get_active_count()
            active_counts.append(active)
            await asyncio.sleep(0.05)

        max_active = max(active_counts) if active_counts else 0

        assert max_active <= 2, f"Max concurrent exceeded: {max_active}"


class TestConversionThroughput:
    """Test conversion throughput benchmarks."""

    @pytest.mark.asyncio
    async def test_image_conversion_throughput(self, sample_images, temp_dir):
        """Benchmark image conversion throughput."""
        converter = ImageConverter()

        start_time = time.monotonic()

        results = []
        for img in sample_images:
            output = temp_dir / f"{img.stem}.jpg"
            result = await converter.convert(img, "jpg", output_path=output)
            results.append(result)

        elapsed = time.monotonic() - start_time

        assert len(results) == len(sample_images)

        throughput = len(results) / elapsed
        print(f"Image throughput: {throughput:.2f} conversions/second")

        assert throughput > 0.5, "Throughput too low"

    @pytest.mark.asyncio
    async def test_concurrent_throughput(self, sample_images, temp_dir):
        """Benchmark concurrent conversion throughput."""
        converter = ImageConverter()

        start_time = time.monotonic()

        async def convert_one(img):
            output = temp_dir / f"{img.stem}_concurrent.jpg"
            return await converter.convert(img, "jpg", output_path=output)

        results = await asyncio.gather(*[convert_one(img) for img in sample_images])

        elapsed = time.monotonic() - start_time

        assert len(results) == len(sample_images)

        throughput = len(results) / elapsed
        print(f"Concurrent throughput: {throughput:.2f} conversions/second")

    @pytest.mark.asyncio
    async def test_router_throughput(self, sample_images, temp_dir):
        """Benchmark router-based conversion throughput."""
        router = ConverterRouter()

        start_time = time.monotonic()

        results = []
        for img in sample_images:
            output = temp_dir / f"{img.stem}_routed.jpg"
            result = await router.convert(img, "jpg", output_path=output)
            results.append(result)

        elapsed = time.monotonic() - start_time

        assert len(results) == len(sample_images)

        throughput = len(results) / elapsed
        print(f"Router throughput: {throughput:.2f} conversions/second")


class TestConversionLatency:
    """Test individual conversion latency."""

    @pytest.mark.asyncio
    async def test_single_image_latency(self, sample_images, temp_dir):
        """Measure single image conversion latency."""
        converter = ImageConverter()

        latencies = []

        for img in sample_images[:5]:
            output = temp_dir / f"{img.stem}_latency.jpg"

            start = time.monotonic()
            await converter.convert(img, "jpg", output_path=output)
            elapsed = time.monotonic() - start

            latencies.append(elapsed)

        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)

        print(
            f"Latency - avg: {avg_latency * 1000:.1f}ms, min: {min_latency * 1000:.1f}ms, max: {max_latency * 1000:.1f}ms"
        )

        assert avg_latency < 1.0, f"Average latency too high: {avg_latency:.2f}s"

    @pytest.mark.asyncio
    async def test_format_detection_overhead(self, sample_images, temp_dir):
        """Measure format detection overhead."""
        router = ConverterRouter()

        detection_times = []

        for img in sample_images[:5]:
            start = time.monotonic()
            router.get_converter_type(img.suffix.lstrip("."), "jpg")
            elapsed = time.monotonic() - start
            detection_times.append(elapsed)

        avg_detection = statistics.mean(detection_times)

        print(f"Format detection avg: {avg_detection * 1000:.3f}ms")

        assert avg_detection < 0.001, "Format detection too slow"


class TestQueuePerformance:
    """Test queue performance under load."""

    @pytest.mark.asyncio
    async def test_queue_submit_performance(self, sample_images):
        """Benchmark queue submission speed."""
        queue = ConversionQueue()

        start_time = time.monotonic()

        job_ids = []
        for img in sample_images:
            job_id = await queue.submit(source=img, target_format="jpg")
            job_ids.append(job_id)

        elapsed = time.monotonic() - start_time

        submit_rate = len(job_ids) / elapsed
        print(f"Queue submit rate: {submit_rate:.0f} jobs/second")

        assert len(job_ids) == len(sample_images)
        assert submit_rate > 100, "Queue submit rate too slow"

    @pytest.mark.asyncio
    async def test_queue_status_lookup_performance(self, sample_images):
        """Benchmark queue status lookup speed."""
        queue = ConversionQueue()

        job_ids = []
        for img in sample_images:
            job_id = await queue.submit(source=img, target_format="jpg")
            job_ids.append(job_id)

        start_time = time.monotonic()

        for job_id in job_ids:
            queue.get_job(job_id)

        elapsed = time.monotonic() - start_time

        lookup_rate = len(job_ids) / elapsed
        print(f"Queue lookup rate: {lookup_rate:.0f} lookups/second")

        assert lookup_rate > 1000, "Queue lookup rate too slow"


class TestResourceManagerPerformance:
    """Test resource manager performance."""

    def test_file_manager_path_resolution(self, sample_images):
        """Benchmark file manager path resolution."""
        fm = FileManager()

        start_time = time.monotonic()

        for img in sample_images:
            fm.resolve_output_path(img, "jpg")

        elapsed = time.monotonic() - start_time

        rate = len(sample_images) / elapsed
        print(f"Path resolution rate: {rate:.0f} paths/second")

        assert rate > 1000, "Path resolution too slow"

    def test_disk_space_check_performance(self, temp_dir):
        """Benchmark disk space check speed."""
        fm = FileManager()

        start_time = time.monotonic()

        for _ in range(100):
            fm.check_disk_space(str(temp_dir))

        elapsed = time.monotonic() - start_time

        rate = 100 / elapsed
        print(f"Disk space check rate: {rate:.0f} checks/second")

        assert rate > 100, "Disk space check too slow"


class TestConcurrencyStress:
    """Stress tests for concurrency handling."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_concurrency_stress(self, temp_dir):
        """Test with high concurrency load."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        images = []
        for i in range(20):
            img_path = temp_dir / f"stress_{i}.png"
            img = Image.new("RGB", (100, 100), color=(i, i, i))
            img.save(img_path, "PNG")
            img.close()
            images.append(img_path)

        converter = ImageConverter()

        start_time = time.monotonic()

        results = []
        for img in images:
            try:
                output = temp_dir / f"{img.stem}.jpg"
                result = await converter.convert(img, "jpg", output_path=output)
                results.append(result)
            except Exception as e:
                results.append(e)

        elapsed = time.monotonic() - start_time

        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = sum(1 for r in results if isinstance(r, Exception))

        throughput = successful / elapsed if elapsed > 0 else 0

        print(f"Stress test: {successful} successful, {failed} failed, {throughput:.1f}/s")

        assert successful >= 15, f"Too many failures: {failed}"

    @pytest.mark.asyncio
    async def test_sustained_load(self, temp_dir):
        """Test sustained conversion load."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        converter = ImageConverter()
        iterations = 10

        latencies = []

        for i in range(iterations):
            img_path = temp_dir / f"sustain_{i}.png"
            img = Image.new("RGB", (200, 200), color=(i * 10, 100, 150))
            img.save(img_path, "PNG")
            img.close()

            output = temp_dir / f"sustain_{i}.jpg"

            start = time.monotonic()
            await converter.convert(img_path, "jpg", output_path=output)
            elapsed = time.monotonic() - start

            latencies.append(elapsed)

            img_path.unlink()
            output.unlink()

        avg_latency = statistics.mean(latencies)
        std_dev = statistics.stdev(latencies) if len(latencies) > 1 else 0

        print(f"Sustained load - avg: {avg_latency * 1000:.1f}ms, std: {std_dev * 1000:.1f}ms")

        assert std_dev < avg_latency, "Latency variance too high"
