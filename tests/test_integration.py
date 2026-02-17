"""
Integration tests for format conversion with real files.

Tests end-to-end conversion workflows with actual file operations.
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
from src.converter.converters.audio import AudioConverter
from src.converter.converters.ebook import EbookConverter
from src.converter.converters.router import ConverterRouter
from src.converter.file_manager import FileManager
from src.converter.progress import ProgressReporter, ProgressStage


pytestmark = pytest.mark.integration


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp(prefix="converter_test_")
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def sample_image(temp_dir):
    """Create a sample image file for testing."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    img_path = temp_dir / "test_image.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, "PNG")
    return img_path


@pytest.fixture
def sample_video(temp_dir):
    """Create a sample video file using FFmpeg."""
    video_path = temp_dir / "test_video.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x240:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(video_path),
    ]

    import subprocess

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        pytest.skip("FFmpeg not available or failed to create test video")

    return video_path


@pytest.fixture
def sample_audio(temp_dir):
    """Create a sample audio file using FFmpeg."""
    audio_path = temp_dir / "test_audio.mp3"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:a",
        "libmp3lame",
        str(audio_path),
    ]

    import subprocess

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        pytest.skip("FFmpeg not available or failed to create test audio")

    return audio_path


@pytest.fixture
def sample_epub(temp_dir):
    """Create a minimal EPUB file for testing."""
    try:
        import zipfile
    except ImportError:
        pytest.skip("zipfile not available")

    epub_path = temp_dir / "test_book.epub"

    with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "content.opf",
            """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
    <dc:creator>Test Author</dc:creator>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="nav"/>
  </spine>
</package>""",
        )
        zf.writestr(
            "nav.xhtml",
            """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test</title></head>
<body><p>Test content</p></body>
</html>""",
        )

    return epub_path


class TestImageConversionIntegration:
    """Integration tests for image conversion."""

    @pytest.mark.asyncio
    async def test_png_to_jpg_conversion(self, sample_image, temp_dir):
        """Test converting PNG to JPG."""
        converter = ImageConverter()
        output_path = temp_dir / "output.jpg"

        result = await converter.convert(
            sample_image, "jpg", output_path=output_path, quality="high"
        )

        assert result.exists()
        assert result.suffix == ".jpg"
        assert result.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_png_to_webp_conversion(self, sample_image, temp_dir):
        """Test converting PNG to WebP."""
        converter = ImageConverter()
        output_path = temp_dir / "output.webp"

        result = await converter.convert(sample_image, "webp", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".webp"

    @pytest.mark.asyncio
    async def test_png_to_gif_conversion(self, sample_image, temp_dir):
        """Test converting PNG to GIF."""
        converter = ImageConverter()
        output_path = temp_dir / "output.gif"

        result = await converter.convert(sample_image, "gif", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".gif"

    @pytest.mark.asyncio
    async def test_image_quality_presets(self, sample_image, temp_dir):
        """Test different quality presets produce different file sizes."""
        converter = ImageConverter()

        qualities = ["low", "medium", "high"]
        sizes = []

        for quality in qualities:
            output_path = temp_dir / f"output_{quality}.jpg"
            await converter.convert(sample_image, "jpg", output_path=output_path, quality=quality)
            sizes.append(output_path.stat().st_size)

        assert sizes[0] <= sizes[1] <= sizes[2]


class TestVideoConversionIntegration:
    """Integration tests for video conversion."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mp4_to_webm_conversion(self, sample_video, temp_dir):
        """Test converting MP4 to WebM."""
        converter = VideoConverter()
        output_path = temp_dir / "output.webm"

        result = await converter.convert(
            sample_video, "webm", output_path=output_path, quality="low"
        )

        assert result.exists()
        assert result.suffix == ".webm"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_mp4_to_avi_conversion(self, sample_video, temp_dir):
        """Test converting MP4 to AVI."""
        converter = VideoConverter()
        output_path = temp_dir / "output.avi"

        result = await converter.convert(
            sample_video, "avi", output_path=output_path, quality="low"
        )

        assert result.exists()
        assert result.suffix == ".avi"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_video_with_progress_callback(self, sample_video, temp_dir):
        """Test video conversion with progress reporting."""
        converter = VideoConverter()
        output_path = temp_dir / "output.webm"

        progress_values = []

        def callback(percent):
            progress_values.append(percent)

        result = await converter.convert(
            sample_video, "webm", output_path=output_path, quality="low", progress_callback=callback
        )

        assert result.exists()
        assert len(progress_values) > 0
        assert progress_values[-1] == 100.0


class TestAudioConversionIntegration:
    """Integration tests for audio conversion."""

    @pytest.mark.asyncio
    async def test_mp3_to_wav_conversion(self, sample_audio, temp_dir):
        """Test converting MP3 to WAV."""
        converter = AudioConverter()
        output_path = temp_dir / "output.wav"

        result = await converter.convert(sample_audio, "wav", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".wav"

    @pytest.mark.asyncio
    async def test_mp3_to_flac_conversion(self, sample_audio, temp_dir):
        """Test converting MP3 to FLAC."""
        converter = AudioConverter()
        output_path = temp_dir / "output.flac"

        result = await converter.convert(sample_audio, "flac", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".flac"

    @pytest.mark.asyncio
    async def test_mp3_to_aac_conversion(self, sample_audio, temp_dir):
        """Test converting MP3 to AAC."""
        converter = AudioConverter()
        output_path = temp_dir / "output.aac"

        result = await converter.convert(sample_audio, "aac", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".aac"


class TestEbookConversionIntegration:
    """Integration tests for ebook conversion."""

    @pytest.mark.asyncio
    async def test_epub_to_pdf_conversion(self, sample_epub, temp_dir):
        """Test converting EPUB to PDF using Calibre."""
        import subprocess

        result = subprocess.run(["which", "ebook-convert"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Calibre ebook-convert not available")

        converter = EbookConverter()
        output_path = temp_dir / "output.pdf"

        result = await converter.convert(sample_epub, "pdf", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".pdf"

    @pytest.mark.asyncio
    async def test_epub_to_mobi_conversion(self, sample_epub, temp_dir):
        """Test converting EPUB to MOBI using Calibre."""
        import subprocess

        result = subprocess.run(["which", "ebook-convert"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("Calibre ebook-convert not available")

        converter = EbookConverter()
        output_path = temp_dir / "output.mobi"

        result = await converter.convert(sample_epub, "mobi", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".mobi"


class TestRouterIntegration:
    """Integration tests for the conversion router."""

    @pytest.mark.asyncio
    async def test_router_image_conversion(self, sample_image, temp_dir):
        """Test router correctly routes image conversions."""
        router = ConverterRouter()
        output_path = temp_dir / "output.jpg"

        result = await router.convert(sample_image, "jpg", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".jpg"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_router_video_conversion(self, sample_video, temp_dir):
        """Test router correctly routes video conversions."""
        router = ConverterRouter()
        output_path = temp_dir / "output.webm"

        result = await router.convert(sample_video, "webm", output_path=output_path, quality="low")

        assert result.exists()
        assert result.suffix == ".webm"

    @pytest.mark.asyncio
    async def test_router_audio_conversion(self, sample_audio, temp_dir):
        """Test router correctly routes audio conversions."""
        router = ConverterRouter()
        output_path = temp_dir / "output.wav"

        result = await router.convert(sample_audio, "wav", output_path=output_path)

        assert result.exists()
        assert result.suffix == ".wav"


class TestFileManagerIntegration:
    """Integration tests for file manager."""

    @pytest.mark.asyncio
    async def test_collision_handling(self, sample_image, temp_dir):
        """Test file collision auto-rename."""
        fm = FileManager(output_dir=str(temp_dir))

        path1 = fm.resolve_output_path(sample_image, "jpg")
        path1.touch()

        path2 = fm.resolve_output_path(sample_image, "jpg")

        assert path1 != path2
        assert "_1" in str(path2) or path2.suffix == ".jpg"

    def test_disk_space_check(self, temp_dir):
        """Test disk space verification."""
        fm = FileManager()

        result = fm.check_disk_space(str(temp_dir))

        assert result is True


class TestProgressReportingIntegration:
    """Integration tests for progress reporting."""

    @pytest.mark.asyncio
    async def test_progress_reporter_with_conversion(self, sample_image, temp_dir):
        """Test progress reporter tracks conversion progress."""
        reporter = ProgressReporter()
        converter = ImageConverter()
        output_path = temp_dir / "output.jpg"

        job_id = "test-job-1"

        await reporter.start_job(job_id, message="Starting conversion")

        result = await converter.convert(sample_image, "jpg", output_path=output_path)

        final_info = await reporter.complete_job(job_id, success=True)

        assert result.exists()
        assert final_info.stage == ProgressStage.COMPLETE

    @pytest.mark.asyncio
    async def test_concurrent_progress_tracking(self, sample_image, temp_dir):
        """Test tracking progress for concurrent conversions."""
        reporter = ProgressReporter()
        converter = ImageConverter()

        job_ids = ["job-1", "job-2", "job-3"]

        for job_id in job_ids:
            await reporter.start_job(job_id, message=f"Starting {job_id}")

        async def convert_job(job_id, idx):
            output_path = temp_dir / f"output_{idx}.jpg"
            await converter.convert(sample_image, "jpg", output_path=output_path)
            await reporter.complete_job(job_id, success=True)

        await asyncio.gather(*[convert_job(job_id, i) for i, job_id in enumerate(job_ids)])

        for job_id in job_ids:
            assert reporter.get_job(job_id) is None


class TestCleanupVerification:
    """Verify cleanup after conversions."""

    @pytest.mark.asyncio
    async def test_no_temp_files_left(self, sample_image, temp_dir):
        """Verify no temp files remain after conversion."""
        converter = ImageConverter()
        output_path = temp_dir / "output.jpg"

        temp_files_before = set(temp_dir.glob("*.tmp"))

        await converter.convert(sample_image, "jpg", output_path=output_path)

        temp_files_after = set(temp_dir.glob("*.tmp"))

        assert temp_files_before == temp_files_after

    @pytest.mark.asyncio
    async def test_output_in_correct_location(self, sample_image, temp_dir):
        """Verify output file is in the correct location."""
        output_dir = temp_dir / "output"
        output_dir.mkdir()

        fm = FileManager(output_dir=str(output_dir))
        converter = ImageConverter(file_manager=fm)

        result = await converter.convert(sample_image, "jpg")

        assert result.parent == output_dir


class TestEdgeCases:
    """Edge case testing."""

    @pytest.mark.asyncio
    async def test_same_format_conversion(self, sample_image, temp_dir):
        """Test converting to the same format."""
        converter = ImageConverter()
        output_path = temp_dir / "output.png"

        result = await converter.convert(sample_image, "png", output_path=output_path)

        assert result.exists()

    @pytest.mark.asyncio
    async def test_special_characters_in_path(self, temp_dir):
        """Test handling special characters in file paths."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        special_name = "test file (1).png"
        img_path = temp_dir / special_name
        img = Image.new("RGB", (50, 50), color="blue")
        img.save(img_path, "PNG")

        converter = ImageConverter()
        output_path = temp_dir / "output.jpg"

        result = await converter.convert(img_path, "jpg", output_path=output_path)

        assert result.exists()

    @pytest.mark.asyncio
    async def test_empty_directory_output(self, sample_image):
        """Test output to a directory that gets created."""
        temp_base = tempfile.mkdtemp(prefix="converter_test_empty_")
        try:
            output_dir = Path(temp_base) / "new" / "nested" / "dir"

            fm = FileManager(output_dir=str(output_dir))
            converter = ImageConverter(file_manager=fm)

            result = await converter.convert(sample_image, "jpg")

            assert result.exists()
            assert output_dir.exists()
        finally:
            shutil.rmtree(temp_base, ignore_errors=True)
