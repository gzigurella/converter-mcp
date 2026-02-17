"""Unit tests for file manager module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.converter.file_manager import (
    FileOperationError,
    FileManager,
)


class TestFileManager:
    """Test cases for FileManager class."""

    def test_init_default(self):
        """Test FileManager initialization with default values."""
        manager = FileManager()

        assert manager.output_dir is None
        assert manager.min_disk_space_mb == 100

    def test_init_with_output_dir(self):
        """Test FileManager initialization with custom output directory."""
        manager = FileManager(output_dir="/tmp/output")

        assert manager.output_dir == Path("/tmp/output")

    def test_init_with_custom_min_disk_space(self):
        """Test FileManager initialization with custom min disk space."""
        manager = FileManager(min_disk_space_mb=500)

        assert manager.min_disk_space_mb == 500


class TestResolveOutputPath:
    """Test cases for output path resolution with collision handling."""

    def test_resolve_no_collision_default_output_dir(self, tmp_path):
        """Test path resolution without collision in source parent directory."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        manager = FileManager()
        output_path = manager.resolve_output_path(source, "pdf")

        assert output_path.parent == tmp_path
        assert output_path.name == "source.pdf"
        assert not output_path.exists()

    def test_resolve_with_custom_output_dir(self, tmp_path):
        """Test path resolution with custom output directory."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        output_dir = tmp_path / "output"
        manager = FileManager(output_dir=str(output_dir))
        output_path = manager.resolve_output_path(source, "pdf")

        assert output_path.parent == output_dir
        assert output_path.name == "source.pdf"

    def test_resolve_with_collision_renames(self, tmp_path):
        """Test that colliding files get auto-renamed with counter."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        # Create a file that would collide
        (tmp_path / "source.pdf").write_text("existing")

        manager = FileManager()
        output_path = manager.resolve_output_path(source, "pdf")

        assert output_path.parent == tmp_path
        assert output_path.name == "source_1.pdf"

    def test_resolve_multiple_collisions(self, tmp_path):
        """Test that multiple collisions increment counter correctly."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        # Create multiple colliding files
        (tmp_path / "source.pdf").write_text("existing")
        (tmp_path / "source_1.pdf").write_text("existing")
        (tmp_path / "source_2.pdf").write_text("existing")

        manager = FileManager()
        output_path = manager.resolve_output_path(source, "pdf")

        assert output_path.name == "source_3.pdf"

    def test_resolve_target_format_case_insensitive(self, tmp_path):
        """Test that target format is converted to lowercase."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        manager = FileManager()

        output_path_upper = manager.resolve_output_path(source, "PDF")
        output_path_mixed = manager.resolve_output_path(source, "Pdf")

        assert output_path_upper.name == "source.pdf"
        assert output_path_mixed.name == "source.pdf"

    def test_resolve_source_not_exists_raises_error(self, tmp_path):
        """Test that non-existent source raises FileOperationError."""
        source = tmp_path / "nonexistent.txt"

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.resolve_output_path(source, "pdf")

        assert "does not exist" in str(exc_info.value).lower()

    def test_resolve_source_is_directory_raises_error(self, tmp_path):
        """Test that directory as source raises FileOperationError."""
        source = tmp_path / "directory"
        source.mkdir()

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.resolve_output_path(source, "pdf")

        assert "not a file" in str(exc_info.value).lower()

    def test_resolve_invalid_target_format_raises_error(self, tmp_path):
        """Test that invalid target format raises FileOperationError."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.resolve_output_path(source, "")

        assert "format" in str(exc_info.value).lower()

    def test_resolve_whitespace_format_raises_error(self, tmp_path):
        """Test that whitespace-only format raises FileOperationError."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.resolve_output_path(source, "   ")

        assert "format" in str(exc_info.value).lower()

    def test_resolve_too_many_collisions_raises_error(self, tmp_path):
        """Test that too many collisions raises FileOperationError."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        (tmp_path / "source.pdf").write_text("existing")
        for i in range(1, 1001):
            (tmp_path / f"source_{i}.pdf").write_text("existing")

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.resolve_output_path(source, "pdf")

        assert "too many" in str(exc_info.value).lower()


class TestCheckDiskSpace:
    """Test cases for disk space verification."""

    def test_check_disk_space_sufficient(self, tmp_path):
        """Test that sufficient disk space passes check."""
        manager = FileManager(min_disk_space_mb=1)

        assert manager.check_disk_space(tmp_path) is True

    def test_check_disk_space_custom_required(self, tmp_path):
        """Test that custom required space is used."""
        manager = FileManager(min_disk_space_mb=1000)

        assert manager.check_disk_space(tmp_path, required_mb=1) is True

    def test_check_disk_space_insufficient_raises_error(self, tmp_path):
        """Test that insufficient disk space raises FileOperationError."""
        manager = FileManager(min_disk_space_mb=999999999)

        with pytest.raises(FileOperationError) as exc_info:
            manager.check_disk_space(tmp_path)

        assert "insufficient" in str(exc_info.value).lower()
        assert "disk space" in str(exc_info.value).lower()

    def test_check_disk_space_file_path_uses_parent(self, tmp_path):
        """Test that file path uses parent directory for space check."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        manager = FileManager(min_disk_space_mb=1)

        assert manager.check_disk_space(test_file) is True

    def test_check_disk_space_invalid_path_raises_error(self):
        """Test that invalid path raises FileOperationError."""
        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.check_disk_space("/nonexistent/path/12345")

        assert "invalid path" in str(exc_info.value).lower()


class TestAtomicMove:
    """Test cases for atomic file move operations."""

    def test_atomic_move_success(self, tmp_path):
        """Test successful atomic file move."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        dest = tmp_path / "dest.txt"

        manager = FileManager()
        result = manager.atomic_move(source, dest)

        assert result == dest
        assert dest.exists()
        assert not source.exists()
        assert dest.read_text() == "content"

    def test_atomic_move_creates_parent_dirs(self, tmp_path):
        """Test that atomic move creates parent directories."""
        source = tmp_path / "source.txt"
        source.write_text("content")

        dest = tmp_path / "subdir" / "nested" / "dest.txt"

        manager = FileManager()
        result = manager.atomic_move(source, dest)

        assert result == dest
        assert dest.exists()
        assert dest.parent.exists()
        assert dest.read_text() == "content"

    def test_atomic_move_overwrites_existing(self, tmp_path):
        """Test that atomic move overwrites existing file."""
        source = tmp_path / "source.txt"
        source.write_text("new content")

        dest = tmp_path / "dest.txt"
        dest.write_text("old content")

        manager = FileManager()
        result = manager.atomic_move(source, dest)

        assert result == dest
        assert dest.read_text() == "new content"

    def test_atomic_move_source_not_exists_raises_error(self, tmp_path):
        """Test that non-existent source raises FileOperationError."""
        source = tmp_path / "nonexistent.txt"
        dest = tmp_path / "dest.txt"

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.atomic_move(source, dest)

        assert "does not exist" in str(exc_info.value).lower()

    def test_atomic_move_source_is_directory_raises_error(self, tmp_path):
        """Test that directory as source raises FileOperationError."""
        source = tmp_path / "directory"
        source.mkdir()

        dest = tmp_path / "dest.txt"

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.atomic_move(source, dest)

        assert "not a file" in str(exc_info.value).lower()


class TestValidatePath:
    """Test cases for path validation."""

    def test_validate_path_exists(self, tmp_path):
        """Test validation of existing path."""
        test_path = tmp_path / "test.txt"
        test_path.write_text("content")

        manager = FileManager()
        result = manager.validate_path(test_path)

        assert result == test_path

    def test_validate_path_not_exists_with_must_exist(self, tmp_path):
        """Test that non-existent path raises error when must_exist=True."""
        test_path = tmp_path / "nonexistent.txt"

        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.validate_path(test_path, must_exist=True)

        assert "does not exist" in str(exc_info.value).lower()

    def test_validate_path_not_exists_without_must_exist(self, tmp_path):
        """Test that non-existent path is valid when must_exist=False."""
        test_path = tmp_path / "nonexistent.txt"

        manager = FileManager()
        result = manager.validate_path(test_path, must_exist=False)

        assert result == test_path

    def test_validate_path_string_input(self, tmp_path):
        """Test validation of string path input."""
        test_path = tmp_path / "test.txt"
        test_path.write_text("content")

        manager = FileManager()
        result = manager.validate_path(str(test_path))

        assert isinstance(result, Path)
        assert result == test_path

    def test_validate_path_normalizes_traversal(self, tmp_path):
        """Test that path traversal is normalized."""
        manager = FileManager()

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        traversal_path = str(tmp_path / ".." / tmp_path.name / "test.txt")

        result = manager.validate_path(traversal_path, must_exist=True)

        assert result == test_file


class TestGetOutputDir:
    """Test cases for getting output directory."""

    def test_get_output_dir_configured(self, tmp_path):
        """Test getting configured output directory."""
        manager = FileManager(output_dir=str(tmp_path))

        result = manager.get_output_dir()

        assert result == tmp_path

    def test_get_output_dir_not_configured_raises_error(self):
        """Test that unconfigured output directory raises error."""
        manager = FileManager()

        with pytest.raises(FileOperationError) as exc_info:
            manager.get_output_dir()

        assert "not configured" in str(exc_info.value).lower()


class TestFileOperationError:
    """Test cases for FileOperationError exception."""

    def test_error_message(self):
        """Test that FileOperationError can carry meaningful messages."""
        error = FileOperationError("File operation failed")
        assert str(error) == "File operation failed"

    def test_error_inheritance(self):
        """Test that FileOperationError inherits from RuntimeError."""
        error = FileOperationError("Test error")
        assert isinstance(error, RuntimeError)
