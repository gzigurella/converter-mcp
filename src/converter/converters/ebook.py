"""
Ebook converter using Calibre CLI.

Supports conversions between common ebook formats:
- EPUB, PDF, MOBI, AZW3, TXT
"""

import asyncio
import shutil
from pathlib import Path
from typing import Optional

from ..async_utils import safe_subprocess, concurrency_limiter
from ..file_manager import FileManager
from ..logging_config import ConversionError, FormatNotSupportedError, get_logger

logger = get_logger("converters.ebook")

SUPPORTED_INPUT_FORMATS = {"epub", "pdf", "mobi", "azw", "azw3", "txt", "rtf", "html", "docx"}
SUPPORTED_OUTPUT_FORMATS = {"epub", "pdf", "mobi", "azw3", "txt"}

PAPER_SIZE_MAP = {
    "a4": "595x842",
    "a5": "420x595",
    "letter": "612x792",
}


class EbookConverter:
    """Convert ebooks between formats using Calibre ebook-convert."""

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
    def get_supported_formats() -> tuple[set, set]:
        """Get supported input and output formats."""
        return SUPPORTED_INPUT_FORMATS.copy(), SUPPORTED_OUTPUT_FORMATS.copy()

    async def convert(
        self,
        source_path: str | Path,
        target_format: str,
        output_path: Optional[Path] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        paper_size: Optional[str] = None,
        pdf_margin: Optional[str] = None,
    ) -> Path:
        """
        Convert an ebook to the target format.

        Args:
            source_path: Path to source ebook
            target_format: Target format (epub, pdf, mobi, azw3, txt)
            output_path: Optional output path (auto-generated if not provided)
            title: Optional title override
            author: Optional author override
            paper_size: Paper size for PDF output (a4, a5, letter)
            pdf_margin: Margin for PDF output (e.g., "36pt")

        Returns:
            Path to the converted ebook

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

        cmd = self._build_calibre_command(
            source, output_path, target_format, title, author, paper_size, pdf_margin
        )

        async with concurrency_limiter:
            try:
                returncode, stdout, stderr = await safe_subprocess(cmd, timeout=600)

                if returncode != 0:
                    raise ConversionError(
                        f"Ebook conversion failed",
                        suggestion=f"Check if Calibre is installed and source file is valid. stderr: {stderr[-500:]}",
                    )

            except asyncio.TimeoutError:
                raise ConversionError(
                    "Ebook conversion timed out",
                    suggestion="Large ebooks may take longer. Try again or use a smaller file.",
                )

        logger.info(f"Converted {source} -> {output_path}")
        return output_path

    def _build_calibre_command(
        self,
        source: Path,
        output: Path,
        target_format: str,
        title: Optional[str],
        author: Optional[str],
        paper_size: Optional[str],
        pdf_margin: Optional[str],
    ) -> list[str]:
        """Build Calibre ebook-convert command."""
        cmd = [
            "ebook-convert",
            str(source),
            str(output),
        ]

        if title:
            cmd.extend(["--title", title])

        if author:
            cmd.extend(["--authors", author])

        if target_format == "pdf":
            if paper_size:
                cmd.extend(["--paper-size", paper_size])
            else:
                cmd.extend(["--paper-size", "a4"])

            if pdf_margin:
                cmd.extend(["--pdf-page-margin-left", pdf_margin])
                cmd.extend(["--pdf-page-margin-right", pdf_margin])
                cmd.extend(["--pdf-page-margin-top", pdf_margin])
                cmd.extend(["--pdf-page-margin-bottom", pdf_margin])

            cmd.extend(["--pdf-default-font-size", "12"])
            cmd.extend(["--pdf-mono-font-size", "12"])

        return cmd

    async def get_ebook_metadata(self, source_path: str | Path) -> dict:
        """
        Get metadata from an ebook file.

        Args:
            source_path: Path to ebook file

        Returns:
            Dictionary with ebook metadata
        """
        source = Path(source_path)

        cmd = [
            "ebook-meta",
            str(source),
        ]

        returncode, stdout, stderr = await safe_subprocess(cmd, timeout=30)

        if returncode != 0:
            return {"error": stderr}

        return self._parse_metadata(stdout)

    def _parse_metadata(self, output: str) -> dict:
        """Parse ebook-meta output into dictionary."""
        metadata = {}
        for line in output.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip().lower().replace(" ", "_")] = value.strip()
        return metadata
