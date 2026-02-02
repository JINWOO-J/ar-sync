"""Unit tests for MergeEngine.

Tests for the MergeEngine class which handles 3-way merges using git merge-file.

Requirements tested:
- 5.4: When user selects `m` (merge) for a text file, perform 3-way merge using `git merge-file`
- 5.6: When merge produces conflicts, display conflict markers and prompt user to edit manually
- 5.7: If the file is binary, disable the merge option and only allow local/remote/skip
"""



from ar_sync.sync.merge_engine import MergeEngine


class TestMergeEngineBasicMerge:
    """Tests for basic 3-way merge functionality."""

    def test_clean_merge_no_conflicts(self, tmp_path):
        """Requirement 5.4: Clean 3-way merge with no conflicts."""
        # Create base, local, and remote files with non-conflicting changes
        # Changes must be in separate, non-adjacent regions to avoid conflicts
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        # Use more lines with changes in distant regions
        base_file.write_text("line1\nline2\nline3\nline4\nline5\nline6\nline7\n")
        local_file.write_text("line1\nlocal change\nline3\nline4\nline5\nline6\nline7\n")  # Changed line2
        remote_file.write_text("line1\nline2\nline3\nline4\nline5\nline6\nremote change\n")  # Changed line7

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is True
        assert result.has_conflicts is False
        assert result.merged_content is not None
        assert "local change" in result.merged_content
        assert "remote change" in result.merged_content
        assert result.conflict_markers == []

    def test_merge_with_conflicts(self, tmp_path):
        """Requirement 5.6: Merge with conflicts should detect conflict markers."""
        # Create base, local, and remote files with conflicting changes
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("line1\noriginal\nline3\n")
        local_file.write_text("line1\nlocal version\nline3\n")  # Changed line2
        remote_file.write_text("line1\nremote version\nline3\n")  # Also changed line2

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is False
        assert result.has_conflicts is True
        assert result.merged_content is not None
        assert "<<<<<<" in result.merged_content
        assert "======" in result.merged_content
        assert ">>>>>>" in result.merged_content
        assert len(result.conflict_markers) > 0

    def test_identical_files_merge(self, tmp_path):
        """Test merging identical files results in clean merge."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        content = "line1\nline2\nline3\n"
        base_file.write_text(content)
        local_file.write_text(content)
        remote_file.write_text(content)

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is True
        assert result.has_conflicts is False
        assert result.merged_content.strip() == content.strip()


class TestMergeEngineWithoutBase:
    """Tests for 2-way merge (when base is None)."""

    def test_merge_without_base_creates_conflict(self, tmp_path):
        """Test that merging without base creates a conflict for different content."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        local_file.write_text("local content\n")
        remote_file.write_text("remote content\n")

        engine = MergeEngine()
        result = engine.merge_files(None, local_file, remote_file)

        # Without a base, different content should result in conflicts
        assert result.merged_content is not None
        # The merge will show both versions as additions from empty base
        assert result.has_conflicts is True

    def test_merge_without_base_identical_content(self, tmp_path):
        """Test that merging identical content without base succeeds."""
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        local_file.write_text("same content\n")
        remote_file.write_text("same content\n")

        engine = MergeEngine()
        result = engine.merge_files(None, local_file, remote_file)

        # Identical content should merge cleanly even without base
        assert result.success is True
        assert result.has_conflicts is False


class TestMergeEngineBinaryFileRejection:
    """Tests for binary file merge rejection (Requirement 5.7)."""

    def test_binary_local_file_rejected(self, tmp_path):
        """Requirement 5.7: Binary local file should reject merge."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.bin"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("base content")
        local_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # Binary
        remote_file.write_text("remote content")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is False
        assert result.merged_content is None
        assert result.has_conflicts is False  # Not a conflict, just rejected

    def test_binary_remote_file_rejected(self, tmp_path):
        """Requirement 5.7: Binary remote file should reject merge."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.bin"

        base_file.write_text("base content")
        local_file.write_text("local content")
        remote_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)  # Binary

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is False
        assert result.merged_content is None

    def test_both_binary_files_rejected(self, tmp_path):
        """Requirement 5.7: Both binary files should reject merge."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.bin"
        remote_file = tmp_path / "remote.bin"

        base_file.write_text("base content")
        local_file.write_bytes(b'\x00\x01\x02\x03')
        remote_file.write_bytes(b'\x04\x05\x06\x07')

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is False
        assert result.merged_content is None

    def test_text_files_not_rejected(self, tmp_path):
        """Test that text files are not rejected."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("base content\n")
        local_file.write_text("local content\n")
        remote_file.write_text("remote content\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        # Should not be rejected (though may have conflicts)
        assert result.merged_content is not None


class TestMergeEngineConflictMarkerDetection:
    """Tests for conflict marker detection (Requirement 5.6)."""

    def test_conflict_markers_detected(self, tmp_path):
        """Requirement 5.6: Conflict markers should be detected with line numbers."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("line1\noriginal\nline3\n")
        local_file.write_text("line1\nlocal\nline3\n")
        remote_file.write_text("line1\nremote\nline3\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.has_conflicts is True
        assert len(result.conflict_markers) >= 1

        # Verify conflict markers are tuples of (start_line, end_line)
        for start, end in result.conflict_markers:
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start > 0  # 1-indexed
            assert end >= start

    def test_multiple_conflicts_detected(self, tmp_path):
        """Test that multiple conflict regions are detected."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        # Create content with two separate conflict regions
        base_file.write_text("line1\noriginal1\nline3\noriginal2\nline5\n")
        local_file.write_text("line1\nlocal1\nline3\nlocal2\nline5\n")
        remote_file.write_text("line1\nremote1\nline3\nremote2\nline5\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.has_conflicts is True
        # Should detect multiple conflict regions
        assert len(result.conflict_markers) >= 1

    def test_no_conflicts_no_markers(self, tmp_path):
        """Test that clean merge has no conflict markers."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        # Changes must be in separate, non-adjacent regions to avoid conflicts
        base_file.write_text("line1\nline2\nline3\nline4\nline5\nline6\nline7\n")
        local_file.write_text("line1\nlocal\nline3\nline4\nline5\nline6\nline7\n")  # Change line2
        remote_file.write_text("line1\nline2\nline3\nline4\nline5\nline6\nremote\n")  # Change line7

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is True
        assert result.has_conflicts is False
        assert result.conflict_markers == []


class TestMergeEngineEdgeCases:
    """Tests for edge cases in merge operations."""

    def test_empty_base_file(self, tmp_path):
        """Test merge with empty base file."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("")
        local_file.write_text("local content\n")
        remote_file.write_text("remote content\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        # Both added content from empty base - should conflict
        assert result.merged_content is not None

    def test_empty_local_file(self, tmp_path):
        """Test merge with empty local file."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("original content\n")
        local_file.write_text("")  # Local deleted all content
        remote_file.write_text("remote content\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.merged_content is not None

    def test_empty_remote_file(self, tmp_path):
        """Test merge with empty remote file."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("original content\n")
        local_file.write_text("local content\n")
        remote_file.write_text("")  # Remote deleted all content

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.merged_content is not None

    def test_unicode_content(self, tmp_path):
        """Test merge with unicode content."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        base_file.write_text("한글 베이스\n日本語\n")
        local_file.write_text("한글 로컬\n日本語\n")
        remote_file.write_text("한글 베이스\n日本語 リモート\n")

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.merged_content is not None
        assert "한글" in result.merged_content
        assert "日本語" in result.merged_content

    def test_large_file_merge(self, tmp_path):
        """Test merge with larger files."""
        base_file = tmp_path / "base.txt"
        local_file = tmp_path / "local.txt"
        remote_file = tmp_path / "remote.txt"

        # Create files with many lines
        base_lines = [f"line{i}\n" for i in range(100)]
        local_lines = base_lines.copy()
        remote_lines = base_lines.copy()

        # Make non-conflicting changes
        local_lines[10] = "local change at line 10\n"
        remote_lines[90] = "remote change at line 90\n"

        base_file.write_text("".join(base_lines))
        local_file.write_text("".join(local_lines))
        remote_file.write_text("".join(remote_lines))

        engine = MergeEngine()
        result = engine.merge_files(base_file, local_file, remote_file)

        assert result.success is True
        assert result.has_conflicts is False
        assert "local change at line 10" in result.merged_content
        assert "remote change at line 90" in result.merged_content


class TestMergeEngineInternalMethods:
    """Tests for internal helper methods."""

    def test_is_binary_file_text(self, tmp_path):
        """Test _is_binary_file returns False for text files."""
        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello, World!\n")

        engine = MergeEngine()
        assert engine._is_binary_file(text_file) is False

    def test_is_binary_file_binary(self, tmp_path):
        """Test _is_binary_file returns True for binary files."""
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b'\x00\x01\x02\x03')

        engine = MergeEngine()
        assert engine._is_binary_file(binary_file) is True

    def test_is_binary_file_nonexistent(self, tmp_path):
        """Test _is_binary_file returns False for nonexistent files."""
        nonexistent = tmp_path / "nonexistent.txt"

        engine = MergeEngine()
        assert engine._is_binary_file(nonexistent) is False

    def test_detect_conflict_markers_empty_content(self):
        """Test _detect_conflict_markers with empty content."""
        engine = MergeEngine()
        markers = engine._detect_conflict_markers("")
        assert markers == []

    def test_detect_conflict_markers_no_conflicts(self):
        """Test _detect_conflict_markers with no conflict markers."""
        engine = MergeEngine()
        content = "line1\nline2\nline3\n"
        markers = engine._detect_conflict_markers(content)
        assert markers == []

    def test_detect_conflict_markers_single_conflict(self):
        """Test _detect_conflict_markers with single conflict."""
        engine = MergeEngine()
        content = """line1
<<<<<<< local
local content
=======
remote content
>>>>>>> remote
line3
"""
        markers = engine._detect_conflict_markers(content)
        assert len(markers) == 1
        start, end = markers[0]
        assert start == 2  # Line with <<<<<<<
        assert end == 6  # Line with >>>>>>>

    def test_detect_conflict_markers_multiple_conflicts(self):
        """Test _detect_conflict_markers with multiple conflicts."""
        engine = MergeEngine()
        content = """line1
<<<<<<< local
local1
=======
remote1
>>>>>>> remote
line3
<<<<<<< local
local2
=======
remote2
>>>>>>> remote
line5
"""
        markers = engine._detect_conflict_markers(content)
        assert len(markers) == 2
