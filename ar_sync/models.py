"""Data models for ar-sync configuration and metadata.

This module defines the core data structures used throughout ar-sync:
- LocalConfig: User's local configuration (~/.config/ar-sync/config.yaml)
- StoreMetadata: Store metadata ({store_path}/.ar-sync.yaml)
- ProjectInfo: Project information within store metadata
- MachineInfo: Machine information for project tracking
"""

from dataclasses import dataclass, field


@dataclass
class LocalConfig:
    """Local configuration for ar-sync CLI.

    Stored at ~/.config/ar-sync/config.yaml

    Attributes:
        version: Configuration file format version (currently 1)
        backend: Storage backend type ("git" or "local")
        store_path: Local filesystem path where store is located
        repo_url: Git repository URL (only for "git" backend, optional for "local")
        default_targets: List of default target directories to sync (e.g., [".cursor", ".kiro"])
        auto_sync: Whether to automatically sync after operations
        backup_originals: Whether to backup existing files before linking
        backup_dir: Directory path for storing backups
    """
    version: int
    backend: str
    store_path: str
    repo_url: str
    default_targets: list[str]
    auto_sync: bool
    backup_originals: bool
    backup_dir: str


@dataclass
class MachineInfo:
    """Information about a machine that has linked to a project.

    Attributes:
        hostname: Machine hostname identifier
        linked_at: ISO 8601 timestamp when machine linked to project
    """
    hostname: str
    linked_at: str


@dataclass
class ProjectInfo:
    """Information about a project in the store.

    Attributes:
        added_at: ISO 8601 timestamp when project was added
        targets: List of target directories synced for this project
        machines: List of machines that have linked to this project
    """
    added_at: str
    targets: list[str]
    machines: list[MachineInfo] = field(default_factory=list)


@dataclass
class StoreMetadata:
    """Store metadata for ar-sync.

    Stored at {store_path}/.ar-sync.yaml

    Attributes:
        version: Metadata file format version (currently 1)
        created_at: ISO 8601 timestamp when store was created
        projects: Dictionary mapping project names to ProjectInfo
    """
    version: int
    created_at: str
    projects: dict[str, ProjectInfo] = field(default_factory=dict)
