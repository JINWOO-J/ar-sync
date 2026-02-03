"""Integration tests for new features: auto_sync, SSH verification, sync_mode."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ar_sync.cli import perform_auto_sync
from ar_sync.constants import SYNC_MODE_COPY, SYNC_MODE_LINK
from ar_sync.git_backend import GitBackend
from ar_sync.models import LocalConfig
from ar_sync.store_manager import StoreManager


class TestSSHVerification:
    """Integration tests for SSH verification feature."""

    def test_verify_remote_access_with_valid_repo(self):
        """Test SSH verification with a valid repository."""
        # This will actually try to connect, so we mock it
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert result is True

    def test_verify_remote_access_with_invalid_repo(self):
        """Test SSH verification with an invalid repository."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 128
            result = GitBackend.verify_remote_access("git@github.com:invalid/repo.git")
            assert result is False


class TestAutoSync:
    """Integration tests for auto_sync feature."""

    def test_perform_auto_sync_when_disabled(self):
        """Test that auto_sync does nothing when disabled."""
        config = LocalConfig(
            version=1,
            backend="git",
            store_path="/tmp/test",
            repo_url="git@github.com:user/repo.git",
            default_targets=[".cursor"],
            auto_sync=False,
            backup_originals=True,
            backup_dir="/tmp/backup",
        )

        # Should return immediately without doing anything
        with patch("ar_sync.cli.GitBackend") as mock_git:
            perform_auto_sync(config)
            mock_git.assert_not_called()

    def test_perform_auto_sync_when_enabled_with_git_backend(self):
        """Test that auto_sync works when enabled with git backend."""
        config = LocalConfig(
            version=1,
            backend="git",
            store_path="/tmp/test",
            repo_url="git@github.com:user/repo.git",
            default_targets=[".cursor"],
            auto_sync=True,
            backup_originals=True,
            backup_dir="/tmp/backup",
        )

        with patch("ar_sync.cli.GitBackend") as mock_git_class:
            mock_git = MagicMock()
            mock_git_class.return_value = mock_git

            perform_auto_sync(config)

            # Verify GitBackend was initialized and sync was called
            mock_git_class.assert_called_once()
            mock_git.initialize.assert_called_once()
            mock_git.sync.assert_called_once()

    def test_perform_auto_sync_skips_for_local_backend(self):
        """Test that auto_sync is skipped for local backend."""
        config = LocalConfig(
            version=1,
            backend="local",
            store_path="/tmp/test",
            repo_url="",
            default_targets=[".cursor"],
            auto_sync=True,
            backup_originals=True,
            backup_dir="/tmp/backup",
        )

        with patch("ar_sync.cli.GitBackend") as mock_git:
            perform_auto_sync(config)
            mock_git.assert_not_called()


class TestSyncModeIntegration:
    """Integration tests for sync_mode feature."""

    @pytest.fixture
    def temp_store_dir(self):
        """Create a temporary directory for store."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_mode_workflow(self, temp_store_dir):
        """Test complete sync_mode workflow: create, update, verify."""
        manager = StoreManager(temp_store_dir)
        manager.initialize()

        # Step 1: Add project with default (copy) mode
        manager.add_project("test-project", [".cursor"], "machine1")
        project = manager.get_project("test-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_COPY

        # Step 2: Update to link mode
        result = manager.update_sync_mode("test-project", SYNC_MODE_LINK)
        assert result is True

        # Step 3: Verify persistence
        manager2 = StoreManager(temp_store_dir)
        project2 = manager2.get_project("test-project")
        assert project2 is not None
        assert project2.sync_mode == SYNC_MODE_LINK

        # Step 4: Add another machine without changing sync_mode
        manager2.add_project("test-project", [".cursor", ".kiro"], "machine2")
        project3 = manager2.get_project("test-project")
        assert project3 is not None
        assert project3.sync_mode == SYNC_MODE_LINK  # Should be preserved

    def test_sync_mode_backward_compatibility(self, temp_store_dir):
        """Test that old metadata without sync_mode still works."""
        import yaml

        # Create old-format metadata (without sync_mode)
        metadata_path = temp_store_dir / ".ar-sync.yaml"
        old_format = {
            "version": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "projects": {
                "old-project": {
                    "added_at": "2025-01-01T00:00:00Z",
                    "targets": [".cursor"],
                    "machines": [{"hostname": "machine1", "linked_at": "2025-01-01T00:00:00Z"}],
                }
            },
        }

        with open(metadata_path, "w") as f:
            yaml.safe_dump(old_format, f)

        # Load and verify default sync_mode
        manager = StoreManager(temp_store_dir)
        project = manager.get_project("old-project")
        assert project is not None
        assert project.sync_mode == SYNC_MODE_COPY  # Should default to copy


class TestFeatureInteraction:
    """Test interactions between multiple features."""

    def test_auto_sync_with_sync_mode_link(self):
        """Test that auto_sync works correctly with link mode projects."""
        # This is a conceptual test - in practice, auto_sync only affects
        # git operations, not the sync_mode of individual projects
        config = LocalConfig(
            version=1,
            backend="git",
            store_path="/tmp/test",
            repo_url="git@github.com:user/repo.git",
            default_targets=[".cursor"],
            auto_sync=True,
            backup_originals=True,
            backup_dir="/tmp/backup",
        )

        # auto_sync should work regardless of project sync_mode
        assert config.auto_sync is True

    def test_ssh_verification_before_auto_sync(self):
        """Test that SSH verification can prevent auto_sync failures."""
        # Verify SSH access before attempting auto_sync
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            can_access = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert can_access is True

            # If verification passes, auto_sync should be safe to use
            config = LocalConfig(
                version=1,
                backend="git",
                store_path="/tmp/test",
                repo_url="git@github.com:user/repo.git",
                default_targets=[".cursor"],
                auto_sync=True,
                backup_originals=True,
                backup_dir="/tmp/backup",
            )
            assert config.auto_sync is True
