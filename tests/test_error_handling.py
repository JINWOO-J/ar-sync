"""Unit tests for error handling module."""

import platform

from ar_sync.errors import ARSyncError, ErrorCategory, get_symlink_error_guidance


class TestARSyncError:
    """Tests for ARSyncError exception class."""

    def test_error_with_message_only(self) -> None:
        """Test ARSyncError with message only."""
        error = ARSyncError(
            "Test error message",
            ErrorCategory.USER_INPUT
        )

        assert error.message == "Test error message"
        assert error.category == ErrorCategory.USER_INPUT
        assert error.recovery_steps == []
        assert str(error) == "Test error message"

    def test_error_with_recovery_steps(self) -> None:
        """Test ARSyncError with recovery steps."""
        recovery_steps = [
            "Step 1: Do this",
            "Step 2: Do that"
        ]
        error = ARSyncError(
            "Test error",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=recovery_steps
        )

        assert error.recovery_steps == recovery_steps

    def test_format_error_without_recovery_steps(self) -> None:
        """Test format_error without recovery steps."""
        error = ARSyncError(
            "Simple error",
            ErrorCategory.CONFIG
        )

        formatted = error.format_error()
        assert formatted == "Error: Simple error"

    def test_format_error_with_recovery_steps(self) -> None:
        """Test format_error with recovery steps."""
        error = ARSyncError(
            "Complex error",
            ErrorCategory.GIT,
            recovery_steps=[
                "First step",
                "Second step",
                "Third step"
            ]
        )

        formatted = error.format_error()
        assert "Error: Complex error" in formatted
        assert "To resolve this issue:" in formatted
        assert "  1. First step" in formatted
        assert "  2. Second step" in formatted
        assert "  3. Third step" in formatted

    def test_error_categories(self) -> None:
        """Test all error categories are defined."""
        assert ErrorCategory.USER_INPUT.value == "user_input"
        assert ErrorCategory.FILE_SYSTEM.value == "file_system"
        assert ErrorCategory.GIT.value == "git"
        assert ErrorCategory.CONFIG.value == "config"


class TestSymlinkErrorGuidance:
    """Tests for platform-specific symlink error guidance."""

    def test_get_symlink_error_guidance_returns_string(self) -> None:
        """Test that get_symlink_error_guidance returns a non-empty string."""
        guidance = get_symlink_error_guidance()

        assert isinstance(guidance, str)
        assert len(guidance) > 0
        assert "Symlink" in guidance or "symlink" in guidance.lower()

    def test_guidance_contains_platform_specific_info(self) -> None:
        """Test that guidance contains platform-specific information."""
        guidance = get_symlink_error_guidance()
        system = platform.system()

        if system == "Windows":
            assert "Developer Mode" in guidance
            assert "Settings" in guidance
        elif system == "Darwin":
            assert "chmod" in guidance
            assert "permissions" in guidance.lower()
        else:  # Linux and others
            assert "chmod" in guidance
            assert "permissions" in guidance.lower()

    def test_guidance_provides_actionable_steps(self) -> None:
        """Test that guidance provides actionable steps."""
        guidance = get_symlink_error_guidance()

        # Should contain numbered steps or specific commands
        assert "chmod" in guidance or "Settings" in guidance
