"""
Format converters for the MCP conversion server.

This package provides converters for:
- Images: JPEG, PNG, GIF, WebP, TIFF, BMP
- Video: MP4, AVI, MOV, WebM, MKV
- Audio: MP3, WAV, FLAC, AAC, OGG, M4A
- Ebooks: EPUB, PDF, MOBI, AZW3, TXT
"""

from .image import ImageConverter
from .video import VideoConverter
from .audio import AudioConverter
from .ebook import EbookConverter
from .router import ConverterRouter, router

__all__ = [
    "ImageConverter",
    "VideoConverter",
    "AudioConverter",
    "EbookConverter",
    "ConverterRouter",
    "router",
]
