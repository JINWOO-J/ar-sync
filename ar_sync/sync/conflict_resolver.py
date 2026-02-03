"""
ar_sync.sync.conflict_resolver - Conflict resolution handler.

This module provides the ConflictResolver class for handling conflicts
between Project and Store files, supporting both interactive and automatic
resolution strategies.

Requirements:
- 4.1: When a file differs between Project_Directory and Store, mark it as a conflict
- 4.2: Display format `[Conflict] <file_path>`
- 4.3: List all conflicts before prompting for resolution
- 4.4: Display both local and remote versions in the diff output
- 5.1: Prompt for each conflict with options: [l]ocal / [r]emote / [s]kip
- 5.2: When user selects `l` (local), copy Project_Directory version to Store
- 5.3: When user selects `r` (remote), copy Store version to Project_Directory
- 5.5: When user selects `s` (skip), leave both versions unchanged
- 6.1: --local option automatically prefers Project_Directory files
- 6.2: --remote option automatically prefers Store files
- 6.4: Display which files were resolved and how
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from ar_sync.sync.models import (
    ChangeType,
    FileChange,
    Resolution,
    ResolutionStrategy,
    ResolvedChange,
)


class ConflictResolver:
    """Handler for resolving conflicts between Project and Store files.

    This class provides:
    - Interactive conflict resolution with user prompts
    - Automatic resolution using --local or --remote strategies
    - Rich-formatted conflict display with diff output

    Validates:
    - Requirement 4.1, 4.2, 4.3, 4.4: Conflict detection and display
    - Requirement 5.1, 5.2, 5.3, 5.5: Interactive resolution options
    - Requirement 6.1, 6.2, 6.4: Automatic resolution strategies
    """

    def __init__(self, console: Console | None = None):
        """Initialize the ConflictResolver.

        Args:
            console: Rich Console instance for output. If None, creates a new one.
        """
        self.console = console or Console()

    def resolve_interactive(
        self,
        change: FileChange,
    ) -> ResolvedChange:
        """Resolve a conflict interactively by prompting the user.

        Displays the conflict information and diff, then prompts the user
        to choose a resolution strategy.

        Args:
            change: The FileChange representing the conflict

        Returns:
            ResolvedChange with the user's chosen resolution

        Validates:
        - Requirement 4.4: Display both local and remote versions in diff output
        - Requirement 5.1: Prompt with [l]ocal / [r]emote / [s]kip options
        - Requirement 5.2: Local selection copies Project to Store
        - Requirement 5.3: Remote selection copies Store to Project
        - Requirement 5.5: Skip leaves both versions unchanged
        """
        # Display the conflict information
        self.display_conflict(change)

        # Prompt for resolution
        resolution = self.prompt_resolution(change)

        # Display resolution result (Requirement 6.4)
        self._display_resolution_result(change, resolution)

        return ResolvedChange(
            file_change=change,
            resolution=resolution,
        )

    def resolve_automatic(
        self,
        change: FileChange,
        strategy: ResolutionStrategy,
    ) -> ResolvedChange:
        """Resolve a conflict automatically using the specified strategy.

        Args:
            change: The FileChange representing the conflict
            strategy: The resolution strategy (LOCAL or REMOTE)

        Returns:
            ResolvedChange with the automatic resolution

        Raises:
            ValueError: If strategy is INTERACTIVE (use resolve_interactive instead)

        Validates:
        - Requirement 6.1: --local option prefers Project_Directory files
        - Requirement 6.2: --remote option prefers Store files
        - Requirement 6.4: Display which files were resolved and how
        """
        if strategy == ResolutionStrategy.INTERACTIVE:
            raise ValueError(
                "Cannot use INTERACTIVE strategy with resolve_automatic. "
                "Use resolve_interactive() instead."
            )

        # Determine resolution based on strategy
        if strategy == ResolutionStrategy.LOCAL:
            resolution = Resolution.USE_LOCAL
        elif strategy == ResolutionStrategy.REMOTE:
            resolution = Resolution.USE_REMOTE
        else:
            # Should not happen, but handle gracefully
            resolution = Resolution.SKIP

        # Display resolution result (Requirement 6.4)
        self._display_resolution_result(change, resolution)

        return ResolvedChange(
            file_change=change,
            resolution=resolution,
        )

    def display_conflict(self, change: FileChange) -> None:
        """Display conflict information with Rich formatting.

        Shows:
        - Conflict header with file path (Requirement 4.2)
        - Change type information
        - Diff output showing both versions (Requirement 4.4)
        - File preview for "only in" cases

        Args:
            change: The FileChange to display

        Validates:
        - Requirement 4.2: Display format `[Conflict] <file_path>`
        - Requirement 4.4: Display both local and remote versions in diff output
        """
        # Create conflict header (Requirement 4.2)
        header = Text()
        header.append("[Conflict] ", style="bold red")
        header.append(change.path, style="bold white")

        self.console.print()
        self.console.print(Panel(header, border_style="red"))

        # Display change type information
        self._display_change_type(change)

        # Display file locations
        self._display_file_locations(change)

        # Display diff output if available (Requirement 4.4)
        if change.diff_output:
            self._display_diff(change.diff_output)
        else:
            # For "only in" cases, show file preview
            self._display_file_preview(change)

        # Display binary file warning if applicable
        if change.is_binary:
            self.console.print(
                "[yellow]⚠ This is a binary file. Only local/remote/skip options available.[/yellow]"
            )

    def prompt_resolution(self, change: FileChange) -> Resolution:
        """Prompt the user to choose a resolution method.

        Displays context-aware options based on conflict type:

        For "only in store" conflicts:
        - [k]eep in store: Copy file to local (default)
        - [d]elete from store: Remove file from store
        - [s]kip: Leave unchanged

        For "only in local" conflicts:
        - [k]eep in local: Copy file to store (default)
        - [d]elete from local: Remove file from local
        - [s]kip: Leave unchanged

        For "modified in both" conflicts:
        - [l]ocal: Use local version
        - [r]emote: Use store version
        - [s]kip: Leave unchanged
        - [Enter]: No default (explicit choice required)

        Args:
            change: The FileChange being resolved

        Returns:
            The user's chosen Resolution

        Validates:
        - Requirement 5.1: Prompt with context-aware options
        """
        # Determine smart default based on change type
        default_choice = None
        default_description = None

        if (
            "only in store" in str(change.change_type).lower()
            or "added_remote" in str(change.change_type).lower()
        ):
            # File exists only in store -> default is to keep (copy to local)
            default_choice = "k"
            default_description = "keep in store (copy to local)"
        elif (
            "only in local" in str(change.change_type).lower()
            or "added_local" in str(change.change_type).lower()
        ):
            # File exists only in local -> default is to keep (copy to store)
            default_choice = "k"
            default_description = "keep in local (copy to store)"

        # Build options text with context-aware descriptions
        options = Text()

        # Determine what each option means based on change type
        if (
            "only in store" in str(change.change_type).lower()
            or "added_remote" in str(change.change_type).lower()
        ):
            # File exists only in store
            options.append("[k]", style="bold cyan")
            options.append("eep in store (copy to local) / ", style="dim")
            options.append("[d]", style="bold cyan")
            options.append("elete from store / ", style="dim")
        elif (
            "only in local" in str(change.change_type).lower()
            or "added_local" in str(change.change_type).lower()
        ):
            # File exists only in local
            options.append("[k]", style="bold cyan")
            options.append("eep in local (copy to store) / ", style="dim")
            options.append("[d]", style="bold cyan")
            options.append("elete from local / ", style="dim")
        else:
            # File exists in both (modified)
            options.append("[l]", style="bold cyan")
            options.append("ocal / ", style="dim")
            options.append("[r]", style="bold cyan")
            options.append("emote / ", style="dim")

        options.append("[s]", style="bold cyan")
        options.append("kip", style="dim")

        self.console.print()
        self.console.print("Choose resolution: ", end="")
        self.console.print(options)

        # Show default hint if available
        if default_choice and default_description:
            self.console.print(f"[dim](Press Enter for default: {default_description})[/dim]")

        # Valid choices - context-dependent
        if (
            "only in store" in str(change.change_type).lower()
            or "added_remote" in str(change.change_type).lower()
        ):
            valid_choices = {"k", "d", "s"}  # keep, delete, skip
        elif (
            "only in local" in str(change.change_type).lower()
            or "added_local" in str(change.change_type).lower()
        ):
            valid_choices = {"k", "d", "s"}  # keep, delete, skip
        else:
            # Modified in both
            valid_choices = {"l", "r", "s"}  # local, remote, skip

        while True:
            try:
                choice = self.console.input("[bold]> [/bold]").strip().lower()

                # Handle empty input (Enter key) - use smart default
                if not choice:
                    if default_choice:
                        self.console.print(f"[dim]Using default: {default_description}[/dim]")
                        choice = default_choice
                    else:
                        continue

                # Take first character
                choice = choice[0]

                if choice not in valid_choices:
                    self.console.print(
                        f"[red]Invalid choice '{choice}'. Please choose from available options.[/red]"
                    )
                    continue

                # Map choice to Resolution based on context
                if (
                    "only in store" in str(change.change_type).lower()
                    or "added_remote" in str(change.change_type).lower()
                ):
                    # File exists only in store
                    resolution_map = {
                        "k": Resolution.USE_REMOTE,  # keep in store = copy to local
                        "d": Resolution.USE_LOCAL,  # delete from store = use local (which doesn't exist)
                        "s": Resolution.SKIP,
                    }
                elif (
                    "only in local" in str(change.change_type).lower()
                    or "added_local" in str(change.change_type).lower()
                ):
                    # File exists only in local
                    resolution_map = {
                        "k": Resolution.USE_LOCAL,  # keep in local = copy to store
                        "d": Resolution.USE_REMOTE,  # delete from local = use remote (which doesn't exist)
                        "s": Resolution.SKIP,
                    }
                else:
                    # Modified in both
                    resolution_map = {
                        "l": Resolution.USE_LOCAL,
                        "r": Resolution.USE_REMOTE,
                        "s": Resolution.SKIP,
                    }

                return resolution_map[choice]

            except (EOFError, KeyboardInterrupt):
                # Handle Ctrl+C or EOF gracefully
                self.console.print("\n[yellow]Skipping conflict...[/yellow]")
                return Resolution.SKIP

    def display_conflicts_summary(self, changes: list[FileChange]) -> None:
        """Display a summary of all conflicts before resolution.

        Lists all conflicting files in a formatted panel.

        Args:
            changes: List of FileChange objects representing conflicts

        Validates:
        - Requirement 4.3: List all conflicts before prompting for resolution
        """
        if not changes:
            self.console.print("[green]No conflicts detected.[/green]")
            return

        self.console.print()
        self.console.print(
            Panel(
                f"[bold red]Found {len(changes)} conflict(s)[/bold red]",
                border_style="red",
            )
        )

        # List all conflicts (Requirement 4.3)
        for i, change in enumerate(changes, start=1):
            conflict_line = Text()
            conflict_line.append(f"  {i}. ", style="dim")
            conflict_line.append("[Conflict] ", style="red")
            conflict_line.append(change.path, style="white")

            # Add change type indicator
            type_indicator, _ = self._get_change_type_indicator(change.change_type)
            conflict_line.append(f" ({type_indicator})", style="dim")

            if change.is_binary:
                conflict_line.append(" [binary]", style="yellow")

            self.console.print(conflict_line)

        self.console.print()

    def _display_change_type(self, change: FileChange) -> None:
        """Display the type of change detected."""
        type_text = Text()
        type_text.append("Status: ", style="dim")

        indicator, description = self._get_change_type_indicator(change.change_type)

        if change.change_type == ChangeType.ADDED_LOCAL:
            type_text.append(indicator, style="green")
        elif change.change_type == ChangeType.ADDED_REMOTE:
            type_text.append(indicator, style="blue")
        elif change.change_type == ChangeType.MODIFIED:
            type_text.append(indicator, style="yellow")
        else:
            type_text.append(indicator, style="dim")

        self.console.print(type_text)

        # Display additional description
        if description:
            desc_text = Text()
            desc_text.append("Description: ", style="dim")
            desc_text.append(description, style="white")
            self.console.print(desc_text)

    def _display_file_locations(self, change: FileChange) -> None:
        """Display the local and remote file paths."""
        if change.local_path:
            local_text = Text()
            local_text.append("  Local:  ", style="dim")
            local_text.append(str(change.local_path), style="cyan")
            self.console.print(local_text)

        if change.remote_path:
            remote_text = Text()
            remote_text.append("  Remote: ", style="dim")
            remote_text.append(str(change.remote_path), style="magenta")
            self.console.print(remote_text)

    def _display_diff(self, diff_output: str) -> None:
        """Display the diff output with syntax highlighting.

        Validates:
        - Requirement 4.4: Display both local and remote versions in diff output
        """
        self.console.print()
        self.console.print("[dim]─── Diff ───[/dim]")

        # Use Rich Syntax for diff highlighting
        syntax = Syntax(
            diff_output,
            "diff",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
        )
        self.console.print(syntax)
        self.console.print("[dim]────────────[/dim]")

    def _display_file_preview(self, change: FileChange) -> None:
        """Display file preview for 'only in' cases.

        Shows a preview of the file content to help user decide.
        """
        # Determine which file to preview
        preview_path = None
        preview_label = None

        if change.local_path and change.local_path.exists():
            preview_path = change.local_path
            preview_label = "Local file preview"
        elif change.remote_path and change.remote_path.exists():
            preview_path = change.remote_path
            preview_label = "Remote file preview"

        if not preview_path or change.is_binary:
            return

        try:
            # Read first 20 lines or 1000 characters
            with open(preview_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(1000)
                lines = content.split("\n")[:20]
                preview_content = "\n".join(lines)

            self.console.print()
            self.console.print(f"[dim]─── {preview_label} ───[/dim]")

            # Detect file type for syntax highlighting
            file_ext = preview_path.suffix.lstrip(".")
            if file_ext in [
                "py",
                "js",
                "ts",
                "java",
                "cpp",
                "c",
                "go",
                "rs",
                "md",
                "yaml",
                "yml",
                "json",
                "xml",
                "html",
                "css",
            ]:
                syntax = Syntax(
                    preview_content,
                    file_ext,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                )
                self.console.print(syntax)
            else:
                self.console.print(preview_content, style="dim")

            if len(content) > 1000 or len(lines) > 20:
                self.console.print("[dim]... (truncated)[/dim]")

            self.console.print("[dim]" + "─" * 40 + "[/dim]")

        except Exception:
            # If preview fails, silently skip
            pass

    def _display_resolution_result(
        self,
        change: FileChange,
        resolution: Resolution,
    ) -> None:
        """Display the resolution result.

        Validates:
        - Requirement 6.4: Display which files were resolved and how
        """
        result_text = Text()
        result_text.append("  → ", style="dim")
        result_text.append(change.path, style="white")
        result_text.append(": ", style="dim")

        if resolution == Resolution.USE_LOCAL:
            result_text.append("using local version", style="green")
        elif resolution == Resolution.USE_REMOTE:
            result_text.append("using remote version", style="blue")
        elif resolution == Resolution.SKIP:
            result_text.append("skipped", style="dim")

        self.console.print(result_text)

    def _get_change_type_indicator(self, change_type: ChangeType) -> tuple[str, str]:
        """Get a human-readable indicator and description for the change type.

        Returns:
            Tuple of (indicator, description) where:
            - indicator: Short status text
            - description: Detailed explanation of what this means
        """
        indicators = {
            ChangeType.ADDED_LOCAL: (
                "exists only in local",
                "This file exists in the current project but not in Store",
            ),
            ChangeType.ADDED_REMOTE: (
                "exists only in store",
                "This file exists in Store but not in the current project",
            ),
            ChangeType.MODIFIED: (
                "modified in both",
                "This file has been modified differently in both local and Store",
            ),
            ChangeType.UNCHANGED: ("unchanged", ""),
        }
        return indicators.get(change_type, ("unknown", ""))
