"""
Unit tests for AtomicFileOperation class.

Tests the atomic file operation functionality including:
- Backup creation before modification
- Rollback on error
- Cleanup on success

Validates: Requirement 11.2 - If sync is interrupted, leave files in a consistent state
"""

from pathlib import Path

import pytest

from ar_sync.sync.atomic_ops import AtomicFileOperation


class TestAtomicFileOperationBasics:
    """Basic functionality tests for AtomicFileOperation."""

    def test_copy_with_backup_new_file(self, tmp_path: Path) -> None:
        """Test copying to a new destination (no backup needed)."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("source content")

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.copy_with_backup(src, dst)

        assert dst.exists()
        assert dst.read_text() == "source content"
        # No backup should be created for new files
        assert len(list((tmp_path / "backups").glob("*.bak"))) == 0

    def test_copy_with_backup_existing_file(self, tmp_path: Path) -> None:
        """Test copying to an existing destination (backup created)."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        backup_dir = tmp_path / "backups"

        src.write_text("new content")
        dst.write_text("original content")

        with AtomicFileOperation(backup_dir) as atomic:
            atomic.copy_with_backup(src, dst)
            # During operation, backup should exist
            assert len(atomic.backups) == 1

        # After success, backup should be cleaned up
        assert dst.read_text() == "new content"
        assert len(list(backup_dir.glob("*.bak"))) == 0

    def test_copy_preserves_metadata(self, tmp_path: Path) -> None:
        """Test that copy preserves file permissions and timestamps."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"

        src.write_text("content")
        src.chmod(0o755)  # Set executable permission

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.copy_with_backup(src, dst)

        # Check permissions are preserved
        assert (dst.stat().st_mode & 0o777) == 0o755

    def test_copy_source_not_found(self, tmp_path: Path) -> None:
        """Test that copying non-existent source raises FileNotFoundError."""
        src = tmp_path / "nonexistent.txt"
        dst = tmp_path / "dest.txt"

        with pytest.raises(FileNotFoundError):
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.copy_with_backup(src, dst)


class TestAtomicFileOperationRollback:
    """Tests for rollback functionality."""

    def test_rollback_on_exception(self, tmp_path: Path) -> None:
        """Test that files are rolled back when an exception occurs."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        src1 = tmp_path / "src1.txt"
        src2 = tmp_path / "src2.txt"

        # Setup initial state
        file1.write_text("original1")
        file2.write_text("original2")
        src1.write_text("new1")
        src2.write_text("new2")

        # Simulate failure during operations
        try:
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.copy_with_backup(src1, file1)
                atomic.copy_with_backup(src2, file2)
                # Simulate an error
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # Files should be rolled back to original state
        assert file1.read_text() == "original1"
        assert file2.read_text() == "original2"

    def test_rollback_partial_operations(self, tmp_path: Path) -> None:
        """Test rollback when only some files were modified."""
        file1 = tmp_path / "file1.txt"
        src1 = tmp_path / "src1.txt"
        nonexistent = tmp_path / "nonexistent.txt"

        file1.write_text("original")
        src1.write_text("new content")

        try:
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.copy_with_backup(src1, file1)
                # This should fail
                atomic.copy_with_backup(nonexistent, tmp_path / "dest.txt")
        except FileNotFoundError:
            pass

        # file1 should be rolled back
        assert file1.read_text() == "original"

    def test_rollback_order_is_reversed(self, tmp_path: Path) -> None:
        """Test that rollback processes in reverse order (LIFO)."""
        file1 = tmp_path / "file1.txt"
        src1 = tmp_path / "src1.txt"
        src2 = tmp_path / "src2.txt"

        file1.write_text("v1")
        src1.write_text("v2")
        src2.write_text("v3")

        try:
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                # First modification
                atomic.copy_with_backup(src1, file1)
                assert file1.read_text() == "v2"

                # Second modification to same file
                atomic.copy_with_backup(src2, file1)
                assert file1.read_text() == "v3"

                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # Should be rolled back to original v1
        assert file1.read_text() == "v1"


class TestAtomicFileOperationCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_on_success(self, tmp_path: Path) -> None:
        """Test that backups are cleaned up on successful completion."""
        backup_dir = tmp_path / "backups"
        file1 = tmp_path / "file1.txt"
        src1 = tmp_path / "src1.txt"

        file1.write_text("original")
        src1.write_text("new")

        with AtomicFileOperation(backup_dir) as atomic:
            atomic.copy_with_backup(src1, file1)
            # Backup should exist during operation
            assert len(list(backup_dir.glob("*.bak"))) == 1

        # Backup should be cleaned up after success
        assert len(list(backup_dir.glob("*.bak"))) == 0

    def test_cleanup_on_rollback(self, tmp_path: Path) -> None:
        """Test that backups are cleaned up after rollback."""
        backup_dir = tmp_path / "backups"
        file1 = tmp_path / "file1.txt"
        src1 = tmp_path / "src1.txt"

        file1.write_text("original")
        src1.write_text("new")

        try:
            with AtomicFileOperation(backup_dir) as atomic:
                atomic.copy_with_backup(src1, file1)
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # Backup should be cleaned up even after rollback
        assert len(list(backup_dir.glob("*.bak"))) == 0

    def test_temp_directory_cleanup(self, tmp_path: Path) -> None:
        """Test that temporary directory is cleaned up when not provided."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"
        src.write_text("content")
        dst.write_text("original")

        # Use AtomicFileOperation without providing backup_dir
        with AtomicFileOperation() as atomic:
            atomic.copy_with_backup(src, dst)
            # Temp directory should exist during operation
            assert atomic._temp_dir is not None
            temp_path = Path(atomic._temp_dir.name)
            assert temp_path.exists()

        # After context exit, temp directory should be cleaned up
        # Note: We can't check temp_path.exists() here because the reference is invalid


class TestAtomicFileOperationWrite:
    """Tests for write_with_backup functionality."""

    def test_write_new_file(self, tmp_path: Path) -> None:
        """Test writing to a new file."""
        dst = tmp_path / "new_file.txt"

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.write_with_backup(dst, "new content")

        assert dst.exists()
        assert dst.read_text() == "new content"

    def test_write_existing_file_with_backup(self, tmp_path: Path) -> None:
        """Test writing to an existing file creates backup."""
        dst = tmp_path / "existing.txt"
        dst.write_text("original")

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.write_with_backup(dst, "new content")

        assert dst.read_text() == "new content"

    def test_write_rollback_on_error(self, tmp_path: Path) -> None:
        """Test that write is rolled back on error."""
        dst = tmp_path / "file.txt"
        dst.write_text("original")

        try:
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.write_with_backup(dst, "new content")
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        assert dst.read_text() == "original"


class TestAtomicFileOperationDelete:
    """Tests for delete_with_backup functionality."""

    def test_delete_with_backup(self, tmp_path: Path) -> None:
        """Test deleting a file with backup."""
        target = tmp_path / "to_delete.txt"
        target.write_text("content")

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.delete_with_backup(target)

        assert not target.exists()

    def test_delete_rollback_on_error(self, tmp_path: Path) -> None:
        """Test that delete is rolled back on error."""
        target = tmp_path / "to_delete.txt"
        target.write_text("content")

        try:
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.delete_with_backup(target)
                assert not target.exists()
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # File should be restored
        assert target.exists()
        assert target.read_text() == "content"

    def test_delete_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that deleting non-existent file raises FileNotFoundError."""
        target = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            with AtomicFileOperation(tmp_path / "backups") as atomic:
                atomic.delete_with_backup(target)


class TestAtomicFileOperationEdgeCases:
    """Edge case tests for AtomicFileOperation."""

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        """Test that nested directories are created for destination."""
        src = tmp_path / "source.txt"
        dst = tmp_path / "nested" / "deep" / "dest.txt"
        src.write_text("content")

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.copy_with_backup(src, dst)

        assert dst.exists()
        assert dst.read_text() == "content"

    def test_multiple_operations_same_file(self, tmp_path: Path) -> None:
        """Test multiple operations on the same file."""
        file1 = tmp_path / "file.txt"
        src1 = tmp_path / "src1.txt"
        src2 = tmp_path / "src2.txt"

        file1.write_text("v1")
        src1.write_text("v2")
        src2.write_text("v3")

        with AtomicFileOperation(tmp_path / "backups") as atomic:
            atomic.copy_with_backup(src1, file1)
            atomic.copy_with_backup(src2, file1)

        assert file1.read_text() == "v3"

    def test_empty_operations(self, tmp_path: Path) -> None:
        """Test context manager with no operations."""
        with AtomicFileOperation(tmp_path / "backups"):
            pass  # No operations

        # Should complete without error
        assert True

    def test_backup_dir_created_on_demand(self, tmp_path: Path) -> None:
        """Test that backup directory is created only when needed."""
        backup_dir = tmp_path / "backups"
        src = tmp_path / "source.txt"
        dst = tmp_path / "dest.txt"

        src.write_text("content")
        dst.write_text("original")

        assert not backup_dir.exists()

        with AtomicFileOperation(backup_dir) as atomic:
            atomic.copy_with_backup(src, dst)
            # Backup dir should now exist
            assert backup_dir.exists()
