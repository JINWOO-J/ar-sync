"""Unit tests for DiffEngine.

Tests for the DiffEngine class which handles file comparison between
Project and Store directories.

Requirements tested:
- 2.1: Identify files that exist only in Project_Directory
- 2.2: Identify files that exist only in Store
- 2.3: Identify files that exist in both but have different content
- 2.4: Use content-based comparison (not timestamp)
- 2.5: Skip symlinks pointing to Store
- 2.6: Recursively compare all files within Target_Files
- 3.1: Use `git diff --no-index` format
- 3.4: Show file paths relative to project root
- 3.5: Exclude files with no differences from output
"""

import os

from ar_sync.sync.diff_engine import DiffEngine
from ar_sync.sync.models import ChangeType


class TestDiffEngineCompareDirectories:
    """Tests for DiffEngine.compare_directories()."""

    def test_file_only_in_project_detected_as_added_local(self, tmp_path):
        """Requirement 2.1: Files only in Project should be ADDED_LOCAL."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create file only in project
        (project_dir / "local_only.txt").write_text("local content")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["local_only.txt"])

        assert len(changes) == 1
        assert changes[0].path == "local_only.txt"
        assert changes[0].change_type == ChangeType.ADDED_LOCAL
        assert changes[0].local_path == project_dir / "local_only.txt"
        assert changes[0].remote_path is None

    def test_file_only_in_store_detected_as_added_remote(self, tmp_path):
        """Requirement 2.2: Files only in Store should be ADDED_REMOTE."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create file only in store
        (store_dir / "remote_only.txt").write_text("remote content")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["remote_only.txt"])

        assert len(changes) == 1
        assert changes[0].path == "remote_only.txt"
        assert changes[0].change_type == ChangeType.ADDED_REMOTE
        assert changes[0].local_path is None
        assert changes[0].remote_path == store_dir / "remote_only.txt"

    def test_different_content_detected_as_modified(self, tmp_path):
        """Requirement 2.3: Files with different content should be MODIFIED."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create files with different content
        (project_dir / "config.txt").write_text("local version")
        (store_dir / "config.txt").write_text("remote version")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["config.txt"])

        assert len(changes) == 1
        assert changes[0].path == "config.txt"
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].local_path == project_dir / "config.txt"
        assert changes[0].remote_path == store_dir / "config.txt"

    def test_identical_files_excluded_from_output(self, tmp_path):
        """Requirement 3.5: Files with no differences should be excluded."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create identical files
        (project_dir / "same.txt").write_text("identical content")
        (store_dir / "same.txt").write_text("identical content")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["same.txt"])

        # UNCHANGED files should be excluded
        assert len(changes) == 0

    def test_recursive_directory_comparison(self, tmp_path):
        """Requirement 2.6: Recursively compare all files within Target_Files."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create nested directory structure
        (project_dir / ".kiro").mkdir()
        (project_dir / ".kiro" / "specs").mkdir()
        (project_dir / ".kiro" / "config.yaml").write_text("local config")
        (project_dir / ".kiro" / "specs" / "feature.md").write_text("local spec")

        (store_dir / ".kiro").mkdir()
        (store_dir / ".kiro" / "specs").mkdir()
        (store_dir / ".kiro" / "config.yaml").write_text("remote config")
        (store_dir / ".kiro" / "specs" / "feature.md").write_text("remote spec")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, [".kiro"])

        # Both files should be detected as modified
        assert len(changes) == 2
        paths = {c.path for c in changes}
        assert ".kiro/config.yaml" in paths
        assert ".kiro/specs/feature.md" in paths

    def test_multiple_targets(self, tmp_path):
        """Test comparison with multiple target files/directories."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create multiple targets
        (project_dir / "AGENTS.md").write_text("local agents")
        (store_dir / "AGENTS.md").write_text("remote agents")
        (project_dir / ".cursor").mkdir()
        (project_dir / ".cursor" / "settings.json").write_text('{"local": true}')
        (store_dir / ".cursor").mkdir()
        (store_dir / ".cursor" / "settings.json").write_text('{"remote": true}')

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["AGENTS.md", ".cursor"])

        assert len(changes) == 2
        paths = {c.path for c in changes}
        assert "AGENTS.md" in paths
        assert ".cursor/settings.json" in paths

    def test_nonexistent_target_ignored(self, tmp_path):
        """Test that nonexistent targets are gracefully ignored."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["nonexistent.txt"])

        assert len(changes) == 0


class TestDiffEngineSymlinkSkip:
    """Tests for symlink detection and skip logic."""

    def test_symlink_to_store_skipped(self, tmp_path):
        """Requirement 2.5: Symlinks pointing to Store should be skipped."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create a file in store
        (store_dir / "config.txt").write_text("store content")

        # Create a symlink in project pointing to store
        symlink_path = project_dir / "config.txt"
        symlink_path.symlink_to(store_dir / "config.txt")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["config.txt"])

        # Symlink should be skipped, so only store file detected
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.ADDED_REMOTE

    def test_symlink_to_other_location_not_skipped(self, tmp_path):
        """Symlinks not pointing to Store should be compared normally."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        other_dir = tmp_path / "other"
        project_dir.mkdir()
        store_dir.mkdir()
        other_dir.mkdir()

        # Create a file in other location
        (other_dir / "config.txt").write_text("other content")

        # Create a symlink in project pointing to other location
        symlink_path = project_dir / "config.txt"
        symlink_path.symlink_to(other_dir / "config.txt")

        # Create different file in store
        (store_dir / "config.txt").write_text("store content")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["config.txt"])

        # Symlink should be compared (points to different content)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED

    def test_broken_symlink_skipped(self, tmp_path):
        """Broken symlinks should be handled gracefully."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create a broken symlink
        symlink_path = project_dir / "broken.txt"
        symlink_path.symlink_to(tmp_path / "nonexistent.txt")

        engine = DiffEngine()
        # Should not raise an error
        changes = engine.compare_directories(project_dir, store_dir, ["broken.txt"])
        assert len(changes) == 0


class TestDiffEngineContentBasedComparison:
    """Tests for content-based comparison (Requirement 2.4)."""

    def test_same_content_different_timestamps_unchanged(self, tmp_path):
        """Requirement 2.4: Same content with different timestamps = UNCHANGED."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create files with same content
        project_file = project_dir / "config.txt"
        store_file = store_dir / "config.txt"
        project_file.write_text("same content")
        store_file.write_text("same content")

        # Set different modification times
        os.utime(project_file, (1000000, 1000000))
        os.utime(store_file, (2000000, 2000000))

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["config.txt"])

        # Should be excluded (UNCHANGED)
        assert len(changes) == 0

    def test_different_content_same_timestamps_modified(self, tmp_path):
        """Requirement 2.4: Different content with same timestamps = MODIFIED."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create files with different content
        project_file = project_dir / "config.txt"
        store_file = store_dir / "config.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")

        # Set same modification times
        os.utime(project_file, (1000000, 1000000))
        os.utime(store_file, (1000000, 1000000))

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["config.txt"])

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED


class TestDiffEngineCompareFiles:
    """Tests for DiffEngine.compare_files()."""

    def test_compare_two_existing_files(self, tmp_path):
        """Test comparing two existing files with different content."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        local_file.write_text("local content")
        remote_file.write_text("remote content")

        engine = DiffEngine()
        change = engine.compare_files(local_file, remote_file)

        assert change.change_type == ChangeType.MODIFIED
        assert change.local_path == local_file
        assert change.remote_path == remote_file

    def test_compare_identical_files(self, tmp_path):
        """Test comparing two identical files."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        local_file.write_text("same content")
        remote_file.write_text("same content")

        engine = DiffEngine()
        change = engine.compare_files(local_file, remote_file)

        assert change.change_type == ChangeType.UNCHANGED

    def test_compare_local_only(self, tmp_path):
        """Test comparing when only local file exists."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        local_file.write_text("local content")
        # remote_file does not exist

        engine = DiffEngine()
        change = engine.compare_files(local_file, remote_file)

        assert change.change_type == ChangeType.ADDED_LOCAL

    def test_compare_remote_only(self, tmp_path):
        """Test comparing when only remote file exists."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        # local_file does not exist
        remote_file.write_text("remote content")

        engine = DiffEngine()
        change = engine.compare_files(local_file, remote_file)

        assert change.change_type == ChangeType.ADDED_REMOTE


class TestDiffEngineGetDiffOutput:
    """Tests for DiffEngine.get_diff_output()."""

    def test_diff_output_format(self, tmp_path):
        """Requirement 3.1: Use git diff --no-index format."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        local_file.write_text("line1\nlocal line\nline3\n")
        remote_file.write_text("line1\nremote line\nline3\n")

        engine = DiffEngine()
        diff_output = engine.get_diff_output(local_file, remote_file)

        # Should contain git diff format markers
        assert "diff --git" in diff_output or "---" in diff_output
        assert "@@" in diff_output  # Hunk header

    def test_diff_output_empty_for_identical_files(self, tmp_path):
        """Test that diff output is empty for identical files."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"
        local_file.write_text("same content")
        remote_file.write_text("same content")

        engine = DiffEngine()
        diff_output = engine.get_diff_output(local_file, remote_file)

        assert diff_output == ""


class TestDiffEngineIsBinaryFile:
    """Tests for DiffEngine.is_binary_file()."""

    def test_text_file_not_binary(self, tmp_path):
        """Test that text files are not detected as binary."""
        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello, World!\nThis is a text file.\n")

        engine = DiffEngine()
        assert engine.is_binary_file(text_file) is False

    def test_binary_file_by_extension(self, tmp_path):
        """Test that files with binary extensions are detected."""
        png_file = tmp_path / "image.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        engine = DiffEngine()
        assert engine.is_binary_file(png_file) is True

    def test_binary_file_by_content(self, tmp_path):
        """Test that files with null bytes are detected as binary."""
        binary_file = tmp_path / "data.dat"
        binary_file.write_bytes(b"Some text\x00with null bytes")

        engine = DiffEngine()
        assert engine.is_binary_file(binary_file) is True

    def test_empty_file_not_binary(self, tmp_path):
        """Test that empty files are not detected as binary."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        engine = DiffEngine()
        assert engine.is_binary_file(empty_file) is False

    def test_json_file_not_binary(self, tmp_path):
        """Test that JSON files are not detected as binary."""
        json_file = tmp_path / "config.json"
        json_file.write_text('{"key": "value", "number": 123}')

        engine = DiffEngine()
        assert engine.is_binary_file(json_file) is False

    def test_yaml_file_not_binary(self, tmp_path):
        """Test that YAML files are not detected as binary."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value\nnumber: 123\n")

        engine = DiffEngine()
        assert engine.is_binary_file(yaml_file) is False


class TestDiffEngineBinaryFileHandling:
    """Tests for binary file handling in comparisons."""

    def test_binary_file_comparison_no_diff_output(self, tmp_path):
        """Test that binary files don't have diff output."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create binary files with different content
        (project_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (store_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x01" * 100)

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["image.png"])

        assert len(changes) == 1
        assert changes[0].is_binary is True
        assert changes[0].diff_output is None

    def test_binary_flag_set_correctly(self, tmp_path):
        """Test that is_binary flag is set correctly for various file types."""
        project_dir = tmp_path / "project"
        store_dir = tmp_path / "store"
        project_dir.mkdir()
        store_dir.mkdir()

        # Create text file
        (project_dir / "readme.md").write_text("# Readme")
        (store_dir / "readme.md").write_text("# Different Readme")

        # Create binary file
        (project_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03")
        (store_dir / "data.bin").write_bytes(b"\x04\x05\x06\x07")

        engine = DiffEngine()
        changes = engine.compare_directories(project_dir, store_dir, ["readme.md", "data.bin"])

        changes_by_path = {c.path: c for c in changes}
        assert changes_by_path["readme.md"].is_binary is False
        assert changes_by_path["data.bin"].is_binary is True
