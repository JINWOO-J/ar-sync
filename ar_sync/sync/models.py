"""
ar_sync.sync.models - Data models for bidirectional synchronization.

This module defines all data models used in the sync module:
- Enums: ChangeType, Resolution, ResolutionStrategy
- Dataclasses: SyncOptions, FileChange, ResolvedChange, SyncResult, MergeResult

Requirements:
- 5.1: Interactive conflict resolution options (l/r/m/s)
- 6.1: --local option for automatic local preference
- 6.2: --remote option for automatic remote preference
- 7.1: --dry-run option for preview mode
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ChangeType(Enum):
    """Type of change detected between Project and Store.
    
    Used by DiffEngine to categorize file differences.
    """
    ADDED_LOCAL = "added_local"      # File exists only in Project
    ADDED_REMOTE = "added_remote"    # File exists only in Store
    MODIFIED = "modified"            # File exists in both but content differs
    UNCHANGED = "unchanged"          # File exists in both with same content


class Resolution(Enum):
    """Resolution choice for a conflict.
    
    Validates: Requirement 5.1 - Interactive options [l]ocal/[r]emote/[m]erge/[s]kip
    """
    USE_LOCAL = "local"    # Copy Project version to Store
    USE_REMOTE = "remote"  # Copy Store version to Project
    MERGE = "merge"        # Perform 3-way merge
    SKIP = "skip"          # Leave both versions unchanged


class ResolutionStrategy(Enum):
    """Strategy for resolving conflicts.
    
    Validates:
    - Requirement 6.1: --local option for automatic local preference
    - Requirement 6.2: --remote option for automatic remote preference
    """
    INTERACTIVE = "interactive"  # Prompt user for each conflict (default)
    LOCAL = "local"              # Automatically prefer Project files
    REMOTE = "remote"            # Automatically prefer Store files


@dataclass
class SyncOptions:
    """Options for sync operation.
    
    Validates:
    - Requirement 6.1, 6.2: strategy field for automatic resolution
    - Requirement 7.1: dry_run field for preview mode
    """
    strategy: ResolutionStrategy = ResolutionStrategy.INTERACTIVE
    dry_run: bool = False
    diff_only: bool = False
    pull_only: bool = False
    push_only: bool = False


@dataclass
class FileChange:
    """Represents a detected change between Project and Store.
    
    Used by DiffEngine to report comparison results.
    """
    path: str                        # Relative path from project/store root
    change_type: ChangeType
    local_path: Path | None          # Full path to Project file (None if not exists)
    remote_path: Path | None         # Full path to Store file (None if not exists)
    is_binary: bool = False
    diff_output: str | None = None   # git diff --no-index output


@dataclass
class ResolvedChange:
    """Represents a resolved conflict.
    
    Used by ConflictResolver to track resolution decisions.
    """
    file_change: FileChange
    resolution: Resolution
    merged_content: str | None = None  # Content after merge (if resolution is MERGE)


@dataclass
class SyncResult:
    """Result of a sync operation.
    
    Returned by BidirectionalSync.sync() to report operation summary.
    """
    pulled_files: int
    pushed_files: int
    conflicts_resolved: int
    skipped_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """Result of a merge operation.
    
    Returned by MergeEngine.merge_files() to report merge outcome.
    """
    success: bool
    merged_content: str | None
    has_conflicts: bool
    conflict_markers: list[tuple[int, int]] = field(default_factory=list)  # (start_line, end_line)
