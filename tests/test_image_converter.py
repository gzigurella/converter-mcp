"""
Tests for image converter.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.converter.converters.image import (
    ImageConverter,
    SUPPORTED_INPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
)


class TestImageConverter:
    """Tests for ImageConverter class."""

    def test_is_format_supported_input(self):
        """Test input format support check."""
        assert ImageConverter.is_format_supported("jpg") is True
        assert ImageConverter.is_format_supported("png") is True
        assert ImageConverter.is_format_supported("svg") is True

    def test_is_format_supported_output(self):
        """Test output format support check."""
        assert ImageConverter.is_format_supported("webp", for_output=True) is True
        assert ImageConverter.is_format_supported("svg", for_output=True) is False

    def test_get_supported_formats(self):
        """Test getting supported formats."""
        input_formats, output_formats = ImageConverter.get_supported_formats()
        assert "jpg" in input_formats
        assert "png" in output_formats

    def test_quality_presets(self):
        """Test quality preset resolution."""
        converter = ImageConverter()
        assert converter._resolve_quality("low") == 60
        assert converter._resolve_quality("medium") == 85
        assert converter._resolve_quality("high") == 95
        assert converter._resolve_quality(50) == 50
        assert converter._resolve_quality(150) == 100

    @pytest.mark.asyncio
    async def test_convert_unsupported_format(self):
        """Test conversion with unsupported format raises error."""
        converter = ImageConverter()

        with pytest.raises(Exception) as exc_info:
            await converter.convert("test.jpg", "svg")

        assert "not supported" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_convert_success(self, tmp_path):
        """Test successful image conversion."""
        converter = ImageConverter()

        source = tmp_path / "test.png"
        output = tmp_path / "test.jpg"

        with patch.object(converter, "_convert_sync", return_value=output):
            result = await converter.convert(source, "jpg", output)

        assert result == output

    def test_svg_in_input_formats(self):
        """Test that SVG is in supported input formats."""
        assert "svg" in SUPPORTED_INPUT_FORMATS

    def test_svg_not_in_output_formats(self):
        """Test that SVG is NOT in supported output formats."""
        assert "svg" not in SUPPORTED_OUTPUT_FORMATS


class TestSVGConversion:
    """Tests for SVG to raster conversion."""

    @pytest.fixture
    def sample_svg(self, tmp_path):
        """Create a sample SVG file for testing."""
        svg_path = tmp_path / "test.svg"
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect x="10" y="10" width="80" height="80" fill="red"/>
</svg>"""
        svg_path.write_text(svg_content)
        return svg_path

    @pytest.mark.asyncio
    async def test_svg_to_png_conversion(self, sample_svg, tmp_path):
        """Test converting SVG to PNG."""
        try:
            import cairosvg
        except ImportError:
            pytest.skip("cairosvg not installed")

        converter = ImageConverter()
        output = tmp_path / "output.png"

        result = await converter.convert(sample_svg, "png", output_path=output)

        assert result.exists()
        assert result.suffix == ".png"
        assert result.stat().st_size > 0

    @pytest.mark.asyncio
    async def test_svg_to_jpg_conversion(self, sample_svg, tmp_path):
        """Test converting SVG to JPG."""
        try:
            import cairosvg
        except ImportError:
            pytest.skip("cairosvg not installed")

        converter = ImageConverter()
        output = tmp_path / "output.jpg"

        result = await converter.convert(sample_svg, "jpg", output_path=output)

        assert result.exists()
        assert result.suffix == ".jpg"

    @pytest.mark.asyncio
    async def test_svg_to_webp_conversion(self, sample_svg, tmp_path):
        """Test converting SVG to WebP."""
        try:
            import cairosvg
        except ImportError:
            pytest.skip("cairosvg not installed")

        converter = ImageConverter()
        output = tmp_path / "output.webp"

        result = await converter.convert(sample_svg, "webp", output_path=output)

        assert result.exists()
        assert result.suffix == ".webp"

    @pytest.mark.asyncio
    async def test_svg_with_resize(self, sample_svg, tmp_path):
        """Test converting SVG with custom resize."""
        try:
            import cairosvg
        except ImportError:
            pytest.skip("cairosvg not installed")

        converter = ImageConverter()
        output = tmp_path / "output.png"

        result = await converter.convert(sample_svg, "png", output_path=output, resize=(200, 200))

        assert result.exists()

    @pytest.mark.asyncio
    async def test_svg_output_not_supported(self, tmp_path):
        """Test that converting TO SVG raises an error."""
        converter = ImageConverter()

        source = tmp_path / "test.png"
        source.touch()

        with pytest.raises(Exception) as exc_info:
            await converter.convert(source, "svg")

        assert "not supported" in str(exc_info.value).lower()

    def test_convert_svg_to_raster_missing_cairosvg(self, sample_svg, tmp_path):
        """Test that missing cairosvg raises helpful error."""
        converter = ImageConverter()
        output = tmp_path / "output.png"

        with patch.dict("sys.modules", {"cairosvg": None}):
            with patch(
                "builtins.__import__", side_effect=ImportError("No module named 'cairosvg'")
            ):
                with pytest.raises(Exception) as exc_info:
                    converter._convert_svg_to_raster(sample_svg, output, "png", 85, None)

                assert "cairosvg" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_svg_file(self, tmp_path):
        """Test that invalid SVG raises conversion error."""
        try:
            import cairosvg
        except ImportError:
            pytest.skip("cairosvg not installed")

        converter = ImageConverter()

        invalid_svg = tmp_path / "invalid.svg"
        invalid_svg.write_text("not valid svg content")

        output = tmp_path / "output.png"

        with pytest.raises(Exception):
            await converter.convert(invalid_svg, "png", output_path=output)
