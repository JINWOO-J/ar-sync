"""Error handling for ar-sync.

This module provides error classes and platform-specific error guidance
for the ar-sync CLI tool.
"""

import platform
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors that can occur in ar-sync."""

    USER_INPUT = "user_input"
    FILE_SYSTEM = "file_system"
    GIT = "git"
    CONFIG = "config"


class ARSyncError(Exception):
    """Base exception class for ar-sync errors.

    This exception includes structured error information with recovery guidance.

    Attributes:
        message: Human-readable error description
        category: Error category for classification
        recovery_steps: Optional list of steps to resolve the issue
    """

    def __init__(
        self, message: str, category: ErrorCategory, recovery_steps: list[str] | None = None
    ) -> None:
        """Initialize ARSyncError.

        Args:
            message: Error description
            category: Error category
            recovery_steps: Optional recovery guidance steps
        """
        self.message = message
        self.category = category
        self.recovery_steps = recovery_steps or []
        super().__init__(self.message)

    def format_error(self) -> str:
        """Format error message with recovery steps.

        Returns:
            Formatted error message string with recovery guidance
        """
        output = [f"Error: {self.message}"]

        if self.recovery_steps:
            output.append("\nTo resolve this issue:")
            for i, step in enumerate(self.recovery_steps, 1):
                output.append(f"  {i}. {step}")

        return "\n".join(output)


class SyncError(ARSyncError):
    """Exception class for sync-specific errors.

    Extends ARSyncError with file path information and automatic
    recovery step generation based on error category.

    Attributes:
        message: Human-readable error description
        category: Error category for classification
        file_path: Optional path to the file that caused the error
        recovery_steps: List of steps to resolve the issue
    """

    def __init__(self, message: str, category: ErrorCategory, file_path: str | None = None) -> None:
        """Initialize SyncError.

        Args:
            message: Error description
            category: Error category
            file_path: Optional path to the file that caused the error
        """
        self.file_path = file_path
        recovery_steps = self._get_recovery_steps(category)
        super().__init__(message, category, recovery_steps)

    def _get_recovery_steps(self, category: ErrorCategory) -> list[str]:
        """Generate recovery steps based on error category.

        Args:
            category: The error category

        Returns:
            List of recovery step strings

        Validates: Requirements 11.3, 11.4
        """
        steps: dict[ErrorCategory, list[str]] = {
            ErrorCategory.CONFIG: [
                "Run `ars setup` to initialize the store",
                "Check that your configuration file exists at ~/.config/ar-sync/config.yaml",
                "Verify the store path in your configuration is correct",
            ],
            ErrorCategory.FILE_SYSTEM: [
                "Check file permissions with `ls -la`",
                "Ensure you have write access to the target directory",
                "Verify the file is not locked by another process",
            ],
            ErrorCategory.GIT: [
                "Check your network connection",
                "Verify your Git credentials are configured correctly",
                "Run `git status` in the store directory to check for conflicts",
                "Try running `git pull` manually in the store directory",
            ],
            ErrorCategory.USER_INPUT: [
                "Check the command syntax with `ars --help`",
                "Verify the project name or path is correct",
            ],
        }
        return steps.get(category, [])

    def format_error(self) -> str:
        """Format error message with file path and recovery steps.

        Returns:
            Formatted error message string with file path and recovery guidance

        Validates: Requirements 11.1
        """
        output = []

        # Include file path if available (Requirement 11.1)
        if self.file_path:
            output.append(f"Error: {self.message}")
            output.append(f"  File: {self.file_path}")
        else:
            output.append(f"Error: {self.message}")

        if self.recovery_steps:
            output.append("\nTo resolve this issue:")
            for i, step in enumerate(self.recovery_steps, 1):
                output.append(f"  {i}. {step}")

        return "\n".join(output)


def get_symlink_error_guidance() -> str:
    """Get platform-specific symlink error guidance.

    Provides detailed instructions for resolving symlink creation issues
    based on the current operating system.

    Returns:
        Platform-specific error guidance string
    """
    system = platform.system()

    if system == "Windows":
        return (
            "Symlink creation requires Developer Mode on Windows.\n"
            "To enable Developer Mode:\n"
            "  1. Open Settings > Update & Security > For developers\n"
            "  2. Enable 'Developer Mode'\n"
            "  3. Restart your terminal\n"
            "Alternatively, run this command as Administrator."
        )
    elif system == "Darwin":  # macOS
        return "Symlink creation failed. Check file permissions:\n  chmod +w ."
    else:  # Linux and other Unix-like systems
        return "Symlink creation failed. Check file permissions:\n  chmod +w ."
