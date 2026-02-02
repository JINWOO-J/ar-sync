"""Integration tests for ProjectManager to improve coverage."""

import socket
from pathlib import Path

import pytest

from ar_sync.project_manager import ProjectManager


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    store_dir = tmp_path / "store"
    backup_dir = tmp_path / "backups"
    project_dir = tmp_path / "project"

    store_dir.mkdir()
    backup_dir.mkdir()
    project_dir.mkdir()

    return {
        "store": store_dir,
        "backup": backup_dir,
        "project": project_dir
    }


@pytest.fixture
def manager(temp_dirs):
    """Create ProjectManager instance."""
    return ProjectManager(temp_dirs["store"], temp_dirs["backup"])


class TestAddProject:
    """Test add_project method."""

    def test_add_project_with_file_target(self, manager, temp_dirs):
        """Test adding project with file target."""
        project_dir = temp_dirs["project"]

        # Create a file target
        (project_dir / "config.txt").write_text("test config")

        manager.add_project(project_dir, "test-project", ["config.txt"])

        # Verify file was copied
        store_file = temp_dirs["store"] / "test-project" / "config.txt"
        assert store_file.exists()
        assert store_file.read_text() == "test config"

    def test_add_project_with_directory_target(self, manager, temp_dirs):
        """Test adding project with directory target."""
        project_dir = temp_dirs["project"]

        # Create a directory target
        kiro_dir = project_dir / ".kiro"
        kiro_dir.mkdir()
        (kiro_dir / "settings.json").write_text('{"test": true}')

        manager.add_project(project_dir, "test-project", [".kiro"])

        # Verify directory was copied
        store_dir = temp_dirs["store"] / "test-project" / ".kiro"
        assert store_dir.exists()
        assert store_dir.is_dir()
        assert (store_dir / "settings.json").read_text() == '{"test": true}'

    def test_add_project_overwrites_existing(self, manager, temp_dirs):
        """Test that add_project overwrites existing files in store."""
        project_dir = temp_dirs["project"]

        # Create initial file
        (project_dir / "config.txt").write_text("version 1")
        manager.add_project(project_dir, "test-project", ["config.txt"])

        # Update file and add again
        (project_dir / "config.txt").write_text("version 2")
        manager.add_project(project_dir, "test-project", ["config.txt"])

        # Verify file was overwritten
        store_file = temp_dirs["store"] / "test-project" / "config.txt"
        assert store_file.read_text() == "version 2"

    def test_add_project_skips_missing_targets(self, manager, temp_dirs):
        """Test that add_project skips targets that don't exist."""
        project_dir = temp_dirs["project"]

        # Create only one target
        (project_dir / "exists.txt").write_text("exists")

        # Try to add both existing and non-existing targets
        manager.add_project(project_dir, "test-project", ["exists.txt", "missing.txt"])

        # Verify only existing target was copied
        assert (temp_dirs["store"] / "test-project" / "exists.txt").exists()
        assert not (temp_dirs["store"] / "test-project" / "missing.txt").exists()

    def test_add_project_raises_error_for_nonexistent_directory(self, manager):
        """Test that add_project raises error for non-existent project directory."""
        with pytest.raises(FileNotFoundError, match="Project directory not found"):
            manager.add_project(Path("/nonexistent"), "test-project", [".kiro"])

    def test_add_project_creates_nested_directories(self, manager, temp_dirs):
        """Test that add_project creates nested directory structure."""
        project_dir = temp_dirs["project"]

        # Create nested structure
        nested = project_dir / ".kiro" / "subdir"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("nested")

        manager.add_project(project_dir, "test-project", [".kiro"])

        # Verify nested structure was preserved
        store_nested = temp_dirs["store"] / "test-project" / ".kiro" / "subdir" / "file.txt"
        assert store_nested.exists()
        assert store_nested.read_text() == "nested"


class TestLinkProject:
    """Test link_project method."""

    def test_link_project_creates_symlink(self, manager, temp_dirs):
        """Test that link_project creates symlinks."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("store config")

        # Link project
        manager.link_project(project_dir, "test-project", ["config.txt"], force=False)

        # Verify symlink was created
        link = project_dir / "config.txt"
        assert link.is_symlink()
        assert link.resolve() == (project_store / "config.txt").resolve()

    def test_link_project_raises_error_for_nonexistent_project(self, manager, temp_dirs):
        """Test that link_project raises error for non-existent project in store."""
        with pytest.raises(FileNotFoundError, match="Project not found in store"):
            manager.link_project(temp_dirs["project"], "nonexistent", [".kiro"], force=False)

    def test_link_project_raises_error_for_existing_file_without_force(self, manager, temp_dirs):
        """Test that link_project raises error when file exists and force=False."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("store config")

        # Create existing file in project
        (project_dir / "config.txt").write_text("existing")

        # Try to link without force
        with pytest.raises(FileExistsError, match="Target already exists"):
            manager.link_project(project_dir, "test-project", ["config.txt"], force=False)

    def test_link_project_backs_up_existing_file_with_force(self, manager, temp_dirs):
        """Test that link_project backs up existing files when force=True."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]
        temp_dirs["backup"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("store config")

        # Create existing file in project
        (project_dir / "config.txt").write_text("existing")

        # Link with force
        backed_up = manager.link_project(project_dir, "test-project", ["config.txt"], force=True)

        # Verify backup was created
        assert len(backed_up) == 1
        backup_path = Path(backed_up[0])
        assert backup_path.exists()
        assert backup_path.read_text() == "existing"
        assert "test-project" in str(backup_path)

    def test_link_project_removes_existing_directory_with_force(self, manager, temp_dirs):
        """Test that link_project removes existing directories when force=True."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        store_kiro = project_store / ".kiro"
        store_kiro.mkdir()
        (store_kiro / "settings.json").write_text("store")

        # Create existing directory in project
        project_kiro = project_dir / ".kiro"
        project_kiro.mkdir()
        (project_kiro / "old.txt").write_text("old")

        # Link with force
        manager.link_project(project_dir, "test-project", [".kiro"], force=True)

        # Verify symlink was created
        assert project_kiro.is_symlink()
        assert (project_kiro / "settings.json").read_text() == "store"

    def test_link_project_skips_missing_targets(self, manager, temp_dirs):
        """Test that link_project skips targets that don't exist in store."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create project in store with only one target
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "exists.txt").write_text("exists")

        # Try to link both existing and non-existing targets
        backed_up = manager.link_project(
            project_dir, "test-project", ["exists.txt", "missing.txt"], force=False
        )

        # Verify only existing target was linked
        assert (project_dir / "exists.txt").is_symlink()
        assert not (project_dir / "missing.txt").exists()
        assert len(backed_up) == 0

    def test_link_project_handles_existing_symlink_with_force(self, manager, temp_dirs):
        """Test that link_project handles existing symlinks when force=True."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("new")

        # Create existing symlink to different location
        other_file = temp_dirs["backup"] / "other.txt"
        other_file.write_text("old")
        (project_dir / "config.txt").symlink_to(other_file)

        # Link with force
        backed_up = manager.link_project(project_dir, "test-project", ["config.txt"], force=True)

        # Verify new symlink was created
        link = project_dir / "config.txt"
        assert link.is_symlink()
        assert link.read_text() == "new"
        assert len(backed_up) == 1


class TestPullFromStore:
    """Test pull_from_store method."""

    def test_pull_from_store_copies_files(self, manager, temp_dirs):
        """Test that pull_from_store copies files from store to project."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("store config")

        # Pull from store
        manager.pull_from_store(project_dir, "test-project", ["config.txt"])

        # Verify file was copied (not symlinked)
        dest = project_dir / "config.txt"
        assert dest.exists()
        assert not dest.is_symlink()
        assert dest.read_text() == "store config"

    def test_pull_from_store_overwrites_existing_files(self, manager, temp_dirs):
        """Test that pull_from_store overwrites existing files."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("new version")

        # Create existing file
        (project_dir / "config.txt").write_text("old version")

        # Pull from store
        manager.pull_from_store(project_dir, "test-project", ["config.txt"])

        # Verify file was overwritten
        assert (project_dir / "config.txt").read_text() == "new version"

    def test_pull_from_store_removes_existing_directory(self, manager, temp_dirs):
        """Test that pull_from_store removes existing directories before copying."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        store_kiro = project_store / ".kiro"
        store_kiro.mkdir()
        (store_kiro / "new.txt").write_text("new")

        # Create existing directory
        project_kiro = project_dir / ".kiro"
        project_kiro.mkdir()
        (project_kiro / "old.txt").write_text("old")

        # Pull from store
        manager.pull_from_store(project_dir, "test-project", [".kiro"])

        # Verify directory was replaced
        assert project_kiro.exists()
        assert not project_kiro.is_symlink()
        assert (project_kiro / "new.txt").exists()
        assert not (project_kiro / "old.txt").exists()

    def test_pull_from_store_raises_error_for_nonexistent_project(self, manager, temp_dirs):
        """Test that pull_from_store raises error for non-existent project."""
        with pytest.raises(FileNotFoundError, match="Project not found in store"):
            manager.pull_from_store(temp_dirs["project"], "nonexistent", [".kiro"])

    def test_pull_from_store_skips_missing_targets(self, manager, temp_dirs):
        """Test that pull_from_store skips targets that don't exist in store."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create project in store with only one target
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "exists.txt").write_text("exists")

        # Pull both existing and non-existing targets
        manager.pull_from_store(project_dir, "test-project", ["exists.txt", "missing.txt"])

        # Verify only existing target was copied
        assert (project_dir / "exists.txt").exists()
        assert not (project_dir / "missing.txt").exists()

    def test_pull_from_store_removes_existing_symlink(self, manager, temp_dirs):
        """Test that pull_from_store removes existing symlinks before copying."""
        project_dir = temp_dirs["project"]
        store_dir = temp_dirs["store"]

        # Create target in store
        project_store = store_dir / "test-project"
        project_store.mkdir()
        (project_store / "config.txt").write_text("real file")

        # Create existing symlink
        other_file = temp_dirs["backup"] / "other.txt"
        other_file.write_text("symlink target")
        (project_dir / "config.txt").symlink_to(other_file)

        # Pull from store
        manager.pull_from_store(project_dir, "test-project", ["config.txt"])

        # Verify symlink was replaced with real file
        dest = project_dir / "config.txt"
        assert dest.exists()
        assert not dest.is_symlink()
        assert dest.read_text() == "real file"


class TestPushToStore:
    """Test push_to_store method."""

    def test_push_to_store_is_alias_for_add_project(self, manager, temp_dirs):
        """Test that push_to_store works the same as add_project."""
        project_dir = temp_dirs["project"]

        # Create a file
        (project_dir / "config.txt").write_text("test")

        # Push to store
        manager.push_to_store(project_dir, "test-project", ["config.txt"])

        # Verify file was copied
        store_file = temp_dirs["store"] / "test-project" / "config.txt"
        assert store_file.exists()
        assert store_file.read_text() == "test"


class TestStaticMethods:
    """Test static methods."""

    def test_get_hostname_returns_string(self):
        """Test that get_hostname returns a non-empty string."""
        hostname = ProjectManager.get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0
        assert hostname == socket.gethostname()

    def test_get_current_project_name_returns_directory_name(self, tmp_path, monkeypatch):
        """Test that get_current_project_name returns current directory name."""
        test_dir = tmp_path / "my-project"
        test_dir.mkdir()
        monkeypatch.chdir(test_dir)

        project_name = ProjectManager.get_current_project_name()
        assert project_name == "my-project"


class TestScanTargets:
    """Test scan_targets method."""

    def test_scan_targets_finds_existing_files(self, tmp_path):
        """Test that scan_targets finds existing files."""
        # Create some targets
        (tmp_path / ".kiro").mkdir()
        (tmp_path / "AGENTS.md").write_text("# Agents")

        found = ProjectManager.scan_targets(tmp_path, [".kiro", ".cursor", "AGENTS.md"])

        assert ".kiro" in found
        assert "AGENTS.md" in found
        assert ".cursor" not in found

    def test_scan_targets_returns_empty_list_when_nothing_found(self, tmp_path):
        """Test that scan_targets returns empty list when no targets exist."""
        found = ProjectManager.scan_targets(tmp_path, [".kiro", ".cursor"])
        assert found == []

    def test_scan_targets_preserves_order(self, tmp_path):
        """Test that scan_targets preserves the order of found targets."""
        # Create targets in specific order
        (tmp_path / "c.txt").write_text("c")
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        found = ProjectManager.scan_targets(tmp_path, ["a.txt", "b.txt", "c.txt"])

        assert found == ["a.txt", "b.txt", "c.txt"]
