"""Integration tests for CLI commands to improve coverage."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ar_sync.cli import app
from ar_sync.config_manager import ConfigManager
from ar_sync.models import LocalConfig
from ar_sync.store_manager import StoreManager


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_env(tmp_path):
    """Create temporary environment with config."""
    config_dir = tmp_path / "config"
    store_dir = tmp_path / "store"
    backup_dir = tmp_path / "backups"

    config_dir.mkdir()
    store_dir.mkdir()
    backup_dir.mkdir()

    # Set config path
    config_path = config_dir / "config.yaml"
    ConfigManager.CONFIG_PATH = config_path

    return {
        "config_dir": config_dir,
        "store_dir": store_dir,
        "backup_dir": backup_dir,
        "tmp_path": tmp_path
    }


class TestSetupCommand:
    """Test setup command."""

    def test_setup_with_local_backend(self, runner, temp_env):
        """Test setup command with local backend."""
        store_dir = temp_env["store_dir"]
        
        result = runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        assert result.exit_code == 0
        assert "Configuration saved" in result.stdout
        assert "Store directory created" in result.stdout
        assert "Store metadata created" in result.stdout

    def test_setup_with_invalid_backend(self, runner, temp_env):
        """Test setup command with invalid backend."""
        result = runner.invoke(app, [
            "setup",
            "--backend", "invalid",
            "--path", str(temp_env["store_dir"])
        ])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Unsupported backend" in output

    def test_setup_without_path(self, runner, temp_env):
        """Test setup command without path."""
        result = runner.invoke(app, [
            "setup",
            "--backend", "local"
        ])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store path is required" in output

    def test_setup_with_git_backend_without_repo_url(self, runner, temp_env):
        """Test setup command with git backend but no repo URL."""
        result = runner.invoke(app, [
            "setup",
            "--backend", "git",
            "--path", str(temp_env["store_dir"])
        ])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Repository URL is required" in output

    def test_setup_updates_existing_config(self, runner, temp_env):
        """Test that setup can update existing configuration."""
        store_dir = temp_env["store_dir"]
        
        # First setup
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        # Update with new path
        new_store = temp_env["tmp_path"] / "new-store"
        new_store.mkdir()
        
        result = runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(new_store)
        ])
        
        assert result.exit_code == 0
        
        # Verify config was updated
        config_manager = ConfigManager()
        config = config_manager.load()
        assert config.store_path == str(new_store)


class TestInitCommand:
    """Test init command."""

    def test_init_without_setup(self, runner, temp_env, monkeypatch):
        """Test init command without prior setup."""
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["init"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Global configuration not found" in output

    def test_init_with_no_targets_found(self, runner, temp_env, monkeypatch):
        """Test init command when no targets are found."""
        # Setup first
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        # Create empty project directory
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["init"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "No target files found" in output

    def test_init_with_custom_name(self, runner, temp_env, monkeypatch):
        """Test init command with custom project name."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        # Create project with targets
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / ".kiro").mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["init", "--name", "custom-name"])
        
        assert result.exit_code == 0
        assert "custom-name" in result.stdout
        
        # Verify project was added with custom name
        store_manager = StoreManager(store_dir)
        project = store_manager.get_project("custom-name")
        assert project is not None

    def test_init_with_custom_targets(self, runner, temp_env, monkeypatch):
        """Test init command with custom targets."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        # Create project with custom targets
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        (project_dir / "custom.txt").write_text("custom")
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["init", "--targets", "custom.txt"])
        
        assert result.exit_code == 0
        assert "custom.txt" in result.stdout


class TestAddCommand:
    """Test add command."""

    def test_add_without_setup(self, runner, temp_env, monkeypatch):
        """Test add command without prior setup."""
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["add"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output


class TestLinkCommand:
    """Test link command."""

    def test_link_without_setup(self, runner, temp_env, monkeypatch):
        """Test link command without prior setup."""
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["link"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output

    def test_link_nonexistent_project(self, runner, temp_env, monkeypatch):
        """Test link command for non-existent project."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["link", "--project", "nonexistent"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in store" in output

    def test_link_with_missing_store_directory(self, runner, temp_env, monkeypatch):
        """Test link command when store directory is missing."""
        # Create config but don't create store directory
        config = LocalConfig(
            version=1,
            backend="local",
            store_path=str(temp_env["tmp_path"] / "missing-store"),
            repo_url="",
            default_targets=[".kiro"],
            auto_sync=False,
            backup_originals=True,
            backup_dir=str(temp_env["backup_dir"])
        )
        config_manager = ConfigManager()
        config_manager.save(config)
        
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["link"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store directory does not exist" in output


class TestStatusCommand:
    """Test status command."""

    def test_status_without_setup(self, runner, temp_env):
        """Test status command without prior setup."""
        result = runner.invoke(app, ["status"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output

    def test_status_with_no_projects(self, runner, temp_env):
        """Test status command with no registered projects."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["status"])
        
        assert result.exit_code == 0
        assert "No projects registered" in result.stdout

    def test_status_with_missing_store_directory(self, runner, temp_env):
        """Test status command when store directory is missing."""
        # Create config but don't create store directory
        config = LocalConfig(
            version=1,
            backend="local",
            store_path=str(temp_env["tmp_path"] / "missing-store"),
            repo_url="",
            default_targets=[".kiro"],
            auto_sync=False,
            backup_originals=True,
            backup_dir=str(temp_env["backup_dir"])
        )
        config_manager = ConfigManager()
        config_manager.save(config)
        
        result = runner.invoke(app, ["status"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store directory does not exist" in output


class TestSyncCommand:
    """Test sync command."""

    def test_sync_without_setup(self, runner, temp_env):
        """Test sync command without prior setup."""
        result = runner.invoke(app, ["sync"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output

    def test_sync_with_pull_and_push_options(self, runner, temp_env):
        """Test sync command with conflicting --pull and --push options."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "git",
            "--path", str(store_dir),
            "--repo-url", "git@github.com:test/repo.git"
        ])
        
        result = runner.invoke(app, ["sync", "--pull", "--push"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Cannot use --pull and --push together" in output

    def test_sync_with_local_and_remote_options(self, runner, temp_env):
        """Test sync command with conflicting --local and --remote options (Requirement 6.3)."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "git",
            "--path", str(store_dir),
            "--repo-url", "git@github.com:test/repo.git"
        ])
        
        result = runner.invoke(app, ["sync", "--local", "--remote"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Cannot use --local and --remote together" in output

    def test_sync_with_diff_option(self, runner, temp_env):
        """Test sync command with --diff option (Requirement 3.3)."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "git",
            "--path", str(store_dir),
            "--repo-url", "git@github.com:test/repo.git"
        ])
        
        result = runner.invoke(app, ["sync", "--diff"])
        
        assert result.exit_code == 0
        assert "[DRY-RUN]" in result.stdout
        assert "differences only" in result.stdout

    def test_sync_with_dry_run_option(self, runner, temp_env):
        """Test sync command with --dry-run option (Requirement 7.1).
        
        Note: Full dry-run functionality will be implemented in task 9.2.
        This test verifies the option is recognized and displays the preview message.
        """
        # Setup with local backend to avoid git operations
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["sync", "--dry-run"])
        
        # For local backend, new options show warning message
        assert result.exit_code == 0
        assert "only available for 'git' backend" in result.stdout

    def test_sync_with_local_backend_ignores_git_options(self, runner, temp_env):
        """Test that sync with local backend ignores git-specific options."""
        # Setup with local backend
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["sync", "--pull", "-m", "test message"])
        
        assert result.exit_code == 0
        assert "only available for 'git' backend" in result.stdout

    def test_sync_with_local_backend_ignores_new_options(self, runner, temp_env):
        """Test that sync with local backend ignores new bidirectional sync options."""
        # Setup with local backend
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["sync", "--local", "--dry-run", "--diff"])
        
        assert result.exit_code == 0
        assert "only available for 'git' backend" in result.stdout


class TestPullCommand:
    """Test pull command."""

    def test_pull_without_setup(self, runner, temp_env, monkeypatch):
        """Test pull command without prior setup."""
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["pull"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output

    def test_pull_nonexistent_project(self, runner, temp_env, monkeypatch):
        """Test pull command for non-existent project."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["pull", "--project", "nonexistent"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in store" in output

    def test_pull_with_missing_store_directory(self, runner, temp_env, monkeypatch):
        """Test pull command when store directory is missing."""
        # Create config but don't create store directory
        config = LocalConfig(
            version=1,
            backend="local",
            store_path=str(temp_env["tmp_path"] / "missing-store"),
            repo_url="",
            default_targets=[".kiro"],
            auto_sync=False,
            backup_originals=True,
            backup_dir=str(temp_env["backup_dir"])
        )
        config_manager = ConfigManager()
        config_manager.save(config)
        
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["pull"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store directory does not exist" in output


class TestPushCommand:
    """Test push command."""

    def test_push_without_setup(self, runner, temp_env, monkeypatch):
        """Test push command without prior setup."""
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["push"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Store not initialized" in output

    def test_push_nonexistent_project(self, runner, temp_env, monkeypatch):
        """Test push command for non-existent project."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        project_dir = temp_env["tmp_path"] / "project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        
        result = runner.invoke(app, ["push", "--project", "nonexistent"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in store" in output


class TestConfigCommand:
    """Test config command."""

    def test_config_show_without_setup(self, runner, temp_env):
        """Test config --show without prior setup."""
        result = runner.invoke(app, ["config", "--show"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Configuration not found" in output

    def test_config_show_displays_current_config(self, runner, temp_env):
        """Test that config --show displays current configuration."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--show"])
        
        assert result.exit_code == 0
        assert "Current configuration" in result.stdout
        assert "Backend:" in result.stdout
        assert "local" in result.stdout

    def test_config_update_backend(self, runner, temp_env):
        """Test updating backend via config command."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--backend", "git", "--repo-url", "git@github.com:test/repo.git"])
        
        assert result.exit_code == 0
        assert "Backend set to: git" in result.stdout

    def test_config_update_invalid_backend(self, runner, temp_env):
        """Test updating to invalid backend."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--backend", "invalid"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Invalid backend" in output

    def test_config_update_targets(self, runner, temp_env):
        """Test updating default targets."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--targets", ".vscode,.idea"])
        
        assert result.exit_code == 0
        assert "Default targets set to" in result.stdout

    def test_config_update_auto_sync(self, runner, temp_env):
        """Test updating auto_sync setting."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--auto-sync", "true"])
        
        assert result.exit_code == 0
        assert "Auto sync set to: True" in result.stdout

    def test_config_update_auto_sync_invalid_value(self, runner, temp_env):
        """Test updating auto_sync with invalid value."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config", "--auto-sync", "invalid"])
        
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Invalid auto-sync value" in output

    def test_config_without_options_shows_config(self, runner, temp_env):
        """Test that config without options shows current configuration."""
        # Setup
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["config"])
        
        assert result.exit_code == 0
        assert "Current configuration" in result.stdout


class TestVersionOption:
    """Test --version option."""

    def test_version_option(self, runner):
        """Test that --version displays version."""
        result = runner.invoke(app, ["--version"])
        
        assert result.exit_code == 0
        assert "ar-sync version" in result.stdout

    def test_version_short_option(self, runner):
        """Test that -v displays version."""
        result = runner.invoke(app, ["-v"])
        
        assert result.exit_code == 0
        assert "ar-sync version" in result.stdout


class TestDebugOption:
    """Test --debug option."""

    def test_debug_option_with_setup(self, runner, temp_env):
        """Test that --debug option works with setup command."""
        store_dir = temp_env["store_dir"]
        
        result = runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir),
            "--debug"
        ])
        
        # Debug mode should not affect success
        assert result.exit_code == 0

    def test_debug_option_with_status(self, runner, temp_env):
        """Test that --debug option works with status command."""
        # Setup first
        store_dir = temp_env["store_dir"]
        runner.invoke(app, [
            "setup",
            "--backend", "local",
            "--path", str(store_dir)
        ])
        
        result = runner.invoke(app, ["status", "--debug"])
        
        assert result.exit_code == 0
