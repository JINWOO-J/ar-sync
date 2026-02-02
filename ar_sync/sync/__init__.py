"""
ar_sync.sync - Bidirectional Synchronization Module

This module provides bidirectional synchronization between Project, Store, and Remote.
It includes diff detection, merge capabilities, and conflict resolution.

Components:
- DiffEngine: File comparison using git diff --no-index
- MergeEngine: 3-way merge using git merge-file
- ConflictResolver: Interactive and automatic conflict resolution
- BidirectionalSync: Main orchestrator for sync operations
"""

# Data Models (always available)
from ar_sync.sync.models import (
    ChangeType,
    FileChange,
    MergeResult,
    Resolution,
    ResolutionStrategy,
    ResolvedChange,
    SyncOptions,
    SyncResult,
)

__all__ = [
    # Enums
    "ChangeType",
    "Resolution",
    "ResolutionStrategy",
    # Data Models
    "SyncOptions",
    "FileChange",
    "ResolvedChange",
    "SyncResult",
    "MergeResult",
]

# Conditional imports for modules that may not exist yet
try:
    from ar_sync.sync.diff_engine import DiffEngine  # noqa: F401
    __all__.append("DiffEngine")
except ImportError:
    pass

try:
    from ar_sync.sync.merge_engine import MergeEngine  # noqa: F401
    __all__.append("MergeEngine")
except ImportError:
    pass

try:
    from ar_sync.sync.conflict_resolver import ConflictResolver  # noqa: F401
    __all__.append("ConflictResolver")
except ImportError:
    pass

try:
    from ar_sync.sync.bidirectional_sync import BidirectionalSync  # noqa: F401
    __all__.append("BidirectionalSync")
except ImportError:
    pass

try:
    from ar_sync.sync.atomic_ops import AtomicFileOperation  # noqa: F401
    __all__.append("AtomicFileOperation")
except ImportError:
    pass
