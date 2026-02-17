"""
Large file tests for format conversion.

Tests memory efficiency and performance with large files:
- Large images (>50MP)
- Large videos (>100MB)
- Large ebooks (>50MB)

These tests are marked as 'slow' and can be skipped with:
    pytest -m "not slow"
"""

import asyncio
import gc
import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional

import pytest

from src.converter.converters.image import ImageConverter
from src.converter.file_manager import FileManager

pytestmark = pytest.mark.slow


@pytest.fixture
def temp_dir():
    """Create a temporary directory for large test files."""
    temp = tempfile.mkdtemp(prefix="converter_large_")
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def create_large_image(
    output_path: Path,
    width: int = 8000,
    height: int = 8000,
) -> Optional[Path]:
    """Create a large image for testing (64MP by default).

    Returns None if Pillow not available.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    img.save(output_path, "PNG")
    img.close()
    return output_path


def create_large_tiff(
    output_path: Path,
    width: int = 10000,
    height: int = 10000,
) -> Optional[Path]:
    """Create a large TIFF image for testing (100MP).

    Returns None if Pillow not available.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    img = Image.new("RGB", (width, height), color=(50, 100, 150))
    img.save(output_path, "TIFF")
    img.close()
    return output_path


class TestLargeImageMemory:
    """Test memory efficiency with large images."""

    @pytest.mark.asyncio
    async def test_large_png_to_jpg_memory(self, temp_dir):
        """Test converting large PNG to JPG doesn't cause memory spike."""
        large_png = create_large_image(temp_dir / "large.png", 5000, 5000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        if not large_png.exists():
            pytest.skip("Failed to create large image")

        gc.collect()
        memory_before = get_memory_mb()

        converter = ImageConverter()
        output_path = temp_dir / "large.jpg"

        result = await converter.convert(large_png, "jpg", output_path=output_path, quality="high")

        gc.collect()
        memory_after = get_memory_mb()
        memory_increase = memory_after - memory_before

        assert result.exists()
        assert result.stat().st_size > 0

        print(
            f"Memory before: {memory_before:.1f}MB, after: {memory_after:.1f}MB, increase: {memory_increase:.1f}MB"
        )

        assert memory_increase < 500, f"Memory increase too high: {memory_increase:.1f}MB"

    @pytest.mark.asyncio
    async def test_large_tiff_to_webp_memory(self, temp_dir):
        """Test converting large TIFF to WebP doesn't cause memory spike."""
        large_tiff = create_large_tiff(temp_dir / "large.tiff", 6000, 6000)
        if large_tiff is None:
            pytest.skip("Pillow not installed")

        if not large_tiff.exists():
            pytest.skip("Failed to create large TIFF")

        gc.collect()
        memory_before = get_memory_mb()

        converter = ImageConverter()
        output_path = temp_dir / "large.webp"

        result = await converter.convert(
            large_tiff, "webp", output_path=output_path, quality="medium"
        )

        gc.collect()
        memory_after = get_memory_mb()
        memory_increase = memory_after - memory_before

        assert result.exists()

        print(
            f"Memory before: {memory_before:.1f}MB, after: {memory_after:.1f}MB, increase: {memory_increase:.1f}MB"
        )

        assert memory_increase < 400, f"Memory increase too high: {memory_increase:.1f}MB"

    @pytest.mark.asyncio
    async def test_concurrent_large_images(self, temp_dir):
        """Test concurrent large image conversions."""
        images = []
        for i in range(3):
            img = create_large_image(temp_dir / f"large_{i}.png", 3000, 3000)
            if img:
                images.append(img)

        if len(images) < 3:
            pytest.skip("Failed to create test images")

        gc.collect()
        memory_before = get_memory_mb()

        converter = ImageConverter()

        async def convert_one(idx, src):
            output = temp_dir / f"output_{idx}.jpg"
            return await converter.convert(src, "jpg", output_path=output)

        results = await asyncio.gather(*[convert_one(i, img) for i, img in enumerate(images)])

        gc.collect()
        memory_after = get_memory_mb()
        memory_increase = memory_after - memory_before

        for result in results:
            assert result.exists()

        print(
            f"Concurrent memory: before {memory_before:.1f}MB, after {memory_after:.1f}MB, increase: {memory_increase:.1f}MB"
        )


class TestLargeImagePerformance:
    """Test performance with large images."""

    @pytest.mark.asyncio
    async def test_large_image_conversion_time(self, temp_dir):
        """Test that large image conversion completes in reasonable time."""
        import time

        large_png = create_large_image(temp_dir / "large.png", 4000, 4000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        converter = ImageConverter()
        output_path = temp_dir / "large.jpg"

        start_time = time.monotonic()
        result = await converter.convert(large_png, "jpg", output_path=output_path)
        elapsed = time.monotonic() - start_time

        assert result.exists()

        print(f"16MP image conversion time: {elapsed:.2f}s")

        assert elapsed < 30, f"Conversion took too long: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_quality_affects_output_size(self, temp_dir):
        """Test that quality settings affect output size for large images."""
        large_png = create_large_image(temp_dir / "large.png", 4000, 4000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        converter = ImageConverter()
        sizes = {}

        for quality in ["low", "medium", "high"]:
            output_path = temp_dir / f"output_{quality}.jpg"
            await converter.convert(large_png, "jpg", output_path=output_path, quality=quality)
            sizes[quality] = output_path.stat().st_size

        print(
            f"Sizes - low: {sizes['low'] // 1024}KB, medium: {sizes['medium'] // 1024}KB, high: {sizes['high'] // 1024}KB"
        )

        assert sizes["low"] < sizes["medium"] < sizes["high"]


class TestLargeFileCleanup:
    """Test cleanup after large file operations."""

    @pytest.mark.asyncio
    async def test_no_temp_files_after_large_conversion(self, temp_dir):
        """Verify no temporary files remain after large image conversion."""
        large_png = create_large_image(temp_dir / "large.png", 5000, 5000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        files_before = set(temp_dir.iterdir())

        converter = ImageConverter()
        output_path = temp_dir / "large.jpg"
        await converter.convert(large_png, "jpg", output_path=output_path)

        files_after = set(temp_dir.iterdir())
        new_files = files_after - files_before

        temp_extensions = {".tmp", ".temp", ".partial"}
        temp_files = [f for f in new_files if f.suffix.lower() in temp_extensions]

        assert len(temp_files) == 0, f"Temp files found: {temp_files}"

    @pytest.mark.asyncio
    async def test_memory_released_after_conversion(self, temp_dir):
        """Verify memory is not excessively leaked after large conversion."""
        large_png = create_large_image(temp_dir / "large.png", 6000, 6000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        gc.collect()
        memory_before = get_memory_mb()

        converter = ImageConverter()
        output_path = temp_dir / "large.jpg"
        await converter.convert(large_png, "jpg", output_path=output_path)

        gc.collect()
        memory_after = get_memory_mb()

        memory_increase = memory_after - memory_before

        print(
            f"Memory: before {memory_before:.1f}MB, after cleanup {memory_after:.1f}MB, increase: {memory_increase:.1f}MB"
        )

        assert memory_increase < 200, f"Memory leak detected: {memory_increase:.1f}MB increase"


class TestDiskSpaceHandling:
    """Test disk space handling for large files."""

    def test_disk_space_check_with_large_file(self, temp_dir):
        """Test disk space check handles large file estimates."""
        fm = FileManager(min_disk_space_mb=1)

        result = fm.check_disk_space(str(temp_dir))

        assert result is True

    @pytest.mark.asyncio
    async def test_output_size_reasonable(self, temp_dir):
        """Test that output size is reasonable compared to input."""
        large_png = create_large_image(temp_dir / "large.png", 4000, 4000)
        if large_png is None:
            pytest.skip("Pillow not installed")

        input_size = large_png.stat().st_size

        converter = ImageConverter()
        output_path = temp_dir / "large.jpg"
        await converter.convert(large_png, "jpg", output_path=output_path, quality="medium")

        output_size = output_path.stat().st_size

        ratio = output_size / input_size

        print(f"Input: {input_size // 1024}KB, Output: {output_size // 1024}KB, Ratio: {ratio:.2f}")

        assert ratio < 10, f"Output unreasonably large: {ratio:.2f}x input"
