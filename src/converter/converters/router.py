"""
Format detection and conversion routing.

Provides intelligent format detection and routes conversions
to the appropriate converter.
"""

import shutil
from pathlib import Path
from typing import Optional, Tuple, Type

from .image import (
    ImageConverter,
    SUPPORTED_INPUT_FORMATS as IMG_IN,
    SUPPORTED_OUTPUT_FORMATS as IMG_OUT,
)
from .video import (
    VideoConverter,
    SUPPORTED_INPUT_FORMATS as VID_IN,
    SUPPORTED_OUTPUT_FORMATS as VID_OUT,
)
from .audio import (
    AudioConverter,
    SUPPORTED_INPUT_FORMATS as AUD_IN,
    SUPPORTED_OUTPUT_FORMATS as AUD_OUT,
)
from .ebook import (
    EbookConverter,
    SUPPORTED_INPUT_FORMATS as EBOOK_IN,
    SUPPORTED_OUTPUT_FORMATS as EBOOK_OUT,
)

from ..logging_config import FormatNotSupportedError, get_logger

logger = get_logger("converters.router")


class ConverterRouter:
    """Route conversion requests to appropriate converters."""

    def __init__(self):
        self._image_converter: Optional[ImageConverter] = None
        self._video_converter: Optional[VideoConverter] = None
        self._audio_converter: Optional[AudioConverter] = None
        self._ebook_converter: Optional[EbookConverter] = None

    @property
    def image(self) -> ImageConverter:
        if self._image_converter is None:
            self._image_converter = ImageConverter()
        return self._image_converter

    @property
    def video(self) -> VideoConverter:
        if self._video_converter is None:
            self._video_converter = VideoConverter()
        return self._video_converter

    @property
    def audio(self) -> AudioConverter:
        if self._audio_converter is None:
            self._audio_converter = AudioConverter()
        return self._audio_converter

    @property
    def ebook(self) -> EbookConverter:
        if self._ebook_converter is None:
            self._ebook_converter = EbookConverter()
        return self._ebook_converter

    @staticmethod
    def get_converter_type(source_format: str, target_format: str) -> str:
        """
        Determine which converter to use based on formats.

        Returns:
            'image', 'video', 'audio', 'ebook', or raises error
        """
        src = source_format.lower()
        tgt = target_format.lower()

        if src in IMG_IN and tgt in IMG_OUT:
            return "image"

        if src in VID_IN and tgt in VID_OUT:
            return "video"

        if src in VID_IN and tgt in AUD_OUT:
            return "video"

        if src in AUD_IN and tgt in AUD_OUT:
            return "audio"

        if src in EBOOK_IN and tgt in EBOOK_OUT:
            return "ebook"

        raise FormatNotSupportedError(
            f"Conversion from '{source_format}' to '{target_format}' is not supported",
            suggestion="Check supported formats for each converter type",
        )

    def get_supported_conversions(self) -> dict:
        """Get all supported conversion paths."""
        return {
            "image": {
                "input": sorted(IMG_IN),
                "output": sorted(IMG_OUT),
            },
            "video": {
                "input": sorted(VID_IN),
                "output": sorted(VID_OUT),
            },
            "audio": {
                "input": sorted(AUD_IN),
                "output": sorted(AUD_OUT),
            },
            "ebook": {
                "input": sorted(EBOOK_IN),
                "output": sorted(EBOOK_OUT),
            },
        }

    def is_conversion_supported(self, source_format: str, target_format: str) -> bool:
        """Check if a conversion path is supported."""
        try:
            self.get_converter_type(source_format, target_format)
            return True
        except FormatNotSupportedError:
            return False

    async def convert(
        self,
        source_path: str | Path,
        target_format: str,
        output_path: Optional[Path] = None,
        quality: str = "medium",
        **kwargs,
    ) -> Path:
        """
        Route conversion to appropriate converter.

        Args:
            source_path: Path to source file
            target_format: Target format
            output_path: Optional output path
            quality: Quality preset
            **kwargs: Additional converter-specific options

        Returns:
            Path to converted file
        """
        source = Path(source_path)
        source_format = source.suffix.lstrip(".")

        converter_type = self.get_converter_type(source_format, target_format)

        if converter_type == "image":
            return await self.image.convert(source, target_format, output_path, quality, **kwargs)
        elif converter_type == "video":
            if target_format.lower() in AUD_OUT:
                return await self.video.extract_audio(source, output_path, target_format, **kwargs)
            return await self.video.convert(source, target_format, output_path, quality, **kwargs)
        elif converter_type == "audio":
            return await self.audio.convert(source, target_format, output_path, quality, **kwargs)
        elif converter_type == "ebook":
            return await self.ebook.convert(source, target_format, output_path, **kwargs)
        else:
            raise FormatNotSupportedError(f"Unknown converter type: {converter_type}")


router = ConverterRouter()
