"""
ar_sync.sync.bidirectional_sync - Main orchestrator for bidirectional synchronization.

This module provides the BidirectionalSync class that coordinates the full
synchronization flow between Project, Store, and Remote.

Synchronization Flow:
1. Pull Phase: Remote → Store (git pull)
2. Detect Changes: Project ↔ Store (content-based diff)
3. Resolve Conflicts: Interactive or automatic resolution
4. Push Phase: Store → Remote (git commit && push)

Requirements:
- 1.1: Pull changes from Remote to Store before any other operations
- 1.2: Display the number of files changed from remote
- 1.3: Display "already up to date" message when no changes
- 8.1: Commit changes to Store with a descriptive message
- 8.2: Include list of synced files in commit message
- 8.3: Push to Remote after commit succeeds
- 8.5: Skip commit and push when no changes were made
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from ar_sync.errors import ErrorCategory, SyncError
from ar_sync.sync.conflict_resolver import ConflictResolver
from ar_sync.sync.diff_engine import DiffEngine
from ar_sync.sync.merge_engine import MergeEngine
from ar_sync.sync.models import (
    ChangeType,
    FileChange,
    Resolution,
    ResolutionStrategy,
    ResolvedChange,
    SyncOptions,
    SyncResult,
)

if TYPE_CHECKING:
    from ar_sync.git_backend import GitBackend


class BidirectionalSync:
    """Main orchestrator for bidirectional synchronization.

    This class coordinates the full sync flow:
    1. Pull Phase: Remote → Store
    2. Detect Changes: Project ↔ Store
    3. Resolve Conflicts: Interactive or automatic
    4. Apply Changes: File operations
    5. Push Phase: Store → Remote

    Validates:
    - Requirement 1.1, 1.2, 1.3: Pull phase operations
    - Requirement 8.1, 8.2, 8.3, 8.5: Push phase operations
    """

    def __init__(
        self,
        project_dir: Path,
        store_path: Path,
        project_name: str,
        targets: list[str],
        git_backend: GitBackend | None = None,
        console: Console | None = None,
    ):
        """Initialize the BidirectionalSync orchestrator.

        Args:
            project_dir: Path to the project directory
            store_path: Path to the store directory (project-specific subdirectory)
            project_name: Name of the project in the store
            targets: List of target file/directory names to sync
            git_backend: GitBackend instance for remote operations (optional)
            console: Rich Console instance for output (optional)
        """
        self.project_dir = Path(project_dir)
        self.store_path = Path(store_path)
        self.project_name = project_name
        self.targets = targets
        self.git_backend = git_backend
        self.console = console or Console()

        # Initialize component engines
        self.diff_engine = DiffEngine()
        self.merge_engine = MergeEngine()
        self.conflict_resolver = ConflictResolver(console=self.console)

    def sync(self, options: SyncOptions) -> SyncResult:
        """Perform full bidirectional synchronization.

        Orchestrates the complete sync flow based on the provided options:
        - Full sync: Pull → Detect → Resolve → Apply → Push
        - Pull only: Pull → Detect → Resolve → Apply (no push)
        - Push only: Detect → Resolve → Apply → Push (no pull)
        - Diff only: Detect → Display (no changes applied)
        - Dry run: Full flow but no actual file modifications

        Args:
            options: SyncOptions controlling the sync behavior

        Returns:
            SyncResult with operation summary
        """
        result = SyncResult(
            pulled_files=0,
            pushed_files=0,
            conflicts_resolved=0,
            skipped_files=[],
            errors=[],
        )

        # Phase 1: Pull from Remote (Requirement 1.1)
        if not options.push_only:
            pulled_count = self._pull_phase(options)
            result.pulled_files = pulled_count

        # Phase 2: Detect changes between Project and Store
        changes = self._detect_changes()

        # If diff_only mode, just display and return
        if options.diff_only:
            self._display_diff_only(changes, options)
            return result

        # If no changes detected
        if not changes:
            if options.dry_run:
                self.console.print("[DRY-RUN] No changes detected.")
            else:
                self.console.print("[green]✓ Already in sync. No changes needed.[/green]")
            return result

        # Phase 3: Resolve conflicts
        resolved = self._resolve_conflicts(changes, options)

        # Count resolved conflicts (excluding skipped)
        resolved_count = sum(
            1 for r in resolved
            if r.resolution != Resolution.SKIP
        )
        result.conflicts_resolved = resolved_count

        # Track skipped files
        result.skipped_files = [
            r.file_change.path for r in resolved
            if r.resolution == Resolution.SKIP
        ]

        # Phase 4: Apply changes (unless dry-run)
        if not options.dry_run:
            applied_changes = self._apply_changes(resolved)
        else:
            applied_changes = resolved
            self._display_dry_run_changes(resolved)

        # Phase 5: Push to Remote (Requirement 8.1, 8.2, 8.3, 8.5)
        if not options.pull_only and not options.dry_run:
            pushed_count = self._push_phase(applied_changes)
            result.pushed_files = pushed_count

        return result

    def _pull_phase(self, options: SyncOptions) -> int:
        """Execute Remote → Store synchronization.

        Pulls changes from the remote repository to the local store.

        Args:
            options: SyncOptions for dry-run checking

        Returns:
            Number of files changed from remote

        Raises:
            SyncError: If pull fails due to network error or Git conflict

        Validates:
        - Requirement 1.1: Pull changes from Remote to Store before any other operations
        - Requirement 1.2: Display the number of files changed from remote
        - Requirement 1.3: Display "already up to date" message when no changes
        - Requirement 1.4: Display error message with recovery steps on network error
        - Requirement 1.5: Display instructions for manual resolution on Git conflict
        """
        if self.git_backend is None:
            if options.dry_run:
                self.console.print("[DRY-RUN] Would pull from remote (no git backend configured)")
            return 0

        prefix = "[DRY-RUN] " if options.dry_run else ""

        try:
            if options.dry_run:
                # In dry-run mode, just check if pull is needed
                needs_pull = self.git_backend.needs_pull()
                if needs_pull:
                    self.console.print(f"{prefix}Would pull changes from remote")
                else:
                    self.console.print(f"{prefix}Remote is already up to date")
                return 0

            # Perform actual pull (Requirement 1.1)
            pull_result = self.git_backend.pull()

            files_changed = pull_result.get('files_changed', 0)

            # Display result (Requirement 1.2, 1.3)
            if files_changed > 0:
                self.console.print(
                    f"[cyan]↓ Pulled {files_changed} file(s) from remote[/cyan]"
                )
            else:
                self.console.print(
                    "[dim]Remote is already up to date[/dim]"
                )

            return files_changed

        except RuntimeError as e:
            error_msg = str(e).lower()

            # Detect Git conflict (Requirement 1.5)
            if "conflict" in error_msg or "merge" in error_msg:
                raise SyncError(
                    message=f"Pull failed due to Git conflict: {e}",
                    category=ErrorCategory.GIT,
                ) from e

            # Detect network error (Requirement 1.4)
            if any(keyword in error_msg for keyword in [
                "network", "connection", "timeout", "refused",
                "could not resolve", "unable to access", "fatal:"
            ]):
                raise SyncError(
                    message=f"Pull failed due to network error: {e}",
                    category=ErrorCategory.GIT,
                ) from e

            # Generic Git error
            raise SyncError(
                message=f"Pull failed: {e}",
                category=ErrorCategory.GIT,
            ) from e

        except OSError as e:
            # Handle file system errors during pull
            raise SyncError(
                message=f"Pull failed due to file system error: {e}",
                category=ErrorCategory.FILE_SYSTEM,
            ) from e

    def _detect_changes(self) -> list[FileChange]:
        """Detect changes between Project and Store.

        Uses DiffEngine to compare target files/directories between
        the project directory and the store.

        Returns:
            List of FileChange objects representing detected changes
        """
        return self.diff_engine.compare_directories(
            project_dir=self.project_dir,
            store_dir=self.store_path,
            targets=self.targets,
        )

    def _resolve_conflicts(
        self,
        changes: list[FileChange],
        options: SyncOptions,
    ) -> list[ResolvedChange]:
        """Resolve conflicts using ConflictResolver.

        Handles conflict resolution based on the strategy specified in options:
        - INTERACTIVE: Prompt user for each conflict
        - LOCAL: Automatically prefer project files
        - REMOTE: Automatically prefer store files

        Args:
            changes: List of detected changes to resolve
            options: SyncOptions with resolution strategy

        Returns:
            List of ResolvedChange objects with resolution decisions
        """
        resolved: list[ResolvedChange] = []

        # Display conflicts summary first
        self.conflict_resolver.display_conflicts_summary(changes)

        for change in changes:
            if options.strategy == ResolutionStrategy.INTERACTIVE:
                # Interactive resolution
                resolution = self.conflict_resolver.resolve_interactive(
                    change=change,
                    merge_engine=self.merge_engine,
                )
            else:
                # Automatic resolution (LOCAL or REMOTE)
                resolution = self.conflict_resolver.resolve_automatic(
                    change=change,
                    strategy=options.strategy,
                )

            resolved.append(resolution)

        return resolved

    def _apply_changes(self, resolved: list[ResolvedChange]) -> list[ResolvedChange]:
        """Apply resolved changes to files.

        Performs actual file operations based on resolution decisions:
        - USE_LOCAL: Copy project file to store
        - USE_REMOTE: Copy store file to project
        - MERGE: Write merged content to both locations
        - SKIP: No action

        Args:
            resolved: List of resolved changes to apply

        Returns:
            List of successfully applied changes

        Raises:
            SyncError: Re-raises SyncError from _apply_single_change

        Validates:
        - Requirement 11.1: Display the specific file and error reason
        - Requirement 11.3: Provide actionable recovery steps
        """
        applied: list[ResolvedChange] = []

        for change in resolved:
            if change.resolution == Resolution.SKIP:
                continue

            # Let SyncError propagate up for proper handling
            # This ensures the caller can display formatted error messages
            self._apply_single_change(change)
            applied.append(change)

        return applied

    def _apply_single_change(self, resolved: ResolvedChange) -> None:
        """Apply a single resolved change.

        Args:
            resolved: The resolved change to apply

        Raises:
            SyncError: If file operation fails due to permission or I/O error

        Validates:
        - Requirement 11.1: Display the specific file and error reason
        - Requirement 11.3: Provide actionable recovery steps
        """
        change = resolved.file_change
        resolution = resolved.resolution

        try:
            if resolution == Resolution.USE_LOCAL:
                # Copy project file to store
                self._copy_to_store(change)

            elif resolution == Resolution.USE_REMOTE:
                # Copy store file to project
                self._copy_to_project(change)

            elif resolution == Resolution.MERGE:
                # Write merged content to both locations
                if resolved.merged_content is not None:
                    self._write_merged_content(change, resolved.merged_content)

        except PermissionError as e:
            raise SyncError(
                message=f"Permission denied: {e}",
                category=ErrorCategory.FILE_SYSTEM,
                file_path=change.path,
            ) from e

        except OSError as e:
            raise SyncError(
                message=f"File operation failed: {e}",
                category=ErrorCategory.FILE_SYSTEM,
                file_path=change.path,
            ) from e

        except OSError as e:
            raise SyncError(
                message=f"I/O error: {e}",
                category=ErrorCategory.FILE_SYSTEM,
                file_path=change.path,
            ) from e

    def _copy_to_store(self, change: FileChange) -> None:
        """Copy file or directory from project to store.

        Handles both new files (ADDED_LOCAL) and modified files.
        Uses shutil.copy2 to preserve metadata for files.
        Uses shutil.copytree with copy_function=shutil.copy2 for directories.

        Args:
            change: FileChange with local_path to copy

        Raises:
            PermissionError: If permission denied during copy
            OSError: If file operation fails

        Validates:
        - Requirement 10.1: Preserve file permissions (chmod)
        - Requirement 10.2: Preserve file modification timestamps
        - Requirement 10.3: Preserve directory structure and permissions
        - Requirement 11.1: Display the specific file and error reason
        """
        if change.local_path is None:
            return

        # Determine destination path in store
        dest_path = self.store_path / change.path

        try:
            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle directory vs file
            if change.local_path.is_dir():
                # Remove existing destination if it exists
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                # Copy directory tree with metadata preservation (Requirement 10.3)
                shutil.copytree(
                    change.local_path,
                    dest_path,
                    copy_function=shutil.copy2
                )
            else:
                # Copy file with metadata preservation (Requirement 10.1, 10.2)
                shutil.copy2(change.local_path, dest_path)

        except PermissionError:
            # Re-raise to be caught by _apply_single_change
            raise

        except OSError:
            # Re-raise to be caught by _apply_single_change
            raise

    def _copy_to_project(self, change: FileChange) -> None:
        """Copy file or directory from store to project.

        Handles both new files (ADDED_REMOTE) and modified files.
        Uses shutil.copy2 to preserve metadata for files.
        Uses shutil.copytree with copy_function=shutil.copy2 for directories.

        Args:
            change: FileChange with remote_path to copy

        Raises:
            PermissionError: If permission denied during copy
            OSError: If file operation fails

        Validates:
        - Requirement 10.1: Preserve file permissions (chmod)
        - Requirement 10.2: Preserve file modification timestamps
        - Requirement 10.3: Preserve directory structure and permissions
        - Requirement 11.1: Display the specific file and error reason
        """
        if change.remote_path is None:
            return

        # Determine destination path in project
        dest_path = self.project_dir / change.path

        try:
            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle directory vs file
            if change.remote_path.is_dir():
                # Remove existing destination if it exists
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                # Copy directory tree with metadata preservation (Requirement 10.3)
                shutil.copytree(
                    change.remote_path,
                    dest_path,
                    copy_function=shutil.copy2
                )
            else:
                # Copy file with metadata preservation (Requirement 10.1, 10.2)
                shutil.copy2(change.remote_path, dest_path)

        except PermissionError:
            # Re-raise to be caught by _apply_single_change
            raise

        except OSError:
            # Re-raise to be caught by _apply_single_change
            raise

    def _write_merged_content(self, change: FileChange, content: str) -> None:
        """Write merged content to both project and store.

        Preserves file permissions and timestamps from the original files.

        Args:
            change: FileChange with paths to write to
            content: Merged content to write

        Validates:
        - Requirement 10.1: Preserve file permissions (chmod)
        - Requirement 10.2: Preserve file modification timestamps
        """
        import os
        import time

        # Get original file metadata for preservation
        original_mode = None
        original_mtime = None

        # Prefer local file metadata, fallback to remote
        if change.local_path and change.local_path.exists():
            stat_info = change.local_path.stat()
            original_mode = stat_info.st_mode
            original_mtime = stat_info.st_mtime
        elif change.remote_path and change.remote_path.exists():
            stat_info = change.remote_path.stat()
            original_mode = stat_info.st_mode
            original_mtime = stat_info.st_mtime

        # Write to project
        project_path = self.project_dir / change.path
        project_path.parent.mkdir(parents=True, exist_ok=True)
        project_path.write_text(content, encoding='utf-8')

        # Preserve metadata on project file
        if original_mode is not None:
            os.chmod(project_path, original_mode)
        if original_mtime is not None:
            os.utime(project_path, (time.time(), original_mtime))

        # Write to store
        store_path = self.store_path / change.path
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store_path.write_text(content, encoding='utf-8')

        # Preserve metadata on store file
        if original_mode is not None:
            os.chmod(store_path, original_mode)
        if original_mtime is not None:
            os.utime(store_path, (time.time(), original_mtime))

    def _push_phase(self, resolved: list[ResolvedChange]) -> int:
        """Execute Store → Remote synchronization.

        Commits changes to the store and pushes to remote.

        Args:
            resolved: List of applied changes for commit message

        Returns:
            Number of files pushed

        Raises:
            SyncError: If push fails due to network error or Git error

        Validates:
        - Requirement 8.1: Commit changes to Store with a descriptive message
        - Requirement 8.2: Include list of synced files in commit message
        - Requirement 8.3: Push to Remote after commit succeeds
        - Requirement 8.4: Display error message with recovery steps on push failure
        - Requirement 8.5: Skip commit and push when no changes were made
        """
        if self.git_backend is None:
            return 0

        # Requirement 8.5: Skip if no changes
        if not resolved:
            self.console.print("[dim]No changes to push[/dim]")
            return 0

        # Build commit message (Requirement 8.1, 8.2)
        commit_message = self._build_commit_message(resolved)

        try:
            # Commit and push (Requirement 8.3)
            push_result = self.git_backend.commit_and_push(message=commit_message)

            files_changed = push_result.get('files_changed', 0)

            if push_result.get('pushed', False):
                self.console.print(
                    f"[cyan]↑ Pushed {files_changed} file(s) to remote[/cyan]"
                )
            elif push_result.get('committed', False):
                self.console.print(
                    f"[yellow]Committed {files_changed} file(s) but push failed[/yellow]"
                )
            else:
                self.console.print("[dim]No changes to commit[/dim]")

            return files_changed

        except RuntimeError as e:
            # Requirement 8.4: Display error message with recovery steps
            error_msg = str(e).lower()

            # Detect network error
            if any(keyword in error_msg for keyword in [
                "network", "connection", "timeout", "refused",
                "could not resolve", "unable to access", "fatal:"
            ]):
                raise SyncError(
                    message=f"Push failed due to network error: {e}",
                    category=ErrorCategory.GIT,
                ) from e

            # Detect authentication error
            if any(keyword in error_msg for keyword in [
                "authentication", "permission", "denied", "403", "401"
            ]):
                raise SyncError(
                    message=f"Push failed due to authentication error: {e}",
                    category=ErrorCategory.GIT,
                ) from e

            # Generic Git error
            raise SyncError(
                message=f"Push failed: {e}",
                category=ErrorCategory.GIT,
            ) from e

        except OSError as e:
            # Handle file system errors during push
            raise SyncError(
                message=f"Push failed due to file system error: {e}",
                category=ErrorCategory.FILE_SYSTEM,
            ) from e

    def _build_commit_message(self, resolved: list[ResolvedChange]) -> str:
        """Build a descriptive commit message.

        Args:
            resolved: List of resolved changes to include in message

        Returns:
            Formatted commit message

        Validates:
        - Requirement 8.1: Descriptive commit message
        - Requirement 8.2: Include list of synced files
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Count changes by type
        local_count = sum(
            1 for r in resolved
            if r.resolution == Resolution.USE_LOCAL
        )
        remote_count = sum(
            1 for r in resolved
            if r.resolution == Resolution.USE_REMOTE
        )
        merge_count = sum(
            1 for r in resolved
            if r.resolution == Resolution.MERGE
        )

        # Build summary line
        parts = []
        if local_count > 0:
            parts.append(f"{local_count} from project")
        if remote_count > 0:
            parts.append(f"{remote_count} from store")
        if merge_count > 0:
            parts.append(f"{merge_count} merged")

        summary = ", ".join(parts) if parts else "sync"

        # Build file list (Requirement 8.2)
        file_list = "\n".join(
            f"  - {r.file_change.path} ({r.resolution.value})"
            for r in resolved
            if r.resolution != Resolution.SKIP
        )

        message = f"Sync: {summary}\n\nSynced files:\n{file_list}\n\nTimestamp: {timestamp}"

        return message

    def _display_diff_only(
        self,
        changes: list[FileChange],
        options: SyncOptions,
    ) -> None:
        """Display diff output without applying changes.

        Args:
            changes: List of detected changes
            options: SyncOptions for formatting
        """
        prefix = "[DRY-RUN] " if options.dry_run else ""

        if not changes:
            self.console.print(f"{prefix}No differences found.")
            return

        self.console.print(f"\n{prefix}Differences found:\n")

        for change in changes:
            self._display_single_diff(change)

    def _display_single_diff(self, change: FileChange) -> None:
        """Display diff for a single file change.

        Args:
            change: FileChange to display
        """
        # Display file path and change type
        type_indicator = self._get_change_type_indicator(change.change_type)
        self.console.print(f"[bold]{change.path}[/bold] ({type_indicator})")

        # Display diff output if available
        if change.diff_output:
            self.console.print(change.diff_output)

        self.console.print()

    def _display_dry_run_changes(self, resolved: list[ResolvedChange]) -> None:
        """Display what changes would be made in dry-run mode.

        Args:
            resolved: List of resolved changes
        """
        self.console.print("\n[DRY-RUN] Would apply the following changes:\n")

        for r in resolved:
            if r.resolution == Resolution.SKIP:
                continue

            action = self._get_resolution_action(r.resolution, r.file_change.change_type)
            self.console.print(f"  [DRY-RUN] {r.file_change.path}: {action}")

    def _get_change_type_indicator(self, change_type: ChangeType) -> str:
        """Get human-readable indicator for change type."""
        indicators = {
            ChangeType.ADDED_LOCAL: "only in project",
            ChangeType.ADDED_REMOTE: "only in store",
            ChangeType.MODIFIED: "modified",
            ChangeType.UNCHANGED: "unchanged",
        }
        return indicators.get(change_type, "unknown")

    def _get_resolution_action(
        self,
        resolution: Resolution,
        change_type: ChangeType,
    ) -> str:
        """Get human-readable action description for resolution."""
        if resolution == Resolution.USE_LOCAL:
            if change_type == ChangeType.ADDED_LOCAL:
                return "would copy to store (new file)"
            return "would copy to store (overwrite)"

        elif resolution == Resolution.USE_REMOTE:
            if change_type == ChangeType.ADDED_REMOTE:
                return "would copy to project (new file)"
            return "would copy to project (overwrite)"

        elif resolution == Resolution.MERGE:
            return "would merge and write to both"

        elif resolution == Resolution.SKIP:
            return "would skip"

        return "unknown action"
