"""
Edge case tests for the converter.

Tests boundary conditions, error scenarios, and unusual inputs.
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.converter.converters.image import ImageConverter
from src.converter.converters.video import VideoConverter
from src.converter.file_manager import FileManager, FileOperationError
from src.converter.logging_config import ConversionError, FormatNotSupportedError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp(prefix="converter_edge_")
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


class TestFilePermissionErrors:
    """Test handling of permission-related errors."""

    @pytest.mark.asyncio
    async def test_read_permission_denied(self, temp_dir):
        """Test conversion with unreadable source file."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_path = temp_dir / "protected.png"
        img = Image.new("RGB", (10, 10), color="red")
        img.save(img_path, "PNG")
        img.close()

        os.chmod(img_path, 0o000)

        try:
            converter = ImageConverter()
            output = temp_dir / "output.jpg"

            with pytest.raises(Exception):
                await converter.convert(img_path, "jpg", output_path=output)
        finally:
            os.chmod(img_path, 0o644)

    @pytest.mark.asyncio
    async def test_write_permission_denied(self, temp_dir):
        """Test conversion when output directory is not writable."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_path = temp_dir / "test.png"
        img = Image.new("RGB", (10, 10), color="red")
        img.save(img_path, "PNG")
        img.close()

        protected_dir = temp_dir / "protected"
        protected_dir.mkdir()
        os.chmod(protected_dir, 0o444)

        try:
            converter = ImageConverter()
            output = protected_dir / "output.jpg"

            with pytest.raises(Exception):
                await converter.convert(img_path, "jpg", output_path=output)
        finally:
            os.chmod(protected_dir, 0o754)


class TestCorruptedFiles:
    """Test handling of corrupted or invalid files."""

    @pytest.mark.asyncio
    async def test_corrupted_image(self, temp_dir):
        """Test conversion with corrupted image file."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        corrupted = temp_dir / "corrupted.png"
        corrupted.write_bytes(b"Not a valid PNG file content")

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        with pytest.raises(Exception):
            await converter.convert(corrupted, "jpg", output_path=output)

    @pytest.mark.asyncio
    async def test_empty_file(self, temp_dir):
        """Test conversion with empty file."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        empty = temp_dir / "empty.png"
        empty.touch()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        with pytest.raises(Exception):
            await converter.convert(empty, "jpg", output_path=output)

    @pytest.mark.asyncio
    async def test_wrong_extension(self, temp_dir):
        """Test file with wrong extension."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        fake_png = temp_dir / "fake.png"
        fake_png.write_text("This is text, not a PNG")

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        with pytest.raises(Exception):
            await converter.convert(fake_png, "jpg", output_path=output)


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    @pytest.mark.asyncio
    async def test_minimum_image_size(self, temp_dir):
        """Test conversion of 1x1 pixel image."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        tiny = temp_dir / "tiny.png"
        img = Image.new("RGB", (1, 1), color="blue")
        img.save(tiny, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(tiny, "jpg", output_path=output)
        assert result.exists()

    @pytest.mark.asyncio
    async def test_resize_to_larger(self, temp_dir):
        """Test resizing image to larger dimensions."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        small = temp_dir / "small.png"
        img = Image.new("RGB", (10, 10), color="green")
        img.save(small, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "large.jpg"

        result = await converter.convert(small, "jpg", output_path=output, resize=(1000, 1000))
        assert result.exists()

    def test_max_collision_limit(self, temp_dir):
        """Test that collision limit is enforced."""
        fm = FileManager()

        base_file = temp_dir / "test.txt"
        base_file.touch()

        for i in range(1005):
            (temp_dir / f"test_{i}.txt").touch()

        with pytest.raises(FileOperationError):
            fm.resolve_output_path(base_file, "txt")


class TestUnicodeAndSpecialChars:
    """Test handling of Unicode and special characters."""

    @pytest.mark.asyncio
    async def test_unicode_filename(self, temp_dir):
        """Test conversion with Unicode filename."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        unicode_file = temp_dir / "test_日本語_🎉.png"
        img = Image.new("RGB", (50, 50), color="yellow")
        img.save(unicode_file, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(unicode_file, "jpg", output_path=output)
        assert result.exists()

    @pytest.mark.asyncio
    async def test_spaces_in_filename(self, temp_dir):
        """Test conversion with spaces in filename."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        spaced = temp_dir / "test file with spaces.png"
        img = Image.new("RGB", (50, 50), color="purple")
        img.save(spaced, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(spaced, "jpg", output_path=output)
        assert result.exists()


class TestFormatEdgeCases:
    """Test format-specific edge cases."""

    @pytest.mark.asyncio
    async def test_quality_boundary_values(self, temp_dir):
        """Test quality values at boundaries."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_path = temp_dir / "test.png"
        img = Image.new("RGB", (50, 50), color="orange")
        img.save(img_path, "PNG")
        img.close()

        converter = ImageConverter()

        for quality in ["low", "medium", "high"]:
            output = temp_dir / f"output_{quality}.jpg"
            result = await converter.convert(img_path, "jpg", output_path=output, quality=quality)
            assert result.exists()

    @pytest.mark.asyncio
    async def test_rgba_to_jpeg(self, temp_dir):
        """Test RGBA image conversion to JPEG (which doesn't support alpha)."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        rgba = temp_dir / "rgba.png"
        img = Image.new("RGBA", (50, 50), color=(255, 0, 0, 128))
        img.save(rgba, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(rgba, "jpg", output_path=output)
        assert result.exists()

    def test_case_insensitive_formats(self):
        """Test that format names are case-insensitive."""
        converter = ImageConverter()

        assert converter.is_format_supported("PNG") is True
        assert converter.is_format_supported("Jpg") is True
        assert converter.is_format_supported("WEBP") is True


class TestConcurrentAccess:
    """Test concurrent file access scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_same_file(self, temp_dir):
        """Test concurrent conversions of same source file."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        source = temp_dir / "source.png"
        img = Image.new("RGB", (50, 50), color="cyan")
        img.save(source, "PNG")
        img.close()

        converter = ImageConverter()

        async def convert_one(idx):
            output = temp_dir / f"output_{idx}.jpg"
            return await converter.convert(source, "jpg", output_path=output)

        results = await asyncio.gather(*[convert_one(i) for i in range(5)])

        for result in results:
            assert result.exists()


class TestPathHandling:
    """Test various path handling scenarios."""

    @pytest.mark.asyncio
    async def test_relative_path(self, temp_dir):
        """Test conversion with relative path."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_path = temp_dir / "relative.png"
        img = Image.new("RGB", (50, 50), color="magenta")
        img.save(img_path, "PNG")
        img.close()

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            converter = ImageConverter()
            result = await converter.convert("relative.png", "jpg")
            assert result.exists()
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_absolute_path(self, temp_dir):
        """Test conversion with absolute path."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_path = temp_dir / "absolute.png"
        img = Image.new("RGB", (50, 50), color="lime")
        img.save(img_path, "PNG")
        img.close()

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(str(img_path.resolve()), "jpg", output_path=output)
        assert result.exists()

    @pytest.mark.asyncio
    async def test_symlink_source(self, temp_dir):
        """Test conversion when source is a symlink."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        real_file = temp_dir / "real.png"
        img = Image.new("RGB", (50, 50), color="pink")
        img.save(real_file, "PNG")
        img.close()

        symlink = temp_dir / "link.png"
        symlink.symlink_to(real_file)

        converter = ImageConverter()
        output = temp_dir / "output.jpg"

        result = await converter.convert(symlink, "jpg", output_path=output)
        assert result.exists()
