"""Property-based tests for StoreManager.

Tests universal properties that should hold for all valid inputs:
- Property 5: Store Metadata initialization
- Property 9: Project update
- Property 10: Metadata update

Uses Hypothesis library with minimum 100 iterations per test.
"""

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ar_sync.models import MachineInfo, ProjectInfo, StoreMetadata
from ar_sync.store_manager import StoreManager


# Hypothesis strategies for generating test data
@st.composite
def valid_project_name_strategy(draw):
    """Generate valid project names."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=30
    ).filter(lambda x: x.strip() and not x.startswith('.')))


@st.composite
def valid_targets_strategy(draw):
    """Generate valid target lists."""
    return draw(st.lists(
        st.sampled_from(['.cursor', '.kiro', '.vscode', '.idea']),
        min_size=1,
        max_size=4,
        unique=True
    ))


@st.composite
def valid_hostname_strategy(draw):
    """Generate valid hostnames."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip()))


@st.composite
def valid_store_metadata_strategy(draw):
    """Generate valid StoreMetadata objects with projects."""
    num_projects = draw(st.integers(min_value=0, max_value=5))
    projects = {}

    for _ in range(num_projects):
        project_name = draw(valid_project_name_strategy())
        targets = draw(valid_targets_strategy())
        num_machines = draw(st.integers(min_value=1, max_value=3))
        machines = []

        for _ in range(num_machines):
            hostname = draw(valid_hostname_strategy())
            linked_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            machines.append(MachineInfo(hostname=hostname, linked_at=linked_at))

        added_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        projects[project_name] = ProjectInfo(
            added_at=added_at,
            targets=targets,
            machines=machines
        )

    return StoreMetadata(
        version=1,
        created_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        projects=projects
    )


@pytest.fixture
def temp_store_dir():
    """Create a temporary directory for store."""
    temp_dir = Path(tempfile.mkdtemp())

    yield temp_dir

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestStoreManagerProperties:
    """Property-based tests for StoreManager."""

    # Feature: cli-core-mvp, Property 5: Store Metadata 초기화
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(dummy=st.just(None))
    def test_property_5_store_metadata_initialization(self, temp_store_dir, dummy):
        """
        Property 5: Store Metadata 초기화

        For any Git repository initialization, the {store_path}/.ar-sync.yaml
        file should be created with version 1, creation timestamp, and empty
        projects dictionary.

        Validates: Requirements 1.6, 1.7
        """
        # Arrange
        manager = StoreManager(temp_store_dir)

        # Act
        before = datetime.now(timezone.utc)
        metadata = manager.initialize()
        after = datetime.now(timezone.utc)

        # Assert - metadata file exists
        assert manager.metadata_path.exists(), "Metadata file should be created"
        assert manager.metadata_path.is_file(), "Metadata path should be a file"

        # Assert - version is 1
        assert metadata.version == 1, "Metadata version should be 1"

        # Assert - created_at timestamp is set and valid
        assert metadata.created_at.endswith('Z'), "Timestamp should be in UTC (end with Z)"
        timestamp = datetime.fromisoformat(metadata.created_at.rstrip('Z')).replace(tzinfo=timezone.utc)
        assert before <= timestamp <= after, "Timestamp should be within test execution time"

        # Assert - projects dictionary is empty
        assert isinstance(metadata.projects, dict), "Projects should be a dictionary"
        assert len(metadata.projects) == 0, "Projects dictionary should be empty"

        # Assert - file contains valid YAML
        with open(manager.metadata_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert data['version'] == 1
        assert 'created_at' in data
        assert data['projects'] == {}

    # Feature: cli-core-mvp, Property 9: 프로젝트 업데이트
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        initial_targets=valid_targets_strategy(),
        updated_targets=valid_targets_strategy(),
        hostname=valid_hostname_strategy()
    )
    def test_property_9_project_update(
        self, temp_store_dir, project_name, initial_targets, updated_targets, hostname
    ):
        """
        Property 9: 프로젝트 업데이트

        For any project name that already exists in Store_Metadata, the add
        command should update the existing entry (not create a duplicate).

        Validates: Requirements 2.4
        """
        # Arrange - initialize and add project
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project(project_name, initial_targets, hostname)

        # Verify initial state
        initial_metadata = manager.metadata
        assert project_name in initial_metadata.projects
        initial_project = initial_metadata.projects[project_name]
        assert initial_project.targets == initial_targets

        # Act - update the same project with different targets
        manager.add_project(project_name, updated_targets, hostname)

        # Assert - project still exists (not duplicated)
        assert project_name in manager.metadata.projects, "Project should still exist"

        # Assert - only one project with this name
        project_count = sum(1 for name in manager.metadata.projects.keys() if name == project_name)
        assert project_count == 1, "Should have exactly one project with this name"

        # Assert - targets are updated
        updated_project = manager.metadata.projects[project_name]
        assert updated_project.targets == updated_targets, "Targets should be updated"

        # Assert - added_at timestamp is preserved (not changed)
        assert updated_project.added_at == initial_project.added_at, \
            "Original added_at timestamp should be preserved"

        # Assert - machine is not duplicated
        hostnames = [m.hostname for m in updated_project.machines]
        assert hostnames.count(hostname) == 1, "Machine should not be duplicated"

    # Feature: cli-core-mvp, Property 9: 프로젝트 업데이트 (new machine)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        targets=valid_targets_strategy(),
        hostname1=valid_hostname_strategy(),
        hostname2=valid_hostname_strategy()
    )
    def test_property_9_project_update_adds_new_machine(
        self, temp_store_dir, project_name, targets, hostname1, hostname2
    ):
        """
        Property 9: 프로젝트 업데이트 (new machine)

        For any project update from a different machine, the system should
        add the new machine to the machines list without duplicating the project.

        Validates: Requirements 2.4
        """
        # Skip if hostnames are the same (would be idempotent case)
        if hostname1 == hostname2:
            return

        # Arrange - initialize and add project from first machine
        manager = StoreManager(temp_store_dir)
        manager.initialize()
        manager.add_project(project_name, targets, hostname1)

        # Act - update from second machine
        manager.add_project(project_name, targets, hostname2)

        # Assert - project exists once
        assert project_name in manager.metadata.projects
        project = manager.metadata.projects[project_name]

        # Assert - both machines are in the list
        hostnames = [m.hostname for m in project.machines]
        assert hostname1 in hostnames, "First machine should be in list"
        assert hostname2 in hostnames, "Second machine should be in list"

        # Assert - exactly 2 machines (no duplicates)
        assert len(project.machines) == 2, "Should have exactly 2 machines"

    # Feature: cli-core-mvp, Property 10: Metadata 업데이트
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        targets=valid_targets_strategy(),
        hostname=valid_hostname_strategy()
    )
    def test_property_10_metadata_update(
        self, temp_store_dir, project_name, targets, hostname
    ):
        """
        Property 10: Metadata 업데이트

        For any project addition, Store_Metadata should be updated with:
        - Project name
        - added_at timestamp
        - targets list
        - current Machine information

        Validates: Requirements 2.5
        """
        # Arrange
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act
        before = datetime.now(timezone.utc)
        manager.add_project(project_name, targets, hostname)
        after = datetime.now(timezone.utc)

        # Assert - project exists in metadata
        assert project_name in manager.metadata.projects, "Project should be in metadata"
        project = manager.metadata.projects[project_name]

        # Assert - project name is correct
        assert project_name in manager.metadata.projects.keys()

        # Assert - added_at timestamp is set and valid
        assert project.added_at.endswith('Z'), "Timestamp should be in UTC"
        timestamp = datetime.fromisoformat(project.added_at.rstrip('Z')).replace(tzinfo=timezone.utc)
        assert before <= timestamp <= after, "Timestamp should be within test execution time"

        # Assert - targets list is correct
        assert project.targets == targets, "Targets should match input"
        assert isinstance(project.targets, list), "Targets should be a list"

        # Assert - machine information is present
        assert len(project.machines) > 0, "Should have at least one machine"
        machine = project.machines[0]
        assert machine.hostname == hostname, "Machine hostname should match"
        assert machine.linked_at.endswith('Z'), "Machine linked_at should be in UTC"

        # Assert - changes are persisted to disk
        manager2 = StoreManager(temp_store_dir)
        loaded_metadata = manager2.load()
        assert project_name in loaded_metadata.projects, "Project should be persisted to disk"

    # Feature: cli-core-mvp, Property 10: Metadata 업데이트 (persistence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        targets=valid_targets_strategy(),
        hostname=valid_hostname_strategy()
    )
    def test_property_10_metadata_update_persists_to_disk(
        self, temp_store_dir, project_name, targets, hostname
    ):
        """
        Property 10: Metadata 업데이트 (persistence)

        For any metadata update, changes should be persisted to disk
        immediately and be loadable by a new manager instance.

        Validates: Requirements 2.5
        """
        # Arrange
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act
        manager.add_project(project_name, targets, hostname)

        # Create a new manager instance and load
        manager2 = StoreManager(temp_store_dir)
        loaded_metadata = manager2.load()

        # Assert - project exists in loaded metadata
        assert project_name in loaded_metadata.projects
        loaded_project = loaded_metadata.projects[project_name]

        # Assert - all fields match
        assert loaded_project.targets == targets
        assert len(loaded_project.machines) == 1
        assert loaded_project.machines[0].hostname == hostname

    # Feature: cli-core-mvp, Property 5: Store Metadata 초기화 (atomic write)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(dummy=st.just(None))
    def test_property_5_initialization_atomic_write(self, temp_store_dir, dummy):
        """
        Property 5: Store Metadata 초기화 (atomic write)

        For any metadata initialization, the system should use atomic writes
        to prevent corruption.

        Validates: Requirements 1.6, 1.7
        """
        # Arrange
        manager = StoreManager(temp_store_dir)

        # Act
        manager.initialize()

        # Assert - metadata file exists
        assert manager.metadata_path.exists()

        # Assert - temp file does not exist (atomic rename completed)
        temp_path = manager.metadata_path.with_suffix('.tmp')
        assert not temp_path.exists(), "Temporary file should not exist after successful write"

        # Assert - file is valid and complete
        with open(manager.metadata_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert data is not None
        assert 'version' in data
        assert 'created_at' in data
        assert 'projects' in data

    # Feature: cli-core-mvp, Property 10: Metadata 업데이트 (YAML structure)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        targets=valid_targets_strategy(),
        hostname=valid_hostname_strategy()
    )
    def test_property_10_metadata_update_yaml_structure(
        self, temp_store_dir, project_name, targets, hostname
    ):
        """
        Property 10: Metadata 업데이트 (YAML structure)

        For any metadata update, the saved YAML file should have the correct
        structure with all required fields.

        Validates: Requirements 2.5
        """
        # Arrange
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act
        manager.add_project(project_name, targets, hostname)

        # Assert - read YAML file directly
        with open(manager.metadata_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Assert - top-level structure
        assert 'version' in data
        assert 'created_at' in data
        assert 'projects' in data

        # Assert - project structure
        assert project_name in data['projects']
        project_data = data['projects'][project_name]

        assert 'added_at' in project_data
        assert 'targets' in project_data
        assert 'machines' in project_data

        # Assert - project data values
        assert project_data['targets'] == targets
        assert len(project_data['machines']) == 1
        assert project_data['machines'][0]['hostname'] == hostname
        assert 'linked_at' in project_data['machines'][0]

    # Feature: cli-core-mvp, Property 9: 프로젝트 업데이트 (idempotent)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        project_name=valid_project_name_strategy(),
        targets=valid_targets_strategy(),
        hostname=valid_hostname_strategy()
    )
    def test_property_9_project_update_idempotent(
        self, temp_store_dir, project_name, targets, hostname
    ):
        """
        Property 9: 프로젝트 업데이트 (idempotent)

        For any project update with the same machine and targets, the operation
        should be idempotent (no duplicate machines, same result).

        Validates: Requirements 2.4
        """
        # Arrange
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Act - add project multiple times with same parameters
        manager.add_project(project_name, targets, hostname)
        manager.add_project(project_name, targets, hostname)
        manager.add_project(project_name, targets, hostname)

        # Assert - project exists once
        assert project_name in manager.metadata.projects
        project = manager.metadata.projects[project_name]

        # Assert - targets are correct
        assert project.targets == targets

        # Assert - machine appears only once
        hostnames = [m.hostname for m in project.machines]
        assert hostnames.count(hostname) == 1, "Machine should appear exactly once"
        assert len(project.machines) == 1, "Should have exactly one machine"

    # Feature: cli-core-mvp, Property 5: Store Metadata 초기화 (round-trip)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(dummy=st.just(None))
    def test_property_5_initialization_round_trip(self, temp_store_dir, dummy):
        """
        Property 5: Store Metadata 초기화 (round-trip)

        For any metadata initialization, saving and then loading should
        preserve all field values exactly.

        Validates: Requirements 1.6, 1.7
        """
        # Arrange
        manager = StoreManager(temp_store_dir)

        # Act - initialize then load
        original_metadata = manager.initialize()

        manager2 = StoreManager(temp_store_dir)
        loaded_metadata = manager2.load()

        # Assert - all fields match
        assert loaded_metadata.version == original_metadata.version
        assert loaded_metadata.created_at == original_metadata.created_at
        assert len(loaded_metadata.projects) == len(original_metadata.projects)
        assert loaded_metadata.projects == original_metadata.projects
