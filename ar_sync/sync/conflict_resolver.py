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
- 5.1: Prompt for each conflict with options: [l]ocal / [r]emote / [m]erge / [s]kip
- 5.2: When user selects `l` (local), copy Project_Directory version to Store
- 5.3: When user selects `r` (remote), copy Store version to Project_Directory
- 5.5: When user selects `s` (skip), leave both versions unchanged
- 6.1: --local option automatically prefers Project_Directory files
- 6.2: --remote option automatically prefers Store files
- 6.4: Display which files were resolved and how
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from ar_sync.sync.merge_engine import MergeEngine


class ConflictResolver:
    """Handler for resolving conflicts between Project and Store files.
    
    This class provides:
    - Interactive conflict resolution with user prompts
    - Automatic resolution using --local or --remote strategies
    - Rich-formatted conflict display with diff output
    - Support for merge operations (text files only)
    
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
        merge_engine: MergeEngine,
    ) -> ResolvedChange:
        """Resolve a conflict interactively by prompting the user.
        
        Displays the conflict information and diff, then prompts the user
        to choose a resolution strategy.
        
        Args:
            change: The FileChange representing the conflict
            merge_engine: MergeEngine instance for merge operations
            
        Returns:
            ResolvedChange with the user's chosen resolution
            
        Validates:
        - Requirement 4.4: Display both local and remote versions in diff output
        - Requirement 5.1: Prompt with [l]ocal / [r]emote / [m]erge / [s]kip options
        - Requirement 5.2: Local selection copies Project to Store
        - Requirement 5.3: Remote selection copies Store to Project
        - Requirement 5.5: Skip leaves both versions unchanged
        """
        # Display the conflict information
        self.display_conflict(change)
        
        # Prompt for resolution
        resolution = self.prompt_resolution(change)
        
        # Handle merge if selected
        merged_content: str | None = None
        if resolution == Resolution.MERGE:
            merged_content = self._perform_merge(change, merge_engine)
            if merged_content is None:
                # Merge failed or was cancelled, prompt again
                self.console.print(
                    "[yellow]Merge failed or was cancelled. Please choose another option.[/yellow]"
                )
                resolution = self.prompt_resolution(change)
        
        # Display resolution result (Requirement 6.4)
        self._display_resolution_result(change, resolution)
        
        return ResolvedChange(
            file_change=change,
            resolution=resolution,
            merged_content=merged_content,
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
            merged_content=None,
        )
    
    def display_conflict(self, change: FileChange) -> None:
        """Display conflict information with Rich formatting.
        
        Shows:
        - Conflict header with file path (Requirement 4.2)
        - Change type information
        - Diff output showing both versions (Requirement 4.4)
        
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
        
        # Display binary file warning if applicable
        if change.is_binary:
            self.console.print(
                "[yellow]⚠ This is a binary file. Merge option is not available.[/yellow]"
            )
    
    def prompt_resolution(self, change: FileChange) -> Resolution:
        """Prompt the user to choose a resolution method.
        
        Displays options and waits for user input:
        - [l]ocal: Use Project_Directory version
        - [r]emote: Use Store version
        - [m]erge: Perform 3-way merge (disabled for binary files)
        - [s]kip: Leave both versions unchanged
        
        Args:
            change: The FileChange being resolved
            
        Returns:
            The user's chosen Resolution
            
        Validates:
        - Requirement 5.1: Prompt with [l]ocal / [r]emote / [m]erge / [s]kip options
        - Requirement 5.7: Disable merge option for binary files
        """
        # Build options text (Requirement 5.1)
        options = Text()
        options.append("[l]", style="bold cyan")
        options.append("ocal / ", style="dim")
        options.append("[r]", style="bold cyan")
        options.append("emote / ", style="dim")
        
        # Disable merge for binary files (Requirement 5.7)
        if change.is_binary:
            options.append("[m]", style="dim strikethrough")
            options.append("erge / ", style="dim strikethrough")
        else:
            options.append("[m]", style="bold cyan")
            options.append("erge / ", style="dim")
        
        options.append("[s]", style="bold cyan")
        options.append("kip", style="dim")
        
        self.console.print()
        self.console.print("Choose resolution: ", end="")
        self.console.print(options)
        
        # Valid choices
        valid_choices = {'l', 'r', 's'}
        if not change.is_binary:
            valid_choices.add('m')
        
        while True:
            try:
                choice = self.console.input("[bold]> [/bold]").strip().lower()
                
                if not choice:
                    continue
                
                # Take first character
                choice = choice[0]
                
                if choice not in valid_choices:
                    if choice == 'm' and change.is_binary:
                        self.console.print(
                            "[red]Merge is not available for binary files.[/red]"
                        )
                    else:
                        self.console.print(
                            f"[red]Invalid choice '{choice}'. Please enter l, r, m, or s.[/red]"
                        )
                    continue
                
                # Map choice to Resolution
                resolution_map = {
                    'l': Resolution.USE_LOCAL,
                    'r': Resolution.USE_REMOTE,
                    'm': Resolution.MERGE,
                    's': Resolution.SKIP,
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
            type_indicator = self._get_change_type_indicator(change.change_type)
            conflict_line.append(f" ({type_indicator})", style="dim")
            
            if change.is_binary:
                conflict_line.append(" [binary]", style="yellow")
            
            self.console.print(conflict_line)
        
        self.console.print()
    
    def _display_change_type(self, change: FileChange) -> None:
        """Display the type of change detected."""
        type_text = Text()
        type_text.append("Type: ", style="dim")
        
        indicator = self._get_change_type_indicator(change.change_type)
        
        if change.change_type == ChangeType.ADDED_LOCAL:
            type_text.append(indicator, style="green")
        elif change.change_type == ChangeType.ADDED_REMOTE:
            type_text.append(indicator, style="blue")
        elif change.change_type == ChangeType.MODIFIED:
            type_text.append(indicator, style="yellow")
        else:
            type_text.append(indicator, style="dim")
        
        self.console.print(type_text)
    
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
        elif resolution == Resolution.MERGE:
            result_text.append("merged", style="yellow")
        elif resolution == Resolution.SKIP:
            result_text.append("skipped", style="dim")
        
        self.console.print(result_text)
    
    def _get_change_type_indicator(self, change_type: ChangeType) -> str:
        """Get a human-readable indicator for the change type."""
        indicators = {
            ChangeType.ADDED_LOCAL: "only in project",
            ChangeType.ADDED_REMOTE: "only in store",
            ChangeType.MODIFIED: "modified in both",
            ChangeType.UNCHANGED: "unchanged",
        }
        return indicators.get(change_type, "unknown")
    
    def _perform_merge(
        self,
        change: FileChange,
        merge_engine: MergeEngine,
    ) -> str | None:
        """Perform a merge operation for the given change.
        
        Args:
            change: The FileChange to merge
            merge_engine: MergeEngine instance for merge operations
            
        Returns:
            Merged content if successful, None if merge failed or was cancelled
            
        Validates:
        - Requirement 5.4: Perform 3-way merge using git merge-file
        - Requirement 5.6: Display conflict markers if merge has conflicts
        """
        if change.local_path is None or change.remote_path is None:
            self.console.print(
                "[red]Cannot merge: both local and remote files must exist.[/red]"
            )
            return None
        
        # Perform merge (no base for 2-way merge)
        result = merge_engine.merge_files(
            base_path=None,
            local_path=change.local_path,
            remote_path=change.remote_path,
        )
        
        if not result.success and not result.has_conflicts:
            # Merge failed completely
            self.console.print("[red]Merge failed.[/red]")
            return None
        
        if result.has_conflicts:
            # Merge has conflicts (Requirement 5.6)
            self.console.print(
                "[yellow]Merge completed with conflicts. "
                "Please resolve conflict markers manually.[/yellow]"
            )
            
            # Show conflict locations
            if result.conflict_markers:
                self.console.print("[dim]Conflict locations:[/dim]")
                for start, end in result.conflict_markers:
                    self.console.print(f"  Lines {start}-{end}")
            
            # Display merged content with conflicts
            if result.merged_content:
                self.console.print()
                self.console.print("[dim]─── Merged content with conflicts ───[/dim]")
                syntax = Syntax(
                    result.merged_content,
                    "text",
                    theme="monokai",
                    line_numbers=True,
                )
                self.console.print(syntax)
                self.console.print("[dim]──────────────────────────────────────[/dim]")
        else:
            self.console.print("[green]Merge completed successfully.[/green]")
        
        return result.merged_content
