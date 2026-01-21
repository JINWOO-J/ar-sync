"""Unit tests for StoreManager.

Tests the store metadata management including loading, saving,
initialization, and project operations.
"""

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from ar_sync.models import MachineInfo, ProjectInfo, StoreMetadata
from ar_sync.store_manager import StoreManager


@pytest.fixture
def temp_store_dir():
    """Create a temporary directory for store."""
    temp_dir = Path(tempfile.mkdtemp())

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_metadata():
    """Create a sample StoreMetadata for testing."""
    return StoreMetadata(
        version=1,
        created_at='2025-01-21T10:00:00Z',
        projects={
            'test-project': ProjectInfo(
                added_at='2025-01-21T10:00:00Z',
                targets=['.cursor', '.kiro'],
                machines=[
                    MachineInfo(hostname='test-machine', linked_at='2025-01-21T10:00:00Z')
                ]
            )
        }
    )


class TestStoreManager:
    """Test suite for StoreManager class."""

    def test_init_sets_paths(self, temp_store_dir):
        """Test that __init__ sets store_path and metadata_path correctly."""
        manager = StoreManager(temp_store_dir)

        assert manager.store_path == temp_store_dir
        assert manager.metadata_path == temp_store_dir / ".ar-sync.yaml"
        assert manager.metadata is None

    def test_initialize_creates_metadata_file(self, temp_store_dir):
        """Test that initialize() creates metadata file."""
        manager = StoreManager(temp_store_dir)

        # Act
        metadata = manager.initialize()

        # Assert
        assert manager.metadata_path.exists()
        assert manager.metadata_path.is_file()
        assert metadata.version == 1
        assert len(metadata.projects) == 0

    def test_initialize_sets_timestamp(self, temp_store_dir):
        """Test that initialize() sets created_at timestamp."""
        manager = StoreManager(temp_store_dir)

        # Act
        before = datetime.now(timezone.utc)
        metadata = manager.initialize()
        after = datetime.now(timezone.utc)

        # Assert
        assert metadata.created_at.endswith('Z')
        # Parse timestamp and verify it's between before and after
        timestamp = datetime.fromisoformat(metadata.created_at.rstrip('Z')).replace(tzinfo=timezone.utc)
        assert before <= timestamp <= after

    def test_save_creates_valid_yaml(self, temp_store_dir, sample_metadata):
        """Test that save() writes valid YAML content."""
        manager = StoreManager(temp_store_dir)

        # Act
        manager.save(sample_metadata)

        # Assert - read and parse YAML
        with open(manager.metadata_path) as f:
            data = yaml.safe_load(f)

        assert data['version'] == 1
        assert data['created_at'] == '2025-01-21T10:00:00Z'
        assert 'test-project' in data['projects']
        assert data['projects']['test-project']['targets'] == ['.cursor', '.kiro']

    def test_save_preserves_project_structure(self, temp_store_dir, sample_metadata):
        """Test that save() preserves complete project structure."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        # Act - read YAML
        with open(manager.metadata_path) as f:
            data = yaml.safe_load(f)

        # Assert
        project = data['projects']['test-project']
        assert project['added_at'] == '2025-01-21T10:00:00Z'
        assert project['targets'] == ['.cursor', '.kiro']
        assert len(project['machines']) == 1
        assert project['machines'][0]['hostname'] == 'test-machine'
        assert project['machines'][0]['linked_at'] == '2025-01-21T10:00:00Z'

    def test_load_reads_metadata_file(self, temp_store_dir, sample_metadata):
        """Test that load() reads metadata from disk."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        # Create new manager to test loading
        manager2 = StoreManager(temp_store_dir)

        # Act
        loaded_metadata = manager2.load()

        # Assert
        assert loaded_metadata.version == sample_metadata.version
        assert loaded_metadata.created_at == sample_metadata.created_at
        assert 'test-project' in loaded_metadata.projects

    def test_load_converts_to_dataclasses(self, temp_store_dir, sample_metadata):
        """Test that load() converts nested dicts to dataclasses."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        manager2 = StoreManager(temp_store_dir)

        # Act
        loaded_metadata = manager2.load()

        # Assert
        assert isinstance(loaded_metadata, StoreMetadata)
        project = loaded_metadata.projects['test-project']
        assert isinstance(project, ProjectInfo)
        assert isinstance(project.machines[0], MachineInfo)

    def test_load_raises_error_when_file_not_found(self, temp_store_dir):
        """Test that load() raises FileNotFoundError when metadata doesn't exist."""
        manager = StoreManager(temp_store_dir)

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            manager.load()

        assert "not found" in str(exc_info.value).lower()

    def test_add_project_creates_new_project(self, temp_store_dir):
        """Test that add_project() creates a new project entry."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act
        manager.add_project('new-project', ['.cursor'], 'test-machine')

        # Assert
        assert 'new-project' in manager.metadata.projects
        project = manager.metadata.projects['new-project']
        assert project.targets == ['.cursor']
        assert len(project.machines) == 1
        assert project.machines[0].hostname == 'test-machine'

    def test_add_project_updates_existing_project(self, temp_store_dir, sample_metadata):
        """Test that add_project() updates existing project."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)
        manager.load()

        # Act - update with different targets
        manager.add_project('test-project', ['.cursor', '.kiro', '.vscode'], 'test-machine')

        # Assert
        project = manager.metadata.projects['test-project']
        assert project.targets == ['.cursor', '.kiro', '.vscode']
        # Machine should still be there (not duplicated)
        assert len(project.machines) == 1

    def test_add_project_adds_new_machine(self, temp_store_dir, sample_metadata):
        """Test that add_project() adds new machine to existing project."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)
        manager.load()

        # Act - add from different machine
        manager.add_project('test-project', ['.cursor', '.kiro'], 'new-machine')

        # Assert
        project = manager.metadata.projects['test-project']
        assert len(project.machines) == 2
        hostnames = [m.hostname for m in project.machines]
        assert 'test-machine' in hostnames
        assert 'new-machine' in hostnames

    def test_add_project_does_not_duplicate_machine(self, temp_store_dir, sample_metadata):
        """Test that add_project() doesn't duplicate existing machine."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)
        manager.load()

        # Act - add from same machine again
        manager.add_project('test-project', ['.cursor'], 'test-machine')

        # Assert
        project = manager.metadata.projects['test-project']
        assert len(project.machines) == 1
        assert project.machines[0].hostname == 'test-machine'

    def test_add_project_persists_to_disk(self, temp_store_dir):
        """Test that add_project() saves changes to disk."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project('new-project', ['.cursor'], 'test-machine')

        # Create new manager and load
        manager2 = StoreManager(temp_store_dir)

        # Act
        loaded_metadata = manager2.load()

        # Assert
        assert 'new-project' in loaded_metadata.projects

    def test_get_project_returns_existing_project(self, temp_store_dir, sample_metadata):
        """Test that get_project() returns existing project."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        # Act
        project = manager.get_project('test-project')

        # Assert
        assert project is not None
        assert project.targets == ['.cursor', '.kiro']
        assert len(project.machines) == 1

    def test_get_project_returns_none_for_nonexistent(self, temp_store_dir, sample_metadata):
        """Test that get_project() returns None for non-existent project."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        # Act
        project = manager.get_project('nonexistent-project')

        # Assert
        assert project is None

    def test_get_project_loads_metadata_if_needed(self, temp_store_dir, sample_metadata):
        """Test that get_project() loads metadata if not already loaded."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        # Create new manager (metadata not loaded)
        manager2 = StoreManager(temp_store_dir)
        assert manager2.metadata is None

        # Act
        project = manager2.get_project('test-project')

        # Assert
        assert manager2.metadata is not None
        assert project is not None

    def test_save_updates_manager_metadata_attribute(self, temp_store_dir, sample_metadata):
        """Test that save() updates the manager's metadata attribute."""
        manager = StoreManager(temp_store_dir)
        assert manager.metadata is None

        # Act
        manager.save(sample_metadata)

        # Assert
        assert manager.metadata is not None
        assert manager.metadata.version == sample_metadata.version

    def test_load_updates_manager_metadata_attribute(self, temp_store_dir, sample_metadata):
        """Test that load() updates the manager's metadata attribute."""
        manager = StoreManager(temp_store_dir)
        manager.save(sample_metadata)

        manager2 = StoreManager(temp_store_dir)
        assert manager2.metadata is None

        # Act
        manager2.load()

        # Assert
        assert manager2.metadata is not None
        assert manager2.metadata.version == sample_metadata.version

    def test_atomic_write_uses_temp_file(self, temp_store_dir, sample_metadata):
        """Test that save() uses atomic write with temp file."""
        manager = StoreManager(temp_store_dir)

        # Act
        manager.save(sample_metadata)

        # Assert - temp file should not exist after successful write
        temp_path = manager.metadata_path.with_suffix('.tmp')
        assert not temp_path.exists()
        assert manager.metadata_path.exists()

    def test_initialize_returns_metadata(self, temp_store_dir):
        """Test that initialize() returns the created metadata."""
        manager = StoreManager(temp_store_dir)

        # Act
        metadata = manager.initialize()

        # Assert
        assert isinstance(metadata, StoreMetadata)
        assert metadata.version == 1
        assert isinstance(metadata.projects, dict)
        assert len(metadata.projects) == 0

    def test_add_project_sets_timestamp(self, temp_store_dir):
        """Test that add_project() sets added_at timestamp for new projects."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act
        before = datetime.now(timezone.utc)
        manager.add_project('new-project', ['.cursor'], 'test-machine')
        after = datetime.now(timezone.utc)

        # Assert
        project = manager.metadata.projects['new-project']
        assert project.added_at.endswith('Z')
        timestamp = datetime.fromisoformat(project.added_at.rstrip('Z')).replace(tzinfo=timezone.utc)
        assert before <= timestamp <= after
