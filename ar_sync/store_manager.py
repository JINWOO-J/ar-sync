"""Store metadata management for ar-sync.

This module provides the StoreManager class for managing store metadata,
including loading, saving, initializing, and updating project information.
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml

from ar_sync.constants import SYNC_MODE_COPY
from ar_sync.models import MachineInfo, ProjectInfo, StoreMetadata


class StoreManager:
    """Manages store metadata operations.

    The StoreManager handles all operations related to the store metadata file
    ({store_path}/.ar-sync.yaml), including:
    - Loading and parsing metadata from disk
    - Saving metadata with atomic writes
    - Initializing new store metadata
    - Adding and updating project information
    - Querying project information

    Attributes:
        METADATA_FILENAME: Name of the metadata file (".ar-sync.yaml")
        store_path: Path to the store directory
        metadata_path: Full path to the metadata file
        metadata: Loaded StoreMetadata instance (None until loaded)
    """

    METADATA_FILENAME = ".ar-sync.yaml"

    def __init__(self, store_path: Path):
        """Initialize StoreManager with store path.

        Args:
            store_path: Path to the store directory
        """
        self.store_path = store_path
        self.metadata_path = store_path / self.METADATA_FILENAME
        self.metadata: StoreMetadata | None = None

    def load(self) -> StoreMetadata:
        """Load store metadata from disk.

        Reads the metadata file, parses YAML, and converts nested dictionaries
        to dataclass instances.

        Returns:
            StoreMetadata instance with loaded data

        Raises:
            FileNotFoundError: If metadata file does not exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Store metadata not found at {self.metadata_path}")

        with open(self.metadata_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Convert nested dicts to dataclasses
        projects = {}
        for name, proj_data in data.get("projects", {}).items():
            machines = [MachineInfo(**m) for m in proj_data.get("machines", [])]
            # Backward compatibility: default to "copy" if sync_mode not present
            sync_mode = proj_data.get("sync_mode", SYNC_MODE_COPY)
            projects[name] = ProjectInfo(
                added_at=proj_data["added_at"],
                targets=proj_data["targets"],
                machines=machines,
                sync_mode=sync_mode,
            )

        self.metadata = StoreMetadata(
            version=data["version"], created_at=data["created_at"], projects=projects
        )
        return self.metadata

    def save(self, metadata: StoreMetadata) -> None:
        """Save store metadata to disk with atomic write.

        Converts dataclass instances to dictionaries, writes to a temporary file,
        then atomically renames to the target file to prevent corruption.

        Args:
            metadata: StoreMetadata instance to save

        Raises:
            OSError: If file operations fail
            yaml.YAMLError: If YAML serialization fails
        """
        # Convert dataclasses to dicts
        from typing import Any

        data: dict[str, Any] = {
            "version": metadata.version,
            "created_at": metadata.created_at,
            "projects": {},
        }

        for name, proj in metadata.projects.items():
            data["projects"][name] = {
                "added_at": proj.added_at,
                "targets": proj.targets,
                "machines": [
                    {"hostname": m.hostname, "linked_at": m.linked_at} for m in proj.machines
                ],
                "sync_mode": proj.sync_mode,
            }

        # Atomic write: write to temp file then rename
        temp_path = self.metadata_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        temp_path.replace(self.metadata_path)
        self.metadata = metadata

    def initialize(self) -> StoreMetadata:
        """Create initial store metadata.

        Creates a new StoreMetadata instance with version 1, current timestamp,
        and empty projects dictionary, then saves it to disk.

        Returns:
            Newly created StoreMetadata instance

        Raises:
            OSError: If file operations fail
        """
        metadata = StoreMetadata(
            version=1,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            projects={},
        )
        self.save(metadata)
        return metadata

    def add_project(
        self, name: str, targets: list[str], hostname: str, sync_mode: str | None = None
    ) -> None:
        """Add or update project in metadata.

        If the project already exists, updates its targets and adds the machine
        if not already present. If the project is new, creates a new entry.

        Args:
            name: Project name (identifier)
            targets: List of target directories for this project
            hostname: Current machine hostname
            sync_mode: Sync mode ("copy" or "link"). If None, preserves existing or defaults to "copy"

        Raises:
            FileNotFoundError: If metadata not loaded and file doesn't exist
        """
        if self.metadata is None:
            self.load()

        # After load(), metadata is guaranteed to be non-None
        assert self.metadata is not None

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if name in self.metadata.projects:
            # Update existing project
            project = self.metadata.projects[name]
            project.targets = targets
            # Update sync_mode only if explicitly provided
            if sync_mode is not None:
                project.sync_mode = sync_mode
            # Add machine if not already present
            if not any(m.hostname == hostname for m in project.machines):
                project.machines.append(MachineInfo(hostname=hostname, linked_at=now))
        else:
            # Create new project
            self.metadata.projects[name] = ProjectInfo(
                added_at=now,
                targets=targets,
                machines=[MachineInfo(hostname=hostname, linked_at=now)],
                sync_mode=sync_mode if sync_mode is not None else SYNC_MODE_COPY,
            )

        self.save(self.metadata)

    def get_project(self, name: str) -> ProjectInfo | None:
        """Get project info by name.

        Args:
            name: Project name to look up

        Returns:
            ProjectInfo instance if found, None otherwise

        Raises:
            FileNotFoundError: If metadata not loaded and file doesn't exist
        """
        if self.metadata is None:
            self.load()

        # After load(), metadata is guaranteed to be non-None
        assert self.metadata is not None

        return self.metadata.projects.get(name)

    def update_sync_mode(self, name: str, sync_mode: str) -> bool:
        """Update sync mode for a project.

        Args:
            name: Project name to update
            sync_mode: New sync mode ("copy" or "link")

        Returns:
            True if project was updated, False if project not found

        Raises:
            FileNotFoundError: If metadata not loaded and file doesn't exist
        """
        if self.metadata is None:
            self.load()

        assert self.metadata is not None

        if name not in self.metadata.projects:
            return False

        self.metadata.projects[name].sync_mode = sync_mode
        self.save(self.metadata)
        return True

    def scan_store_targets(self, project_name: str) -> list[str]:
        """Scan store directory to find actual target files/directories.

        Args:
            project_name: Project name to scan

        Returns:
            List of target names found in store (e.g., [".cursor", ".kiro", "AGENTS.md"])
        """
        project_dir = self.store_path / project_name
        if not project_dir.exists():
            return []

        targets = []
        for item in project_dir.iterdir():
            if item.name.startswith(".") or item.is_file():
                targets.append(item.name)

        return sorted(targets)

    def sync_metadata_with_store(self, project_name: str) -> bool:
        """Synchronize metadata with actual files in store.

        Updates the project's targets in metadata to match what's actually
        in the store directory.

        Args:
            project_name: Project name to synchronize

        Returns:
            True if metadata was updated, False if no changes needed
        """
        if self.metadata is None:
            self.load()

        assert self.metadata is not None

        if project_name not in self.metadata.projects:
            return False

        actual_targets = self.scan_store_targets(project_name)
        project = self.metadata.projects[project_name]

        if set(actual_targets) != set(project.targets):
            project.targets = actual_targets
            self.save(self.metadata)
            return True

        return False

    def remove_project(self, name: str) -> None:
        """Remove project from metadata.

        Args:
            name: Project name to remove

        Raises:
            ValueError: If project not found in metadata
            FileNotFoundError: If metadata not loaded and file doesn't exist
        """
        if self.metadata is None:
            self.load()

        assert self.metadata is not None

        if name not in self.metadata.projects:
            raise ValueError(f"Project '{name}' not found in store metadata")

        del self.metadata.projects[name]
        self.save(self.metadata)
