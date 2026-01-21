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
        self,
        message: str,
        category: ErrorCategory,
        recovery_steps: list[str] | None = None
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
        return (
            "Symlink creation failed. Check file permissions:\n"
            "  chmod +w ."
        )
    else:  # Linux and other Unix-like systems
        return (
            "Symlink creation failed. Check file permissions:\n"
            "  chmod +w ."
        )
