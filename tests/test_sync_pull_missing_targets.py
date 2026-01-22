"""Test sync command pulling missing targets from store.

This test verifies that when running 'ars sync' in a project directory,
if the store has targets that are missing in the project directory,
those targets are automatically pulled from the store.
"""


import pytest
from typer.testing import CliRunner

from ar_sync.cli import app
from ar_sync.config_manager import ConfigManager
from ar_sync.models import LocalConfig


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_env(tmp_path):
    """Create temporary environment with config, store, and project."""
    # Setup directories
    config_dir = tmp_path / "config"
    store_dir = tmp_path / "store"
    project_dir = tmp_path / "project"
    backup_dir = tmp_path / "backups"

    config_dir.mkdir()
    store_dir.mkdir()
    project_dir.mkdir()
    backup_dir.mkdir()

    # Create config
    config_path = config_dir / "config.yaml"
    ConfigManager.CONFIG_PATH = config_path

    config = LocalConfig(
        version=1,
        backend="local",
        store_path=str(store_dir),
        repo_url="",
        default_targets=[".kiro", ".cursor", "AGENTS.md"],
        auto_sync=False,
        backup_originals=True,
        backup_dir=str(backup_dir)
    )

    config_manager = ConfigManager()
    config_manager.save(config)

    return {
        "config_dir": config_dir,
        "store_dir": store_dir,
        "project_dir": project_dir,
        "backup_dir": backup_dir,
        "config": config
    }


def test_sync_pulls_missing_kiro_from_store(runner, temp_env, monkeypatch):
    """Test that sync pulls .kiro from store when it's missing in project.

    Scenario:
    1. Project is cloned from Git (no .kiro in project directory)
    2. Store has .kiro for this project
    3. Run 'ars sync' in project directory
    4. .kiro should be automatically pulled from store
    """
    store_dir = temp_env["store_dir"]
    project_dir = temp_env["project_dir"]

    # Setup: Create project in store with .kiro
    project_name = "test-project"
    project_store_dir = store_dir / project_name
    project_store_dir.mkdir()

    # Create .kiro in store
    kiro_store = project_store_dir / ".kiro"
    kiro_store.mkdir()
    (kiro_store / "settings.json").write_text('{"test": "value"}')

    # Create .cursor in store
    cursor_store = project_store_dir / ".cursor"
    cursor_store.mkdir()
    (cursor_store / "config.json").write_text('{"cursor": "config"}')

    # Create store metadata
    from ar_sync.store_manager import StoreManager
    store_manager = StoreManager(store_dir)
    store_manager.initialize()
    store_manager.add_project(project_name, [".kiro", ".cursor"], "test-host")

    # Setup: Project directory has only .cursor (simulating Git clone without .kiro)
    cursor_project = project_dir / ".cursor"
    cursor_project.mkdir()
    (cursor_project / "config.json").write_text('{"cursor": "config"}')

    # Verify .kiro doesn't exist in project
    assert not (project_dir / ".kiro").exists()
    assert (project_dir / ".cursor").exists()

    # Change to project directory
    monkeypatch.chdir(project_dir)

    # Mock project name to match store
    from ar_sync.project_manager import ProjectManager
    original_get_name = ProjectManager.get_current_project_name
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        lambda: project_name
    )

    # Run sync command (for local backend, this just syncs metadata)
    result = runner.invoke(app, ["sync"])

    # Verify .kiro was pulled from store
    assert (project_dir / ".kiro").exists()
    assert (project_dir / ".kiro" / "settings.json").exists()
    assert (project_dir / ".kiro" / "settings.json").read_text() == '{"test": "value"}'

    # Verify .cursor was not affected
    assert (project_dir / ".cursor").exists()

    # Verify output message
    assert "누락된 타겟 발견" in result.stdout or "missing" in result.stdout.lower()
    assert ".kiro" in result.stdout

    # Restore original function
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        original_get_name
    )


def test_sync_pulls_multiple_missing_targets(runner, temp_env, monkeypatch):
    """Test that sync pulls multiple missing targets from store."""
    store_dir = temp_env["store_dir"]
    project_dir = temp_env["project_dir"]

    # Setup: Create project in store with multiple targets
    project_name = "multi-target-project"
    project_store_dir = store_dir / project_name
    project_store_dir.mkdir()

    # Create multiple targets in store
    (project_store_dir / ".kiro").mkdir()
    (project_store_dir / ".kiro" / "settings.json").write_text('{"kiro": "config"}')

    (project_store_dir / ".cursor").mkdir()
    (project_store_dir / ".cursor" / "config.json").write_text('{"cursor": "config"}')

    (project_store_dir / "AGENTS.md").write_text("# Agents\n")

    # Create store metadata
    from ar_sync.store_manager import StoreManager
    store_manager = StoreManager(store_dir)
    store_manager.initialize()
    store_manager.add_project(project_name, [".kiro", ".cursor", "AGENTS.md"], "test-host")

    # Setup: Project directory is empty (fresh Git clone)
    # Verify nothing exists
    assert not (project_dir / ".kiro").exists()
    assert not (project_dir / ".cursor").exists()
    assert not (project_dir / "AGENTS.md").exists()

    # Change to project directory
    monkeypatch.chdir(project_dir)

    # Mock project name
    from ar_sync.project_manager import ProjectManager
    original_get_name = ProjectManager.get_current_project_name
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        lambda: project_name
    )

    # Run sync command
    result = runner.invoke(app, ["sync"])

    # Verify all targets were pulled
    assert (project_dir / ".kiro").exists()
    assert (project_dir / ".kiro" / "settings.json").read_text() == '{"kiro": "config"}'

    assert (project_dir / ".cursor").exists()
    assert (project_dir / ".cursor" / "config.json").read_text() == '{"cursor": "config"}'

    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / "AGENTS.md").read_text() == "# Agents\n"

    # Verify output
    assert "누락된 타겟" in result.stdout or "missing" in result.stdout.lower()

    # Restore
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        original_get_name
    )


def test_sync_no_pull_when_all_targets_exist(runner, temp_env, monkeypatch):
    """Test that sync doesn't pull when all targets already exist in project."""
    store_dir = temp_env["store_dir"]
    project_dir = temp_env["project_dir"]

    # Setup: Create project in store
    project_name = "complete-project"
    project_store_dir = store_dir / project_name
    project_store_dir.mkdir()

    # Create targets in store
    (project_store_dir / ".kiro").mkdir()
    (project_store_dir / ".kiro" / "settings.json").write_text('{"kiro": "store"}')

    # Create store metadata
    from ar_sync.store_manager import StoreManager
    store_manager = StoreManager(store_dir)
    store_manager.initialize()
    store_manager.add_project(project_name, [".kiro"], "test-host")

    # Setup: Project directory already has .kiro
    kiro_project = project_dir / ".kiro"
    kiro_project.mkdir()
    (kiro_project / "settings.json").write_text('{"kiro": "project"}')

    # Verify .kiro exists with project content
    assert (project_dir / ".kiro" / "settings.json").read_text() == '{"kiro": "project"}'

    # Change to project directory
    monkeypatch.chdir(project_dir)

    # Mock project name
    from ar_sync.project_manager import ProjectManager
    original_get_name = ProjectManager.get_current_project_name
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        lambda: project_name
    )

    # Run sync command
    result = runner.invoke(app, ["sync"])

    # Verify .kiro was NOT overwritten (still has project content)
    assert (project_dir / ".kiro" / "settings.json").read_text() == '{"kiro": "project"}'

    # Verify no pull message in output
    assert "누락된 타겟" not in result.stdout
    assert "missing" not in result.stdout.lower() or "no missing" in result.stdout.lower()

    # Restore
    monkeypatch.setattr(
        ProjectManager,
        "get_current_project_name",
        original_get_name
    )


def test_sync_ignores_unregistered_project(runner, temp_env, monkeypatch):
    """Test that sync doesn't pull when current directory is not a registered project."""
    store_dir = temp_env["store_dir"]
    project_dir = temp_env["project_dir"]

    # Setup: Create store metadata but no project
    from ar_sync.store_manager import StoreManager
    store_manager = StoreManager(store_dir)
    store_manager.initialize()

    # Change to project directory (not registered)
    monkeypatch.chdir(project_dir)

    # Run sync command
    result = runner.invoke(app, ["sync"])

    # Print output for debugging
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.stdout}")

    # Verify no error and no pull happened
    assert result.exit_code == 0
    assert not (project_dir / ".kiro").exists()
    assert "누락된 타겟" not in result.stdout
