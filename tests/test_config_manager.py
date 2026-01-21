"""Unit tests for ConfigManager.

Tests the configuration file management including loading, saving,
validation, and atomic write operations.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from ar_sync.config_manager import ConfigManager
from ar_sync.models import LocalConfig


@pytest.fixture
def temp_config_dir(monkeypatch):
    """Create a temporary directory for config files."""
    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / ".config" / "ar-sync" / "config.yaml"

    # Patch CONFIG_PATH to use temp directory
    monkeypatch.setattr(ConfigManager, 'CONFIG_PATH', config_path)

    yield config_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Create a sample LocalConfig for testing."""
    return LocalConfig(
        version=1,
        backend='git',
        store_path='/tmp/ar-sync-store',
        repo_url='git@github.com:user/repo.git',
        default_targets=['.cursor', '.kiro'],
        auto_sync=False,
        backup_originals=True,
        backup_dir='~/.config/ar-sync/backups/'
    )


class TestConfigManager:
    """Test suite for ConfigManager class."""

    def test_save_creates_config_file(self, temp_config_dir, sample_config):
        """Test that save() creates a configuration file."""
        manager = ConfigManager()

        # Act
        manager.save(sample_config)

        # Assert
        assert temp_config_dir.exists()
        assert temp_config_dir.is_file()

    def test_save_creates_parent_directories(self, temp_config_dir, sample_config):
        """Test that save() creates parent directories if they don't exist."""
        manager = ConfigManager()

        # Ensure parent doesn't exist
        assert not temp_config_dir.parent.exists()

        # Act
        manager.save(sample_config)

        # Assert
        assert temp_config_dir.parent.exists()
        assert temp_config_dir.exists()

    def test_save_writes_valid_yaml(self, temp_config_dir, sample_config):
        """Test that save() writes valid YAML content."""
        manager = ConfigManager()
        manager.save(sample_config)

        # Act - read and parse YAML
        with open(temp_config_dir) as f:
            data = yaml.safe_load(f)

        # Assert
        assert data['version'] == 1
        assert data['backend'] == 'git'
        assert data['store_path'] == '/tmp/ar-sync-store'
        assert data['repo_url'] == 'git@github.com:user/repo.git'
        assert data['default_targets'] == ['.cursor', '.kiro']

    def test_load_reads_config_file(self, temp_config_dir, sample_config):
        """Test that load() reads configuration from disk."""
        manager = ConfigManager()
        manager.save(sample_config)

        # Create new manager to test loading
        manager2 = ConfigManager()

        # Act
        loaded_config = manager2.load()

        # Assert
        assert loaded_config.version == sample_config.version
        assert loaded_config.backend == sample_config.backend
        assert loaded_config.store_path == sample_config.store_path
        assert loaded_config.repo_url == sample_config.repo_url
        assert loaded_config.default_targets == sample_config.default_targets

    def test_load_raises_error_when_file_not_found(self, temp_config_dir):
        """Test that load() raises FileNotFoundError when config doesn't exist."""
        manager = ConfigManager()

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            manager.load()

        assert "not found" in str(exc_info.value).lower()
        assert "ars setup" in str(exc_info.value)

    def test_validate_rejects_invalid_backend(self, sample_config):
        """Test that validate() rejects unsupported backend."""
        manager = ConfigManager()
        sample_config.backend = 'dropbox'

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(sample_config)

        assert "unsupported backend" in str(exc_info.value).lower()
        assert "dropbox" in str(exc_info.value)

    def test_validate_rejects_empty_backend(self, sample_config):
        """Test that validate() rejects empty backend."""
        manager = ConfigManager()
        sample_config.backend = ''

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(sample_config)

        assert "backend" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_validate_rejects_empty_store_path(self, sample_config):
        """Test that validate() rejects empty store_path."""
        manager = ConfigManager()
        sample_config.store_path = ''

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(sample_config)

        assert "store_path" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_validate_rejects_empty_repo_url(self, sample_config):
        """Test that validate() rejects empty repo_url."""
        manager = ConfigManager()
        sample_config.repo_url = ''

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(sample_config)

        assert "repo_url" in str(exc_info.value).lower()
        assert "required" in str(exc_info.value).lower()

    def test_validate_rejects_invalid_version(self, sample_config):
        """Test that validate() rejects unsupported version."""
        manager = ConfigManager()
        sample_config.version = 2

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.validate(sample_config)

        assert "version" in str(exc_info.value).lower()
        assert "2" in str(exc_info.value)

    def test_save_validates_before_writing(self, temp_config_dir, sample_config):
        """Test that save() validates configuration before writing."""
        manager = ConfigManager()
        sample_config.backend = 'invalid'

        # Act & Assert
        with pytest.raises(ValueError):
            manager.save(sample_config)

        # Config file should not be created
        assert not temp_config_dir.exists()

    def test_atomic_write_no_partial_file_on_error(self, temp_config_dir, sample_config, monkeypatch):
        """Test that atomic write doesn't leave partial files on error."""
        manager = ConfigManager()

        # Mock yaml.safe_dump to raise an error
        def mock_dump(*args, **kwargs):
            raise RuntimeError("Simulated write error")

        monkeypatch.setattr(yaml, 'safe_dump', mock_dump)

        # Act & Assert
        with pytest.raises(RuntimeError):
            manager.save(sample_config)

        # Neither config file nor temp file should exist
        assert not temp_config_dir.exists()
        temp_path = temp_config_dir.with_suffix('.tmp')
        assert not temp_path.exists()

    def test_load_validates_after_reading(self, temp_config_dir):
        """Test that load() validates configuration after reading."""
        # Create invalid config file manually
        temp_config_dir.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_dir, 'w') as f:
            yaml.safe_dump({
                'version': 1,
                'backend': 'invalid_backend',
                'store_path': '/tmp/store',
                'repo_url': 'git@github.com:user/repo.git',
                'default_targets': ['.cursor'],
                'auto_sync': False,
                'backup_originals': True,
                'backup_dir': '~/.config/ar-sync/backups/'
            }, f)

        manager = ConfigManager()

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            manager.load()

        assert "unsupported backend" in str(exc_info.value).lower()

    def test_save_updates_manager_config_attribute(self, temp_config_dir, sample_config):
        """Test that save() updates the manager's config attribute."""
        manager = ConfigManager()
        assert manager.config is None

        # Act
        manager.save(sample_config)

        # Assert
        assert manager.config is not None
        assert manager.config.backend == sample_config.backend

    def test_load_updates_manager_config_attribute(self, temp_config_dir, sample_config):
        """Test that load() updates the manager's config attribute."""
        manager = ConfigManager()
        manager.save(sample_config)

        manager2 = ConfigManager()
        assert manager2.config is None

        # Act
        manager2.load()

        # Assert
        assert manager2.config is not None
        assert manager2.config.backend == sample_config.backend
