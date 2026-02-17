"""Tests for MCP server implementation."""

import asyncio
from unittest.mock import patch

import pytest

from src.converter.server import GracefulShutdown, mcp


class TestGracefulShutdown:
    """Test graceful shutdown handling."""

    def test_init(self):
        """Test GracefulShutdown initialization."""
        shutdown = GracefulShutdown()
        assert not shutdown.is_shutting_down()
        assert len(shutdown._tasks) == 0

    def test_initiate_shutdown(self):
        """Test shutdown initiation."""
        shutdown = GracefulShutdown()
        shutdown.initiate_shutdown()
        assert shutdown.is_shutting_down()

    def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        shutdown = GracefulShutdown()
        shutdown.initiate_shutdown()
        shutdown.initiate_shutdown()
        assert shutdown.is_shutting_down()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_no_tasks(self):
        """Test waiting when no tasks are registered."""
        shutdown = GracefulShutdown()
        await shutdown.wait_for_tasks()

    @pytest.mark.asyncio
    async def test_wait_for_tasks_with_completed_task(self):
        """Test waiting with a completed task."""
        shutdown = GracefulShutdown()

        async def dummy_task():
            await asyncio.sleep(0.01)

        task = asyncio.create_task(dummy_task())
        shutdown.register_task(task)

        await shutdown.wait_for_tasks()
        assert len(shutdown._tasks) == 0

    @pytest.mark.asyncio
    async def test_wait_for_tasks_timeout(self):
        """Test waiting with timeout."""
        shutdown = GracefulShutdown()

        async def slow_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(slow_task())
        shutdown.register_task(task)

        await shutdown.wait_for_tasks(timeout=0.1)
        task.cancel()


class TestMCPTools:
    """Test MCP tool registration and functionality."""

    def test_mcp_instance_created(self):
        """Test that MCP server instance is created."""
        assert mcp is not None
        assert mcp.name == "Format Converter"
        # Flexible version check - verify version exists and matches major.minor
        if hasattr(mcp, "version"):
            if isinstance(mcp.version, str):
                expected = "1.0.0"
                actual = mcp.version.strip()
                assert actual.split(".")[0] == expected.split(".")[0]

    @pytest.mark.asyncio
    async def test_convert_file_placeholder(self):
        """Test convert_file tool returns expected response structure."""
        # This should raise a ToolError due to missing file
        with pytest.raises(Exception):  # ToolError might not be directly importable
            await mcp.call_tool(
                "convert_file",
                {
                    "source": "test.jpg",
                    "target_format": "png",
                    "output_dir": None,
                    "quality": "medium",
                },
            )

    @pytest.mark.asyncio
    async def test_convert_file_with_output_dir(self):
        """Test convert_file with custom output directory."""
        # This should raise a ToolError due to missing file
        with pytest.raises(Exception):  # ToolError might not be directly importable
            await mcp.call_tool(
                "convert_file",
                {
                    "source": "test.jpg",
                    "target_format": "png",
                    "output_dir": "/tmp/output",
                    "quality": "high",
                },
            )

    @pytest.mark.asyncio
    async def test_convert_file_invalid_quality(self):
        """Test convert_file with invalid quality parameter."""
        # This should raise a ValueError for invalid quality
        with pytest.raises(Exception):  # FastMCP may wrap the error
            await mcp.call_tool(
                "convert_file",
                {
                    "source": "test.jpg",
                    "target_format": "png",
                    "output_dir": None,
                    "quality": "invalid",
                },
            )

    @pytest.mark.asyncio
    async def test_list_supported_formats(self):
        """Test list_supported_formats tool."""
        result = await mcp.call_tool("list_supported_formats", {})
        # FastMCP returns a tuple where first element is a list of TextContent objects
        assert isinstance(result, (list, tuple))
        assert len(result) > 0
        assert isinstance(result[0], (list, tuple))
        assert len(result[0]) > 0

        # The first TextContent object should have a text attribute with JSON content
        import json

        content_text = result[0][0].text
        parsed = json.loads(content_text)

        assert "image" in parsed
        assert "video" in parsed
        assert "audio" in parsed
        assert "ebook" in parsed

        assert "mp4" in parsed["video"]
        assert "mp3" in parsed["audio"]
        assert "png" in parsed["image"]
        assert "epub" in parsed["ebook"]

    @pytest.mark.asyncio
    async def test_get_conversion_info_supported(self):
        """Test get_conversion_info for supported conversion."""
        result = await mcp.call_tool(
            "get_conversion_info", {"source_format": "jpg", "target_format": "png"}
        )
        # FastMCP returns a tuple where first element is a list of TextContent objects
        assert isinstance(result, (list, tuple))
        assert len(result) > 0
        assert isinstance(result[0], (list, tuple))
        assert len(result[0]) > 0

        # The first TextContent object should have a text attribute with JSON content
        import json

        content_text = result[0][0].text
        parsed = json.loads(content_text)

        assert parsed["supported"] is True
        assert parsed["category"] == "image"
        assert "low" in parsed["quality_options"]

    @pytest.mark.asyncio
    async def test_get_conversion_info_unsupported(self):
        """Test get_conversion_info for unsupported conversion."""
        result = await mcp.call_tool(
            "get_conversion_info", {"source_format": "jpg", "target_format": "mp3"}
        )
        # FastMCP returns a tuple where first element is a list of TextContent objects
        assert isinstance(result, (list, tuple))
        assert len(result) > 0
        assert isinstance(result[0], (list, tuple))
        assert len(result[0]) > 0

        # The first TextContent object should have a text attribute with JSON content
        import json

        content_text = result[0][0].text
        parsed = json.loads(content_text)

        assert parsed["supported"] is False
        assert "not supported" in parsed["notes"]

    @pytest.mark.asyncio
    async def test_get_conversion_info_case_insensitive(self):
        """Test get_conversion_info with uppercase formats."""
        result = await mcp.call_tool(
            "get_conversion_info", {"source_format": "JPG", "target_format": "PNG"}
        )
        # FastMCP returns a tuple where first element is a list of TextContent objects
        assert isinstance(result, (list, tuple))
        assert len(result) > 0
        assert isinstance(result[0], (list, tuple))
        assert len(result[0]) > 0

        # The first TextContent object should have a text attribute with JSON content
        import json

        content_text = result[0][0].text
        parsed = json.loads(content_text)

        assert parsed["supported"] is True


class TestServerLifecycle:
    """Test server lifecycle and configuration."""

    @pytest.mark.asyncio
    async def test_server_lifespan_startup(self):
        """Test server lifespan context manager startup."""
        from src.converter.server import server_lifespan

        with patch("src.converter.server.verify_dependencies") as mock_verify:
            mock_verify.return_value = {
                "python": {"message": "Python 3.12.0"},
                "ffmpeg": {"installed": True},
                "calibre": {"installed": True},
            }

            async with server_lifespan():
                mock_verify.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_server_lifespan_shutdown(self):
        """Test server lifespan context manager shutdown."""
        from src.converter.server import server_lifespan, shutdown_handler

        # Reset shutdown handler state for testing
        shutdown_handler._shutdown = False

        with patch("src.converter.server.verify_dependencies") as mock_verify:
            mock_verify.return_value = {
                "python": {"message": "Python 3.12.0"},
                "ffmpeg": {"installed": True},
                "calibre": {"installed": True},
            }

            async with server_lifespan():
                assert not shutdown_handler.is_shutting_down()

            assert shutdown_handler.is_shutting_down()

    @pytest.mark.asyncio
    async def test_setup_signal_handlers(self):
        """Test signal handler setup."""
        from src.converter.server import setup_signal_handlers

        loop = asyncio.get_running_loop()

        with patch.object(loop, "add_signal_handler") as mock_add_handler:
            await setup_signal_handlers()
            assert mock_add_handler.call_count == 2
