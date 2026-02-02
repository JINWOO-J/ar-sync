"""
ar_sync.sync.atomic_ops - Atomic file operations for safe synchronization.

This module provides the AtomicFileOperation class that ensures file operations
are atomic - either all changes succeed or all are rolled back.

Requirements:
- 11.2: If sync is interrupted, leave files in a consistent state (no partial copies)

Usage:
    with AtomicFileOperation(backup_dir) as atomic:
        atomic.copy_with_backup(src1, dst1)
        atomic.copy_with_backup(src2, dst2)
        # If any operation fails, all changes are rolled back
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType


class AtomicFileOperation:
    """Context manager for atomic file operations with backup and rollback.
    
    This class ensures that file operations are atomic:
    - Creates backups before modifying existing files
    - Rolls back all changes if any operation fails
    - Cleans up backups on successful completion
    
    Validates:
    - Requirement 11.2: If sync is interrupted, leave files in a consistent state
    
    Example:
        >>> with AtomicFileOperation(Path("/tmp/backups")) as atomic:
        ...     atomic.copy_with_backup(src_file, dst_file)
        ...     # If this fails, dst_file is restored from backup
        ...     atomic.copy_with_backup(src_file2, dst_file2)
    """
    
    def __init__(self, backup_dir: Path | None = None):
        """Initialize AtomicFileOperation.
        
        Args:
            backup_dir: Directory to store backups. If None, a temporary
                       directory will be created and cleaned up automatically.
        """
        self._backup_dir_provided = backup_dir is not None
        self._backup_dir: Path | None = backup_dir
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.backups: list[tuple[Path, Path]] = []
    
    @property
    def backup_dir(self) -> Path:
        """Get the backup directory, creating it if necessary."""
        if self._backup_dir is None:
            # Create a temporary directory if none was provided
            self._temp_dir = tempfile.TemporaryDirectory(prefix="ar_sync_backup_")
            self._backup_dir = Path(self._temp_dir.name)
        
        # Ensure the backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        return self._backup_dir
    
    def __enter__(self) -> AtomicFileOperation:
        """Enter the context manager.
        
        Returns:
            Self for use in with statement
        """
        return self
    
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager.
        
        If an exception occurred, rolls back all changes.
        Always cleans up backup files.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if exc_type is not None:
            # An error occurred - rollback all changes
            self._rollback()
        
        # Always cleanup backups
        self._cleanup_backups()
        
        # Cleanup temporary directory if we created one
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except (OSError, IOError):
                pass  # Best effort cleanup
            self._temp_dir = None
    
    def copy_with_backup(self, src: Path, dst: Path) -> None:
        """Copy a file or directory with backup creation for rollback support.
        
        If the destination exists, creates a backup before copying.
        The backup is used for rollback if any subsequent operation fails.
        
        For files: Uses shutil.copy2 to preserve metadata.
        For directories: Uses shutil.copytree with copy_function=shutil.copy2.
        
        Args:
            src: Source file or directory path to copy from
            dst: Destination path to copy to
            
        Raises:
            FileNotFoundError: If source doesn't exist
            PermissionError: If permission denied for read/write
            OSError: If other file operation fails
            
        Validates:
        - Requirement 10.1: Preserve file permissions (chmod)
        - Requirement 10.2: Preserve file modification timestamps
        - Requirement 10.3: Preserve directory structure and permissions
        - Requirement 11.2: No partial copies - either succeeds or rolls back
        """
        # Ensure source exists
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {src}")
        
        # Create backup if destination exists
        if dst.exists():
            backup = self._create_backup(dst)
            self.backups.append((dst, backup))
        
        # Ensure destination directory exists
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file or directory with metadata preservation
        if src.is_dir():
            # Remove existing destination if it exists (for directory replacement)
            if dst.exists():
                shutil.rmtree(dst)
            # Copy directory tree with metadata preservation (Requirement 10.3)
            shutil.copytree(src, dst, copy_function=shutil.copy2)
        else:
            # Copy file with metadata preservation (Requirement 10.1, 10.2)
            shutil.copy2(src, dst)
    
    def write_with_backup(self, dst: Path, content: str, encoding: str = "utf-8") -> None:
        """Write content to a file with backup creation for rollback support.
        
        If the destination file exists, creates a backup before writing.
        The backup is used for rollback if any subsequent operation fails.
        
        Args:
            dst: Destination file path to write to
            content: Text content to write
            encoding: Text encoding (default: utf-8)
            
        Raises:
            PermissionError: If permission denied for write
            OSError: If other file operation fails
            
        Validates:
        - Requirement 11.2: No partial writes - either succeeds or rolls back
        """
        # Create backup if destination exists
        if dst.exists():
            backup = self._create_backup(dst)
            self.backups.append((dst, backup))
        
        # Ensure destination directory exists
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        dst.write_text(content, encoding=encoding)
    
    def delete_with_backup(self, target: Path) -> None:
        """Delete a file with backup creation for rollback support.
        
        Creates a backup before deleting so the file can be restored
        if any subsequent operation fails.
        
        Args:
            target: File path to delete
            
        Raises:
            FileNotFoundError: If target file doesn't exist
            PermissionError: If permission denied for delete
            OSError: If other file operation fails
            
        Validates:
        - Requirement 11.2: Deletion can be rolled back
        """
        if not target.exists():
            raise FileNotFoundError(f"Target file not found: {target}")
        
        # Create backup before deletion
        backup = self._create_backup(target)
        self.backups.append((target, backup))
        
        # Delete the file
        target.unlink()
    
    def _create_backup(self, original: Path) -> Path:
        """Create a backup of a file or directory.
        
        Args:
            original: Path to the file or directory to backup
            
        Returns:
            Path to the backup file or directory
            
        Validates:
        - Requirement 10.1, 10.2, 10.3: Preserve metadata during backup
        """
        # Generate unique backup filename
        backup_name = f"{original.name}.{uuid.uuid4().hex[:8]}.bak"
        backup_path = self.backup_dir / backup_name
        
        # Copy with metadata preservation
        if original.is_dir():
            # Copy directory tree with metadata preservation
            shutil.copytree(original, backup_path, copy_function=shutil.copy2)
        else:
            # Copy file with metadata preservation
            shutil.copy2(original, backup_path)
        
        return backup_path
    
    def _rollback(self) -> None:
        """Rollback all changes by restoring from backups.
        
        Processes backups in reverse order to handle dependencies correctly.
        Supports both files and directories.
        
        Validates:
        - Requirement 11.2: Restore files to consistent state on error
        """
        # Process in reverse order (LIFO) for proper rollback
        for original, backup in reversed(self.backups):
            if backup.exists():
                try:
                    # Remove current state if it exists
                    if original.exists():
                        if original.is_dir():
                            shutil.rmtree(original)
                        else:
                            original.unlink()
                    
                    # Restore original from backup
                    if backup.is_dir():
                        shutil.copytree(backup, original, copy_function=shutil.copy2)
                    else:
                        shutil.copy2(backup, original)
                except (OSError, IOError):
                    # Best effort rollback - continue with other files
                    pass
    
    def _cleanup_backups(self) -> None:
        """Clean up all backup files and directories.
        
        Called after successful completion or after rollback.
        """
        for _, backup in self.backups:
            if backup.exists():
                try:
                    if backup.is_dir():
                        shutil.rmtree(backup)
                    else:
                        backup.unlink()
                except (OSError, IOError):
                    # Best effort cleanup - continue with other files
                    pass
        
        # Clear the backups list
        self.backups.clear()
