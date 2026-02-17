"""
Image converter using Pillow + CairoSVG.

Supports conversions between common image formats:
- Input: JPEG, PNG, GIF, WebP, TIFF, BMP, SVG
- Output: JPEG, PNG, GIF, WebP, TIFF, BMP

SVG is input-only (raster to vector conversion not supported).
"""

import asyncio
from pathlib import Path
from typing import Optional, Tuple

from ..async_utils import concurrency_limiter
from ..file_manager import FileManager
from ..logging_config import ConversionError, FormatNotSupportedError, get_logger

logger = get_logger("converters.image")

SUPPORTED_INPUT_FORMATS = {"jpg", "jpeg", "png", "gif", "webp", "tiff", "tif", "bmp", "svg"}
SUPPORTED_OUTPUT_FORMATS = {"jpg", "jpeg", "png", "gif", "webp", "tiff", "bmp"}

FORMAT_MIME_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "gif": "GIF",
    "webp": "WEBP",
    "tiff": "TIFF",
    "tif": "TIFF",
    "bmp": "BMP",
    "svg": "SVG",
}

QUALITY_PRESETS = {
    "low": 60,
    "medium": 85,
    "high": 95,
}


class ImageConverter:
    """Convert images between formats using Pillow."""

    def __init__(self, file_manager: Optional[FileManager] = None):
        self.file_manager = file_manager or FileManager()

    @staticmethod
    def is_format_supported(format_name: str, for_output: bool = False) -> bool:
        """Check if a format is supported."""
        format_lower = format_name.lower()
        if for_output:
            return format_lower in SUPPORTED_OUTPUT_FORMATS
        return format_lower in SUPPORTED_INPUT_FORMATS

    @staticmethod
    def get_supported_formats() -> Tuple[set, set]:
        """Get supported input and output formats."""
        return SUPPORTED_INPUT_FORMATS.copy(), SUPPORTED_OUTPUT_FORMATS.copy()

    async def convert(
        self,
        source_path: str | Path,
        target_format: str,
        output_path: Optional[Path] = None,
        quality: str = "medium",
        resize: Optional[Tuple[int, int]] = None,
    ) -> Path:
        """
        Convert an image to the target format.

        Args:
            source_path: Path to source image
            target_format: Target format (jpg, png, gif, webp, tiff, bmp)
            output_path: Optional output path (auto-generated if not provided)
            quality: Quality preset (low, medium, high) or numeric 1-100
            resize: Optional tuple of (width, height) to resize

        Returns:
            Path to the converted image

        Raises:
            FormatNotSupportedError: If format is not supported
            ConversionError: If conversion fails
        """
        source = Path(source_path)
        target_format = target_format.lower()

        if not self.is_format_supported(target_format, for_output=True):
            raise FormatNotSupportedError(
                f"Output format '{target_format}' is not supported",
                suggestion=f"Supported formats: {', '.join(sorted(SUPPORTED_OUTPUT_FORMATS))}",
            )

        if output_path is None:
            output_path = self.file_manager.resolve_output_path(source, target_format)

        quality_value = self._resolve_quality(quality)

        async with concurrency_limiter:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._convert_sync,
                source,
                output_path,
                target_format,
                quality_value,
                resize,
            )

        logger.info(f"Converted {source} -> {output_path}")
        return result

    def _resolve_quality(self, quality: str | int) -> int:
        """Resolve quality preset to numeric value."""
        if isinstance(quality, int):
            return max(1, min(100, quality))
        return QUALITY_PRESETS.get(quality.lower(), QUALITY_PRESETS["medium"])

    def _convert_sync(
        self,
        source: Path,
        output: Path,
        target_format: str,
        quality: int,
        resize: Optional[Tuple[int, int]],
    ) -> Path:
        """Synchronous conversion using Pillow."""
        source_format = source.suffix.lower().lstrip(".")

        if source_format == "svg":
            return self._convert_svg_to_raster(source, output, target_format, quality, resize)

        return self._convert_pillow(source, output, target_format, quality, resize)

    def _convert_pillow(
        self,
        source: Path,
        output: Path,
        target_format: str,
        quality: int,
        resize: Optional[Tuple[int, int]],
    ) -> Path:
        """Convert raster images using Pillow."""
        from PIL import Image

        pillow_format = FORMAT_MIME_MAP.get(target_format, target_format.upper())

        with Image.open(source) as img:
            if resize:
                img = img.resize(resize, Image.Resampling.LANCZOS)

            save_kwargs = {"format": pillow_format}

            if pillow_format == "JPEG":
                save_kwargs["quality"] = quality
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
            elif pillow_format == "WEBP":
                save_kwargs["quality"] = quality
            elif pillow_format == "PNG":
                save_kwargs["optimize"] = True

            output.parent.mkdir(parents=True, exist_ok=True)
            img.save(output, **save_kwargs)

        return output

    def _convert_svg_to_raster(
        self,
        source: Path,
        output: Path,
        target_format: str,
        quality: int,
        resize: Optional[Tuple[int, int]],
    ) -> Path:
        """Convert SVG to raster format using cairosvg + Pillow."""
        import tempfile

        try:
            import cairosvg
        except ImportError as e:
            raise ConversionError(
                "SVG conversion requires cairosvg library",
                suggestion="Install with: pip install cairosvg\n"
                "Note: cairosvg requires Cairo system library (libcairo2-dev on Ubuntu/Debian)",
            ) from e

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_png = Path(tmp.name)

        try:
            cairosvg.svg2png(
                url=str(source),
                write_to=str(tmp_png),
                dpi=96,
            )

            if resize:
                from PIL import Image

                with Image.open(tmp_png) as img:
                    resized = img.resize(resize, Image.Resampling.LANCZOS)
                    resized.save(tmp_png, format="PNG")

            return self._convert_pillow(tmp_png, output, target_format, quality, None)

        except (ValueError, TypeError) as e:
            raise ConversionError(
                f"Invalid SVG file: {source}",
                suggestion="Ensure the SVG file is valid XML with proper structure",
            ) from e
        except Exception as e:
            raise ConversionError(f"SVG conversion failed: {e}") from e
        finally:
            if tmp_png.exists():
                tmp_png.unlink()

    async def get_image_info(self, source_path: str | Path) -> dict:
        """
        Get information about an image file.

        Args:
            source_path: Path to image file

        Returns:
            Dictionary with image information
        """
        source = Path(source_path)

        def _get_info():
            from PIL import Image

            with Image.open(source) as img:
                return {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                }

        return await asyncio.get_event_loop().run_in_executor(None, _get_info)
