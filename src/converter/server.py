"""MCP Server for Format Conversion.

This module provides a FastMCP-based MCP server for bidirectional format conversion
supporting video, audio, images, and ebooks.
"""

import asyncio
import logging
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .deps import DependencyError, verify_dependencies


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Handle graceful shutdown of the MCP server."""

    def __init__(self):
        self._shutdown = False
        self._tasks: set[asyncio.Task] = set()

    def is_shutting_down(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown

    def initiate_shutdown(self):
        """Initiate graceful shutdown."""
        if not self._shutdown:
            self._shutdown = True
            logger.info("Shutdown signal received, cleaning up...")

    def register_task(self, task: asyncio.Task):
        """Register a task to be tracked during shutdown."""
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.discard(t))

    async def wait_for_tasks(self, timeout: float = 10.0):
        """Wait for registered tasks to complete with timeout."""
        if not self._tasks:
            return

        logger.info(f"Waiting for {len(self._tasks)} tasks to complete...")
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout=timeout
            )
            logger.info("All tasks completed successfully")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for tasks after {timeout}s")


shutdown_handler = GracefulShutdown()


@asynccontextmanager
async def server_lifespan(app: FastMCP):
    """Manage server startup and shutdown.

    This context manager handles:
    - Dependency verification at startup
    - Graceful shutdown of running tasks
    - Cleanup of temporary files
    """
    temp_dirs: list[Path] = []

    try:
        logger.info("Starting Format Converter MCP Server...")
        logger.info("Verifying system dependencies...")
        try:
            deps = await verify_dependencies()
            logger.info(
                f"Dependencies verified: "
                f"Python {deps['python']['message'].split()[1]}, "
                f"FFmpeg {'✓' if deps['ffmpeg']['installed'] else '✗'}, "
                f"Calibre {'✓' if deps['calibre']['installed'] else '✗'}"
            )
        except DependencyError as e:
            logger.error(f"Dependency check failed: {e}")
            raise

        yield

    finally:
        logger.info("Shutting down server...")
        shutdown_handler.initiate_shutdown()
        await shutdown_handler.wait_for_tasks()

        logger.info("Cleaning up temporary files...")
        import shutil

        for temp_dir in temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.info(f"Removed temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")

        logger.info("Server shutdown complete")


mcp = FastMCP(
    name="Format Converter",
    instructions=(
        "MCP server for bidirectional format conversion. "
        "Supports video, audio, images, and ebook formats. "
        "All conversions use subprocess calls for memory efficiency."
    ),
    lifespan=server_lifespan,
)


@mcp.tool()
async def convert_file(
    source: str,
    target_format: str,
    output_dir: str | None = None,
    quality: str = "medium",
) -> dict[str, Any]:
    """Convert file to target format.

    This tool provides bidirectional format conversion for:
    - Video: MP4, AVI, MOV, WebM
    - Audio: MP3, AAC, FLAC, WAV, OGG
    - Images: JPG, PNG, GIF, WebP, TIFF
    - Ebooks: EPUB, PDF, MOBI, AZW3

    Args:
        source: Path to source file (absolute or relative to current directory)
        target_format: Target format (e.g., 'jpg', 'png', 'mp4', 'webm', 'mp3', 'epub', 'pdf')
        output_dir: Optional output directory (default: same directory as source)
        quality: Quality preset - 'low', 'medium', or 'high' (default: 'medium')

    Returns:
        dict with:
            - status: 'success', 'pending', 'error'
            - output_path: Path to converted file (on success)
            - message: Status message or error description
            - format: Target format achieved

    Raises:
        ValueError: If source file doesn't exist or target format is invalid
        RuntimeError: If conversion fails
    """
    from pathlib import Path
    from .converters.router import router
    from .file_manager import FileManager

    logger.info(f"Conversion requested: {source} -> {target_format}")

    if shutdown_handler.is_shutting_down():
        return {
            "status": "error",
            "output_path": None,
            "message": "Server is shutting down, new conversions not accepted",
            "format": target_format,
        }

    source_path = Path(source)
    if not source_path.exists():
        raise ValueError(f"Source file not found: {source}")

    if not source_path.is_file():
        raise ValueError(f"Source path is not a file: {source}")

    valid_qualities = ["low", "medium", "high"]
    if quality not in valid_qualities:
        raise ValueError(
            f"Invalid quality '{quality}'. Must be one of: {', '.join(valid_qualities)}"
        )

    file_manager = FileManager(output_dir=output_dir)
    output_path = file_manager.resolve_output_path(source_path, target_format)

    try:
        result_path = await router.convert(
            source_path,
            target_format,
            output_path=output_path,
            quality=quality,
        )

        logger.info(f"Conversion complete: {result_path}")

        return {
            "status": "success",
            "output_path": str(result_path),
            "message": f"Successfully converted {source_path.name} to {target_format}",
            "format": target_format,
        }

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return {
            "status": "error",
            "output_path": str(output_path),
            "message": str(e),
            "format": target_format,
        }


@mcp.tool()
async def list_supported_formats() -> dict[str, list[str]]:
    """List all supported formats for conversion.

    Returns:
        dict with format categories and their supported formats:
            - video: List of video formats
            - audio: List of audio formats
            - image: List of image formats
            - ebook: List of ebook formats
    """
    from .converters.router import router

    conversions = router.get_supported_conversions()
    return {
        "image": conversions["image"]["input"],
        "video": conversions["video"]["input"],
        "audio": conversions["audio"]["input"],
        "ebook": conversions["ebook"]["input"],
    }


@mcp.tool()
async def get_conversion_info(source_format: str, target_format: str) -> dict[str, Any]:
    """Get information about a specific conversion path.

    Args:
        source_format: Source format (e.g., 'jpg', 'mp4')
        target_format: Target format (e.g., 'png', 'webm')

    Returns:
        dict with conversion information:
            - supported: Whether this conversion is supported
            - category: Format category (video, audio, image, ebook)
            - quality_options: Available quality presets
            - notes: Any notes about this conversion
    """
    from .converters.router import router

    source_format = source_format.lower()
    target_format = target_format.lower()

    is_supported = router.is_conversion_supported(source_format, target_format)

    try:
        category = router.get_converter_type(source_format, target_format)
    except Exception:
        category = None

    return {
        "supported": is_supported,
        "category": category,
        "quality_options": ["low", "medium", "high"] if is_supported else [],
        "notes": (
            f"Direct {category} conversion supported"
            if is_supported
            else f"Conversion not supported from {source_format} to {target_format}"
        ),
    }


def main():
    """Main entry point for the MCP server.

    Note: mcp.run() manages its own event loop via anyio, so we call it
    synchronously without wrapping in asyncio.run().
    """
    try:
        logger.info("Starting server with stdio transport...")
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        shutdown_handler.initiate_shutdown()
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
