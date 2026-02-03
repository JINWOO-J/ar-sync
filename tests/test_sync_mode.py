"""Tests for sync_mode feature.

Tests the sync_mode field in ProjectInfo and related CLI behavior:
- sync_mode field in metadata
- link command sets sync_mode to "link"
- pull/push commands warn when sync_mode is "link"
- --force flag overrides sync_mode warning
- Backward compatibility with metadata without sync_mode field
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from ar_sync.constants import SYNC_MODE_COPY, SYNC_MODE_LINK
from ar_sync.models import MachineInfo, ProjectInfo, StoreMetadata
from ar_sync.store_manager import StoreManager


@pytest.fixture
def temp_store_dir():
    """Create a temporary directory for store."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_metadata():
    """Create a sample StoreMetadata for testing."""
    return StoreMetadata(
        version=1,
        created_at="2025-01-21T10:00:00Z",
        projects={
            "test-project": ProjectInfo(
                added_at="2025-01-21T10:00:00Z",
                targets=[".cursor", ".kiro"],
                machines=[MachineInfo(hostname="test-machine", linked_at="2025-01-21T10:00:00Z")],
                sync_mode=SYNC_MODE_COPY,
            )
        },
    )


class TestSyncModeField:
    """Test suite for sync_mode field in ProjectInfo."""

    def test_project_info_default_sync_mode_is_copy(self):
        """Test that ProjectInfo defaults sync_mode to 'copy'."""
        project = ProjectInfo(added_at="2025-01-21T10:00:00Z", targets=[".cursor"])
        assert project.sync_mode == SYNC_MODE_COPY

    def test_project_info_accepts_link_sync_mode(self):
        """Test that ProjectInfo accepts 'link' sync_mode."""
        project = ProjectInfo(
            added_at="2025-01-21T10:00:00Z", targets=[".cursor"], sync_mode=SYNC_MODE_LINK
        )
        assert project.sync_mode == SYNC_MODE_LINK

    def test_save_includes_sync_mode_in_yaml(self, temp_store_dir, sample_metadata):
        """Test that save() includes sync_mode in YAML output."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        with open(manager.metadata_path) as f:
            data = yaml.safe_load(f)

        assert "sync_mode" in data["projects"]["test-project"]
        assert data["projects"]["test-project"]["sync_mode"] == SYNC_MODE_COPY

    def test_load_reads_sync_mode_from_yaml(self, temp_store_dir, sample_metadata):
        """Test that load() reads sync_mode from YAML."""
        manager = StoreManager(temp_store_dir)
        sample_metadata.projects["test-project"].sync_mode = SYNC_MODE_LINK
        manager.save(sample_metadata)

        manager2 = StoreManager(temp_store_dir)
        loaded = manager2.load()

        assert loaded.projects["test-project"].sync_mode == SYNC_MODE_LINK

    def test_load_defaults_sync_mode_when_missing(self, temp_store_dir):
        """Test backward compatibility: load() defaults sync_mode to 'copy' when missing."""
        # Create metadata file without sync_mode field (simulating old format)
        metadata_path = temp_store_dir / ".ar-sync.yaml"
        old_format_data = {
            "version": 1,
            "created_at": "2025-01-21T10:00:00Z",
            "projects": {
                "old-project": {
                    "added_at": "2025-01-21T10:00:00Z",
                    "targets": [".cursor"],
                    "machines": [{"hostname": "test-machine", "linked_at": "2025-01-21T10:00:00Z"}],
                    # Note: no sync_mode field
                }
            },
        }
        with open(metadata_path, "w") as f:
            yaml.safe_dump(old_format_data, f)

        manager = StoreManager(temp_store_dir)
        loaded = manager.load()

        # Should default to "copy" for backward compatibility
        assert loaded.projects["old-project"].sync_mode == SYNC_MODE_COPY


class TestAddProjectSyncMode:
    """Test suite for add_project() with sync_mode parameter."""

    def test_add_project_defaults_to_copy(self, temp_store_dir):
        """Test that add_project() defaults sync_mode to 'copy'."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("new-project", [".cursor"], "test-machine")

        project = manager.get_project("new-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_COPY

    def test_add_project_with_link_sync_mode(self, temp_store_dir):
        """Test that add_project() accepts 'link' sync_mode."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("new-project", [".cursor"], "test-machine", sync_mode=SYNC_MODE_LINK)

        project = manager.get_project("new-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_LINK

    def test_add_project_preserves_sync_mode_when_not_provided(self, temp_store_dir):
        """Test that add_project() preserves existing sync_mode when not provided."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("test-project", [".cursor"], "machine1", sync_mode=SYNC_MODE_LINK)

        # Update project without specifying sync_mode
        manager.add_project("test-project", [".cursor", ".kiro"], "machine2")

        project = manager.get_project("test-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_LINK  # Should be preserved

    def test_add_project_updates_sync_mode_when_provided(self, temp_store_dir):
        """Test that add_project() updates sync_mode when explicitly provided."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("test-project", [".cursor"], "machine1", sync_mode=SYNC_MODE_COPY)

        # Update project with new sync_mode
        manager.add_project("test-project", [".cursor"], "machine1", sync_mode=SYNC_MODE_LINK)

        project = manager.get_project("test-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_LINK


class TestUpdateSyncMode:
    """Test suite for update_sync_mode() method."""

    def test_update_sync_mode_changes_mode(self, temp_store_dir):
        """Test that update_sync_mode() changes the sync mode."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("test-project", [".cursor"], "test-machine")

        result = manager.update_sync_mode("test-project", SYNC_MODE_LINK)

        assert result is True
        project = manager.get_project("test-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_LINK

    def test_update_sync_mode_returns_false_for_nonexistent(self, temp_store_dir):
        """Test that update_sync_mode() returns False for non-existent project."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        result = manager.update_sync_mode("nonexistent", SYNC_MODE_LINK)

        assert result is False

    def test_update_sync_mode_persists_to_disk(self, temp_store_dir):
        """Test that update_sync_mode() persists changes to disk."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project("test-project", [".cursor"], "test-machine")
        manager.update_sync_mode("test-project", SYNC_MODE_LINK)

        # Load with new manager instance
        manager2 = StoreManager(temp_store_dir)
        project = manager2.get_project("test-project")

        assert project is not None
        assert project.sync_mode == SYNC_MODE_LINK
