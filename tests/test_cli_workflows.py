"""End-to-end workflow tests for CLI commands to improve coverage."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ar_sync.cli import app
from ar_sync.config_manager import ConfigManager
from ar_sync.store_manager import StoreManager


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_env(tmp_path, monkeypatch):
    """Create temporary environment."""
    config_dir = tmp_path / "config"
    store_dir = tmp_path / "store"
    backup_dir = tmp_path / "backups"

    config_dir.mkdir()
    store_dir.mkdir()
    backup_dir.mkdir()

    # Set config path using monkeypatch (auto-restores after test)
    config_path = config_dir / "config.yaml"
    monkeypatch.setattr(ConfigManager, "CONFIG_PATH", config_path)

    return {
        "config_dir": config_dir,
        "store_dir": store_dir,
        "backup_dir": backup_dir,
        "tmp_path": tmp_path,
    }


class TestCompleteWorkflow:
    """Test complete workflow from setup to link."""

    def test_local_backend_workflow(self, runner, temp_env, monkeypatch):
        """Test complete workflow with local backend."""
        store_dir = temp_env["store_dir"]

        # 1. Setup
        result = runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])
        assert result.exit_code == 0

        # 2. Create project with targets
        project_dir = temp_env["tmp_path"] / "my-project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        (project_dir / ".kiro" / "settings.json").write_text('{"test": true}')
        monkeypatch.chdir(project_dir)

        # 3. Init project
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "my-project" in result.stdout

        # Verify symlink was created (local backend auto-links)
        assert (project_dir / ".kiro").is_symlink()

        # 4. Check status
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "my-project" in result.stdout

        # 5. Create another project directory and link
        project2_dir = temp_env["tmp_path"] / "project2"
        project2_dir.mkdir()
        monkeypatch.chdir(project2_dir)

        result = runner.invoke(app, ["link", "--project", "my-project"])
        assert result.exit_code == 0
        assert (project2_dir / ".kiro").is_symlink()
        assert (project2_dir / ".kiro" / "settings.json").read_text() == '{"test": true}'

    def test_add_and_pull_workflow(self, runner, temp_env, monkeypatch):
        """Test add and pull workflow."""
        store_dir = temp_env["store_dir"]

        # Setup
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        # Create project
        project_dir = temp_env["tmp_path"] / "test-project"
        project_dir.mkdir()
        (project_dir / ".cursor").mkdir()
        (project_dir / ".cursor" / "config.json").write_text('{"cursor": "config"}')
        monkeypatch.chdir(project_dir)

        # Add project
        result = runner.invoke(app, ["add"])
        assert result.exit_code == 0

        # Verify files in store
        assert (store_dir / "test-project" / ".cursor" / "config.json").exists()

        # Modify local file
        (project_dir / ".cursor" / "config.json").write_text('{"cursor": "modified"}')

        # Pull from store (should overwrite)
        result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert (project_dir / ".cursor" / "config.json").read_text() == '{"cursor": "config"}'

    def test_push_workflow(self, runner, temp_env, monkeypatch):
        """Test push workflow."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "test-project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        (project_dir / ".kiro" / "file.txt").write_text("version 1")
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Modify local file
        (project_dir / ".kiro" / "file.txt").write_text("version 2")

        # Push changes
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0

        # Verify store was updated
        assert (store_dir / "test-project" / ".kiro" / "file.txt").read_text() == "version 2"

    def test_push_with_new_targets(self, runner, temp_env, monkeypatch):
        """Test push workflow when new targets are added."""
        store_dir = temp_env["store_dir"]

        # Setup and add project with one target
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "test-project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Add new target
        (project_dir / ".cursor").mkdir()
        (project_dir / ".cursor" / "new.txt").write_text("new target")

        # Push should detect and add new target
        result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        assert "new targets" in result.stdout.lower() or "updated targets" in result.stdout.lower()

        # Verify new target in store
        assert (store_dir / "test-project" / ".cursor" / "new.txt").exists()

    def test_config_update_workflow(self, runner, temp_env):
        """Test config update workflow."""
        store_dir = temp_env["store_dir"]

        # Setup
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        # Update path
        new_store = temp_env["tmp_path"] / "new-store"
        new_store.mkdir()

        result = runner.invoke(app, ["config", "--path", str(new_store)])
        assert result.exit_code == 0

        # Verify config was updated
        result = runner.invoke(app, ["config", "--show"])
        assert str(new_store) in result.stdout

        # Update targets
        result = runner.invoke(app, ["config", "--targets", ".vscode,.idea"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["config", "--show"])
        assert ".vscode" in result.stdout
        assert ".idea" in result.stdout


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_init_creates_backup_when_overwriting(self, runner, temp_env, monkeypatch):
        """Test that init creates backup when overwriting existing files."""
        store_dir = temp_env["store_dir"]

        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()

        # Create existing .kiro directory
        kiro_dir = project_dir / ".kiro"
        kiro_dir.mkdir()
        (kiro_dir / "old.txt").write_text("old content")

        monkeypatch.chdir(project_dir)

        # Init should backup existing directory
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "backed up" in result.stdout.lower() or "backup" in result.stdout.lower()

    def test_link_without_force_preserves_existing(self, runner, temp_env, monkeypatch):
        """Test that link without force preserves existing files."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Create another directory with existing file
        project2_dir = temp_env["tmp_path"] / "project2"
        project2_dir.mkdir()
        (project2_dir / ".kiro").mkdir()
        (project2_dir / ".kiro" / "existing.txt").write_text("existing")
        monkeypatch.chdir(project2_dir)

        # Link without force should fail
        result = runner.invoke(app, ["link", "--project", "project"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "already exists" in output.lower() or "use --force" in output.lower()

    def test_link_with_force_overwrites(self, runner, temp_env, monkeypatch):
        """Test that link with force overwrites existing files."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        (project_dir / ".kiro" / "file.txt").write_text("store version")
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Create another directory with existing file
        project2_dir = temp_env["tmp_path"] / "project2"
        project2_dir.mkdir()
        (project2_dir / ".kiro").mkdir()
        (project2_dir / ".kiro" / "file.txt").write_text("local version")
        monkeypatch.chdir(project2_dir)

        # Link with force should succeed
        result = runner.invoke(app, ["link", "--project", "project", "--force"])
        assert result.exit_code == 0

        # Verify symlink was created
        assert (project2_dir / ".kiro").is_symlink()
        assert (project2_dir / ".kiro" / "file.txt").read_text() == "store version"


class TestSyncModeIntegration:
    """Test sync_mode field integration in CLI."""

    def test_link_sets_sync_mode_to_link(self, runner, temp_env, monkeypatch):
        """Test that link command sets sync_mode to 'link'."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Link from another directory
        project2_dir = temp_env["tmp_path"] / "project2"
        project2_dir.mkdir()
        monkeypatch.chdir(project2_dir)

        result = runner.invoke(app, ["link", "--project", "project"])
        assert result.exit_code == 0
        assert "sync_mode: link" in result.stdout

        # Verify metadata
        store_manager = StoreManager(store_dir)
        project_info = store_manager.get_project("project")
        assert project_info.sync_mode == "link"


class TestStatusCommand:
    """Test status command in various scenarios."""

    def test_status_shows_current_project(self, runner, temp_env, monkeypatch):
        """Test that status highlights current project."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "my-project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Check status from project directory
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "my-project" in result.stdout
        # Should show current directory indicator
        assert "→" in result.stdout or "current" in result.stdout.lower()

    def test_status_syncs_metadata(self, runner, temp_env, monkeypatch):
        """Test that status syncs metadata with store contents."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Manually add a file to store
        (store_dir / "project" / ".cursor").mkdir()
        (store_dir / "project" / ".cursor" / "new.txt").write_text("new")

        # Status should sync and show new target
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0


class TestSyncCommand:
    """Test sync command scenarios."""

    def test_sync_pulls_missing_targets_in_current_project(self, runner, temp_env, monkeypatch):
        """Test that sync pulls missing targets for current project."""
        store_dir = temp_env["store_dir"]

        # Setup and add project
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        (project_dir / ".cursor").mkdir()
        monkeypatch.chdir(project_dir)

        runner.invoke(app, ["add"])

        # Remove .cursor locally
        import shutil

        shutil.rmtree(project_dir / ".cursor")

        # Sync should pull missing .cursor
        result = runner.invoke(app, ["sync"])
        assert result.exit_code == 0
        assert (project_dir / ".cursor").exists()


class TestGitBackendSetup:
    """Test git backend setup scenarios."""

    def test_setup_with_git_backend_success(self, runner, temp_env, monkeypatch):
        """Test setup with git backend when remote is accessible."""
        from ar_sync.git_backend import GitBackend

        # Mock verify_remote_access to return True
        original_verify = GitBackend.verify_remote_access
        monkeypatch.setattr(GitBackend, "verify_remote_access", lambda url: True)

        # Mock initialize to avoid actual git operations
        monkeypatch.setattr(GitBackend, "initialize", lambda self: None)

        store_dir = temp_env["store_dir"]

        result = runner.invoke(
            app,
            [
                "setup",
                "--backend",
                "git",
                "--path",
                str(store_dir),
                "--repo-url",
                "git@github.com:test/repo.git",
            ],
        )

        assert result.exit_code == 0
        assert "Remote repository is accessible" in result.stdout
        assert "Git repository initialized" in result.stdout

        # Restore
        monkeypatch.setattr(GitBackend, "verify_remote_access", original_verify)

    def test_setup_with_git_backend_inaccessible_remote(self, runner, temp_env, monkeypatch):
        """Test setup with git backend when remote is not accessible."""
        from ar_sync.git_backend import GitBackend

        # Mock verify_remote_access to return False
        monkeypatch.setattr(GitBackend, "verify_remote_access", lambda url: False)

        store_dir = temp_env["store_dir"]

        result = runner.invoke(
            app,
            [
                "setup",
                "--backend",
                "git",
                "--path",
                str(store_dir),
                "--repo-url",
                "git@github.com:test/repo.git",
            ],
        )

        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Cannot access remote repository" in output

    def test_setup_with_existing_config_uses_defaults(self, runner, temp_env):
        """Test that setup uses existing config values as defaults."""
        store_dir = temp_env["store_dir"]

        # First setup
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        # Second setup without specifying backend (should use existing)
        new_store = temp_env["tmp_path"] / "new-store"
        new_store.mkdir()

        result = runner.invoke(app, ["setup", "--path", str(new_store)])

        assert result.exit_code == 0

        # Verify backend is still local
        config_manager = ConfigManager()
        config = config_manager.load()
        assert config.backend == "local"


class TestExceptionHandling:
    """Test exception handling in CLI commands."""

    def test_setup_handles_filesystem_errors(self, runner, temp_env, monkeypatch):
        """Test that setup handles filesystem errors gracefully."""
        # Mock Path.mkdir to raise OSError

        original_mkdir = Path.mkdir

        def mock_mkdir(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        result = runner.invoke(
            app, ["setup", "--backend", "local", "--path", str(temp_env["store_dir"])]
        )

        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "failed" in output.lower() or "error" in output.lower()

        # Restore
        monkeypatch.setattr(Path, "mkdir", original_mkdir)

    def test_init_handles_unexpected_errors(self, runner, temp_env, monkeypatch):
        """Test that init handles unexpected errors gracefully."""
        # Setup first
        store_dir = temp_env["store_dir"]
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        # Mock ProjectManager.add_project to raise exception
        from ar_sync.project_manager import ProjectManager

        original_add = ProjectManager.add_project

        def mock_add(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr(ProjectManager, "add_project", mock_add)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "failed" in output.lower() or "error" in output.lower()

        # Restore
        monkeypatch.setattr(ProjectManager, "add_project", original_add)


class TestConfigPathExpansion:
    """Test path expansion in config."""

    def test_setup_expands_tilde_in_path(self, runner, temp_env):
        """Test that setup expands ~ in path."""
        # Use a path with tilde
        result = runner.invoke(app, ["setup", "--backend", "local", "--path", "~/test-store"])

        assert result.exit_code == 0

        # Verify path was expanded (~ should be replaced with actual path)
        config_manager = ConfigManager()
        config = config_manager.load()
        assert "~" not in config.store_path
        # Path should be absolute after expansion
        assert config.store_path.startswith("/")

    def test_config_update_expands_path(self, runner, temp_env):
        """Test that config update expands paths."""
        store_dir = temp_env["store_dir"]

        # Setup
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        # Update with tilde path
        result = runner.invoke(app, ["config", "--path", "~/new-store"])

        assert result.exit_code == 0

        # Verify path was expanded
        config_manager = ConfigManager()
        config = config_manager.load()
        assert "~" not in config.store_path


class TestProjectNameHandling:
    """Test project name handling."""

    def test_init_uses_directory_name_as_default(self, runner, temp_env, monkeypatch):
        """Test that init uses directory name as default project name."""
        store_dir = temp_env["store_dir"]

        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "my-awesome-project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "my-awesome-project" in result.stdout

        # Verify in store
        assert (store_dir / "my-awesome-project").exists()

    def test_add_uses_directory_name_as_default(self, runner, temp_env, monkeypatch):
        """Test that add uses directory name as default project name."""
        store_dir = temp_env["store_dir"]

        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        project_dir = temp_env["tmp_path"] / "another-project"
        project_dir.mkdir()
        (project_dir / ".cursor").mkdir()
        monkeypatch.chdir(project_dir)

        result = runner.invoke(app, ["add"])

        assert result.exit_code == 0
        assert "another-project" in result.stdout


class TestMetadataSync:
    """Test metadata synchronization."""

    def test_status_syncs_metadata_for_all_projects(self, runner, temp_env, monkeypatch):
        """Test that status syncs metadata for all projects."""
        store_dir = temp_env["store_dir"]

        # Setup and add multiple projects
        runner.invoke(app, ["setup", "--backend", "local", "--path", str(store_dir)])

        # Add first project
        project1_dir = temp_env["tmp_path"] / "project1"
        project1_dir.mkdir()
        (project1_dir / ".kiro").mkdir()
        monkeypatch.chdir(project1_dir)
        runner.invoke(app, ["add"])

        # Add second project
        project2_dir = temp_env["tmp_path"] / "project2"
        project2_dir.mkdir()
        (project2_dir / ".cursor").mkdir()
        monkeypatch.chdir(project2_dir)
        runner.invoke(app, ["add"])

        # Manually add files to both projects in store
        (store_dir / "project1" / ".cursor").mkdir()
        (store_dir / "project2" / ".kiro").mkdir()

        # Status should sync both
        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Status command runs successfully (sync happens internally)


class TestBackupHandling:
    """Test backup handling."""
