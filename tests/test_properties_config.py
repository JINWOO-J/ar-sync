"""Property-based tests for ConfigManager.

Tests universal properties that should hold for all valid inputs:
- Property 1: Config file creation and required fields
- Property 26: YAML validation
- Property 27: Required field validation
- Property 31: Atomic write operations

Uses Hypothesis library with minimum 100 iterations per test.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ar_sync.config_manager import ConfigManager
from ar_sync.models import LocalConfig


# Hypothesis strategies for generating test data
@st.composite
def valid_backend_strategy(draw):
    """Generate valid backend values ('git' or 'local')."""
    return draw(st.sampled_from(['git', 'local']))


@st.composite
def valid_store_path_strategy(draw):
    """Generate valid store path strings."""
    # Generate simple alphanumeric paths to avoid filesystem issues
    path_component = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=20
    ))
    return f"/tmp/ar-sync-test-{path_component}"


@st.composite
def valid_repo_url_strategy(draw):
    """Generate valid Git repository URLs."""
    username = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=20
    ))
    repo = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=20
    ))
    return f"git@github.com:{username}/{repo}.git"


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
def valid_local_config_strategy(draw):
    """Generate valid LocalConfig objects."""
    return LocalConfig(
        version=1,
        backend=draw(valid_backend_strategy()),
        store_path=draw(valid_store_path_strategy()),
        repo_url=draw(valid_repo_url_strategy()),
        default_targets=draw(valid_targets_strategy()),
        auto_sync=draw(st.booleans()),
        backup_originals=draw(st.booleans()),
        backup_dir=draw(st.just('~/.config/ar-sync/backups/'))
    )


@pytest.fixture
def temp_config_dir(monkeypatch):
    """Create a temporary directory for config files."""
    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / ".config" / "ar-sync" / "config.yaml"

    # Patch CONFIG_PATH to use temp directory
    monkeypatch.setattr(ConfigManager, 'CONFIG_PATH', config_path)

    yield config_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestConfigManagerProperties:
    """Property-based tests for ConfigManager."""

    # Feature: cli-core-mvp, Property 1: Config 파일 생성 및 필수 필드
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config=valid_local_config_strategy())
    def test_property_1_config_file_creation_and_required_fields(
        self, temp_config_dir, config
    ):
        """
        Property 1: Config 파일 생성 및 필수 필드

        For any valid backend and path input, after executing save(),
        the config file should be created at ~/.config/ar-sync/config.yaml
        and contain backend, store_path, and repo_url fields.

        Validates: Requirements 1.1, 1.2
        """
        # Arrange
        manager = ConfigManager()

        # Act
        manager.save(config)

        # Assert - file exists
        assert temp_config_dir.exists(), "Config file should be created"
        assert temp_config_dir.is_file(), "Config path should be a file"

        # Assert - file contains valid YAML
        with open(temp_config_dir, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Assert - required fields exist
        assert 'backend' in data, "Config must contain 'backend' field"
        assert 'store_path' in data, "Config must contain 'store_path' field"
        assert 'repo_url' in data, "Config must contain 'repo_url' field"

        # Assert - field values match
        assert data['backend'] == config.backend
        assert data['store_path'] == config.store_path
        assert data['repo_url'] == config.repo_url

    # Feature: cli-core-mvp, Property 26: YAML 검증
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config=valid_local_config_strategy())
    def test_property_26_yaml_validation(self, temp_config_dir, config):
        """
        Property 26: YAML 검증

        For any config file creation or update, the system should validate
        YAML syntax before writing.

        Validates: Requirements 6.1, 6.2
        """
        # Arrange
        manager = ConfigManager()

        # Act
        manager.save(config)

        # Assert - file contains valid YAML that can be parsed
        with open(temp_config_dir, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Assert - data is a dictionary (valid YAML structure)
        assert isinstance(data, dict), "Config file should contain valid YAML dictionary"

        # Assert - all expected fields are present and have correct types
        assert isinstance(data['version'], int)
        assert isinstance(data['backend'], str)
        assert isinstance(data['store_path'], str)
        assert isinstance(data['repo_url'], str)
        assert isinstance(data['default_targets'], list)
        assert isinstance(data['auto_sync'], bool)
        assert isinstance(data['backup_originals'], bool)
        assert isinstance(data['backup_dir'], str)

    # Feature: cli-core-mvp, Property 27: 필수 필드 검증
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config=valid_local_config_strategy())
    def test_property_27_required_field_validation(self, temp_config_dir, config):
        """
        Property 27: 필수 필드 검증

        For any LocalConfig read operation, the system should verify that
        backend, store_path, and repo_url fields exist.

        Validates: Requirements 6.3
        """
        # Arrange
        manager = ConfigManager()
        manager.save(config)

        # Act
        loaded_config = manager.load()

        # Assert - required fields are present and not empty
        assert loaded_config.backend, "backend field must be present and non-empty"
        assert loaded_config.store_path, "store_path field must be present and non-empty"
        assert loaded_config.repo_url, "repo_url field must be present and non-empty"

        # Assert - fields match original values
        assert loaded_config.backend == config.backend
        assert loaded_config.store_path == config.store_path
        assert loaded_config.repo_url == config.repo_url

    # Feature: cli-core-mvp, Property 27: 필수 필드 검증 (invalid backend)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        backend=st.text(min_size=1, max_size=20).filter(lambda x: x not in ['git', 'local']),
        store_path=valid_store_path_strategy(),
        repo_url=valid_repo_url_strategy()
    )
    def test_property_27_invalid_backend_rejected(
        self, temp_config_dir, backend, store_path, repo_url
    ):
        """
        Property 27: 필수 필드 검증 (invalid backend)

        For any backend value that is not 'github', the system should
        reject the configuration with a validation error.

        Validates: Requirements 6.3
        """
        # Arrange
        manager = ConfigManager()
        invalid_config = LocalConfig(
            version=1,
            backend=backend,
            store_path=store_path,
            repo_url=repo_url,
            default_targets=['.cursor', '.kiro'],
            auto_sync=False,
            backup_originals=True,
            backup_dir='~/.config/ar-sync/backups/'
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(invalid_config)

        assert 'backend' in str(exc_info.value).lower()

    # Feature: cli-core-mvp, Property 27: 필수 필드 검증 (empty fields)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        field_to_empty=st.sampled_from(['backend', 'store_path', 'repo_url'])
    )
    def test_property_27_empty_required_fields_rejected(
        self, temp_config_dir, field_to_empty
    ):
        """
        Property 27: 필수 필드 검증 (empty fields)

        For any required field that is empty, the system should reject
        the configuration with a validation error.

        Validates: Requirements 6.3
        """
        # Arrange
        manager = ConfigManager()
        config = LocalConfig(
            version=1,
            backend='git',
            store_path='/tmp/store',
            repo_url='git@github.com:user/repo.git',
            default_targets=['.cursor', '.kiro'],
            auto_sync=False,
            backup_originals=True,
            backup_dir='~/.config/ar-sync/backups/'
        )

        # Set the specified field to empty
        setattr(config, field_to_empty, '')

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(config)

        assert field_to_empty in str(exc_info.value).lower()
        assert 'required' in str(exc_info.value).lower()

    # Feature: cli-core-mvp, Property 31: Atomic Write
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config=valid_local_config_strategy())
    def test_property_31_atomic_write(self, temp_config_dir, config):
        """
        Property 31: Atomic Write

        For any config file write operation, the system should ensure
        atomic writes to prevent corruption.

        This means:
        1. Write to a temporary file first
        2. Only replace the original file if write succeeds
        3. No partial files left on error

        Validates: Requirements 6.7
        """
        # Arrange
        manager = ConfigManager()

        # Act
        manager.save(config)

        # Assert - config file exists and is complete
        assert temp_config_dir.exists()

        # Assert - temp file does not exist (atomic rename completed)
        temp_path = temp_config_dir.with_suffix('.tmp')
        assert not temp_path.exists(), "Temporary file should not exist after successful write"

        # Assert - file is valid and complete
        with open(temp_config_dir, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        assert data is not None
        assert 'backend' in data
        assert 'store_path' in data
        assert 'repo_url' in data

    # Feature: cli-core-mvp, Property 31: Atomic Write (error handling)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(config=valid_local_config_strategy())
    def test_property_31_atomic_write_no_partial_on_error(
        self, temp_config_dir, config, monkeypatch
    ):
        """
        Property 31: Atomic Write (error handling)

        For any write operation that fails, the system should not leave
        partial or corrupted files.

        Validates: Requirements 6.7
        """
        # Arrange
        manager = ConfigManager()

        # Mock yaml.safe_dump to simulate write error
        original_dump = yaml.safe_dump
        call_count = [0]

        def mock_dump(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # Fail on first call
                raise RuntimeError("Simulated write error")
            return original_dump(*args, **kwargs)

        monkeypatch.setattr(yaml, 'safe_dump', mock_dump)

        # Act & Assert
        with pytest.raises(RuntimeError):
            manager.save(config)

        # Assert - neither config file nor temp file should exist
        assert not temp_config_dir.exists(), "Config file should not exist after failed write"
        temp_path = temp_config_dir.with_suffix('.tmp')
        assert not temp_path.exists(), "Temp file should be cleaned up after failed write"

    # Feature: cli-core-mvp, Property 1: Config 파일 생성 및 필수 필드 (round-trip)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    @given(config=valid_local_config_strategy())
    def test_property_1_round_trip_preserves_data(self, temp_config_dir, config):
        """
        Property 1: Config 파일 생성 및 필수 필드 (round-trip)

        For any valid config, saving and then loading should preserve
        all field values exactly.

        Validates: Requirements 1.1, 1.2
        """
        # Arrange
        manager = ConfigManager()

        # Act - save then load
        manager.save(config)
        loaded_config = manager.load()

        # Assert - all fields match
        assert loaded_config.version == config.version
        assert loaded_config.backend == config.backend
        assert loaded_config.store_path == config.store_path
        assert loaded_config.repo_url == config.repo_url
        assert loaded_config.default_targets == config.default_targets
        assert loaded_config.auto_sync == config.auto_sync
        assert loaded_config.backup_originals == config.backup_originals
        assert loaded_config.backup_dir == config.backup_dir
