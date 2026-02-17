"""File management module with collision handling and disk space checks.

This module provides the FileManager class for handling file operations including
path validation, collision handling with auto-rename, disk space verification,
and atomic file operations.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileOperationError(RuntimeError):
    """Raised when a file operation fails."""

    pass


class FileManager:
    """Handles file operations with collision handling and disk space checks."""

    def __init__(self, output_dir: Optional[str] = None, min_disk_space_mb: int = 100):
        """Initialize FileManager.

        Args:
            output_dir: Optional output directory. If None, uses source file's parent directory.
            min_disk_space_mb: Minimum disk space required in MB (default: 100).
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.min_disk_space_mb = min_disk_space_mb

    def resolve_output_path(self, source_path: str | Path, target_format: str) -> Path:
        """Resolve output path with collision handling.

        Args:
            source_path: Path to the source file.
            target_format: Target file format (e.g., 'pdf', 'epub').

        Returns:
            Resolved output Path with collision handling applied.

        Raises:
            FileOperationError: If path validation fails or too many collisions.
        """
        source = Path(source_path)

        if not source.exists():
            raise FileOperationError(f"Source file does not exist: {source}")

        if not source.is_file():
            raise FileOperationError(f"Source path is not a file: {source}")

        if self.output_dir:
            out_dir = self.output_dir
        else:
            out_dir = source.parent

        if not target_format or not isinstance(target_format, str):
            raise FileOperationError("Target format must be a non-empty string")

        target_format = target_format.lower().strip()
        if not target_format:
            raise FileOperationError("Target format cannot be empty or whitespace")

        output_name = f"{source.stem}.{target_format}"
        output_path = out_dir / output_name

        if output_path.exists():
            counter = 1
            while True:
                output_name = f"{source.stem}_{counter}.{target_format}"
                output_path = out_dir / output_name
                if not output_path.exists():
                    logger.debug(f"Collision detected, using renamed path: {output_path}")
                    break
                counter += 1
                if counter > 1000:
                    raise FileOperationError(
                        f"Too many file collisions for {source}. Cannot find available output path."
                    )

        logger.info(f"Resolved output path: {output_path}")
        return output_path

    def check_disk_space(self, path: str | Path, required_mb: int | None = None) -> bool:
        """Check if there's enough disk space.

        Args:
            path: Path to check (file or directory).
            required_mb: Required disk space in MB. If None, uses min_disk_space_mb.

        Returns:
            True if enough disk space is available.

        Raises:
            FileOperationError: If insufficient disk space or path validation fails.
        """
        check_path = Path(path)

        if check_path.is_file():
            check_path = check_path.parent
        elif not check_path.is_dir():
            raise FileOperationError(f"Invalid path for disk space check: {path}")

        required = required_mb or self.min_disk_space_mb

        try:
            usage = shutil.disk_usage(check_path)
            free_mb = usage.free / (1024 * 1024)
        except OSError as e:
            raise FileOperationError(f"Failed to check disk space for {check_path}: {e}") from e

        if free_mb < required:
            raise FileOperationError(
                f"Insufficient disk space: {free_mb:.1f}MB free, {required}MB required"
            )

        logger.debug(f"Disk space check passed: {free_mb:.1f}MB free at {check_path}")
        return True

    def atomic_move(self, source: Path, dest: Path) -> Path:
        """Move file atomically using temporary location.

        Args:
            source: Source file path.
            dest: Destination file path.

        Returns:
            The destination Path after successful move.

        Raises:
            FileOperationError: If the move operation fails.
        """
        if not source.exists():
            raise FileOperationError(f"Source file does not exist: {source}")

        if not source.is_file():
            raise FileOperationError(f"Source path is not a file: {source}")

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            os.replace(str(source), str(dest))
            logger.info(f"Atomically moved {source} -> {dest}")
        except OSError as e:
            raise FileOperationError(f"Failed to move file from {source} to {dest}: {e}") from e

        return dest

    def validate_path(self, path: str | Path, must_exist: bool = True) -> Path:
        """Validate a file path.

        Args:
            path: Path to validate.
            must_exist: If True, path must exist. If False, path is validated but may not exist.

        Returns:
            Validated Path object.

        Raises:
            FileOperationError: If path validation fails.
        """
        path = Path(path)

        try:
            path = path.resolve()
        except OSError as e:
            raise FileOperationError(f"Invalid path: {path}: {e}") from e

        if must_exist and not path.exists():
            raise FileOperationError(f"Path does not exist: {path}")

        return path

    def get_output_dir(self) -> Path:
        """Get the configured output directory.

        Returns:
            Path to the output directory.

        Raises:
            FileOperationError: If no output directory is configured.
        """
        if self.output_dir is None:
            raise FileOperationError("Output directory not configured")
        return self.output_dir
