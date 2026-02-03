"""Tests for SyncError exception class.

This module tests the SyncError class which extends ARSyncError
with file path information and automatic recovery step generation.
"""

import pytest

from ar_sync.errors import ARSyncError, ErrorCategory, SyncError


class TestSyncError:
    """Test suite for SyncError exception class."""

    def test_sync_error_inherits_from_arsync_error(self):
        """Test that SyncError is a subclass of ARSyncError."""
        error = SyncError("Test error", ErrorCategory.FILE_SYSTEM)
        assert isinstance(error, ARSyncError)
        assert isinstance(error, Exception)

    def test_sync_error_with_file_path(self):
        """Test SyncError stores file_path attribute correctly.

        Validates: Requirement 11.1
        """
        error = SyncError(
            "File operation failed", ErrorCategory.FILE_SYSTEM, file_path="/path/to/file.txt"
        )
        assert error.file_path == "/path/to/file.txt"
        assert error.message == "File operation failed"
        assert error.category == ErrorCategory.FILE_SYSTEM

    def test_sync_error_without_file_path(self):
        """Test SyncError works without file_path."""
        error = SyncError("General error", ErrorCategory.GIT)
        assert error.file_path is None
        assert error.message == "General error"
        assert error.category == ErrorCategory.GIT

    def test_format_error_includes_file_path(self):
        """Test format_error() includes file path when available.

        Validates: Requirement 11.1
        """
        error = SyncError(
            "Permission denied", ErrorCategory.FILE_SYSTEM, file_path=".kiro/config.yaml"
        )
        formatted = error.format_error()

        assert "Error: Permission denied" in formatted
        assert "File: .kiro/config.yaml" in formatted

    def test_format_error_without_file_path(self):
        """Test format_error() works without file path."""
        error = SyncError("Network error", ErrorCategory.GIT)
        formatted = error.format_error()

        assert "Error: Network error" in formatted
        assert "File:" not in formatted

    def test_recovery_steps_for_config_category(self):
        """Test recovery steps are generated for CONFIG category.

        Validates: Requirements 11.3, 11.4
        """
        error = SyncError("Store not initialized", ErrorCategory.CONFIG)

        assert len(error.recovery_steps) > 0
        # Requirement 11.4: prompt user to run `ars setup`
        assert any("ars setup" in step for step in error.recovery_steps)

    def test_recovery_steps_for_file_system_category(self):
        """Test recovery steps are generated for FILE_SYSTEM category.

        Validates: Requirement 11.3
        """
        error = SyncError(
            "Cannot write file", ErrorCategory.FILE_SYSTEM, file_path="/path/to/file.txt"
        )

        assert len(error.recovery_steps) > 0
        # Should include permission-related guidance
        assert any("permission" in step.lower() for step in error.recovery_steps)

    def test_recovery_steps_for_git_category(self):
        """Test recovery steps are generated for GIT category.

        Validates: Requirement 11.3
        """
        error = SyncError("Failed to push to remote", ErrorCategory.GIT)

        assert len(error.recovery_steps) > 0
        # Should include network or git-related guidance
        assert any(
            "network" in step.lower() or "git" in step.lower() for step in error.recovery_steps
        )

    def test_recovery_steps_for_user_input_category(self):
        """Test recovery steps are generated for USER_INPUT category.

        Validates: Requirement 11.3
        """
        error = SyncError("Invalid project name", ErrorCategory.USER_INPUT)

        assert len(error.recovery_steps) > 0
        # Should include help or syntax guidance
        assert any(
            "help" in step.lower() or "syntax" in step.lower() for step in error.recovery_steps
        )

    def test_format_error_includes_recovery_steps(self):
        """Test format_error() includes recovery steps.

        Validates: Requirement 11.3
        """
        error = SyncError("Store not initialized", ErrorCategory.CONFIG)
        formatted = error.format_error()

        assert "To resolve this issue:" in formatted
        assert "1." in formatted  # Numbered steps

    def test_sync_error_exception_message(self):
        """Test that SyncError can be raised and caught with correct message."""
        with pytest.raises(SyncError) as exc_info:
            raise SyncError("Test exception", ErrorCategory.FILE_SYSTEM, file_path="/test/path")

        assert str(exc_info.value) == "Test exception"
        assert exc_info.value.file_path == "/test/path"

    def test_sync_error_all_categories_have_recovery_steps(self):
        """Test that all error categories generate recovery steps."""
        for category in ErrorCategory:
            error = SyncError(f"Error for {category.value}", category)
            assert len(error.recovery_steps) > 0, f"Category {category} should have recovery steps"

    def test_format_error_complete_output(self):
        """Test complete format_error() output structure."""
        error = SyncError(
            "Failed to sync file", ErrorCategory.FILE_SYSTEM, file_path=".cursor/settings.json"
        )
        formatted = error.format_error()

        lines = formatted.split("\n")

        # First line should be error message
        assert lines[0] == "Error: Failed to sync file"
        # Second line should be file path
        assert lines[1] == "  File: .cursor/settings.json"
        # Should have recovery section
        assert any("To resolve this issue:" in line for line in lines)
