"""Unit tests for ConflictResolver.

Tests for the ConflictResolver class which handles conflict resolution
between Project and Store files.

Requirements tested:
- 4.1: When a file differs between Project_Directory and Store, mark it as a conflict
- 4.2: Display format `[Conflict] <file_path>`
- 4.3: List all conflicts before prompting for resolution
- 4.4: Display both local and remote versions in the diff output
- 5.1: Prompt for each conflict with options: [l]ocal / [r]emote / [m]erge / [s]kip
- 5.2: When user selects `l` (local), copy Project_Directory version to Store
- 5.3: When user selects `r` (remote), copy Store version to Project_Directory
- 5.5: When user selects `s` (skip), leave both versions unchanged
- 6.1: --local option automatically prefers Project_Directory files
- 6.2: --remote option automatically prefers Store files
- 6.4: Display which files were resolved and how
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from ar_sync.sync.conflict_resolver import ConflictResolver
from ar_sync.sync.merge_engine import MergeEngine
from ar_sync.sync.models import (
    ChangeType,
    FileChange,
    MergeResult,
    Resolution,
    ResolutionStrategy,
    ResolvedChange,
)


@pytest.fixture
def console():
    """Create a Console that captures output."""
    return Console(file=StringIO(), force_terminal=True)


@pytest.fixture
def resolver(console):
    """Create a ConflictResolver with captured output."""
    return ConflictResolver(console=console)


@pytest.fixture
def sample_change(tmp_path):
    """Create a sample FileChange for testing."""
    local_path = tmp_path / "project" / "test.txt"
    remote_path = tmp_path / "store" / "test.txt"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text("local content\n")
    remote_path.write_text("remote content\n")

    return FileChange(
        path="test.txt",
        change_type=ChangeType.MODIFIED,
        local_path=local_path,
        remote_path=remote_path,
        is_binary=False,
        diff_output="--- a/test.txt\n+++ b/test.txt\n@@ -1 +1 @@\n-local content\n+remote content\n",
    )


@pytest.fixture
def binary_change(tmp_path):
    """Create a binary FileChange for testing."""
    local_path = tmp_path / "project" / "image.png"
    remote_path = tmp_path / "store" / "image.png"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    remote_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x01' * 100)

    return FileChange(
        path="image.png",
        change_type=ChangeType.MODIFIED,
        local_path=local_path,
        remote_path=remote_path,
        is_binary=True,
        diff_output="Binary files differ",
    )


class TestConflictResolverInit:
    """Tests for ConflictResolver initialization."""

    def test_init_with_console(self, console):
        """Test initialization with provided console."""
        resolver = ConflictResolver(console=console)
        assert resolver.console is console

    def test_init_without_console(self):
        """Test initialization creates default console."""
        resolver = ConflictResolver()
        assert resolver.console is not None


class TestResolveAutomatic:
    """Tests for automatic conflict resolution (Requirements 6.1, 6.2, 6.4)."""

    def test_resolve_automatic_local_strategy(self, resolver, sample_change):
        """Requirement 6.1: --local option prefers Project_Directory files."""
        result = resolver.resolve_automatic(sample_change, ResolutionStrategy.LOCAL)

        assert isinstance(result, ResolvedChange)
        assert result.file_change is sample_change
        assert result.resolution == Resolution.USE_LOCAL
        assert result.merged_content is None

    def test_resolve_automatic_remote_strategy(self, resolver, sample_change):
        """Requirement 6.2: --remote option prefers Store files."""
        result = resolver.resolve_automatic(sample_change, ResolutionStrategy.REMOTE)

        assert isinstance(result, ResolvedChange)
        assert result.file_change is sample_change
        assert result.resolution == Resolution.USE_REMOTE
        assert result.merged_content is None

    def test_resolve_automatic_interactive_raises_error(self, resolver, sample_change):
        """Test that INTERACTIVE strategy raises ValueError."""
        with pytest.raises(ValueError, match="Cannot use INTERACTIVE strategy"):
            resolver.resolve_automatic(sample_change, ResolutionStrategy.INTERACTIVE)

    def test_resolve_automatic_displays_result(self, resolver, sample_change, console):
        """Requirement 6.4: Display which files were resolved and how."""
        resolver.resolve_automatic(sample_change, ResolutionStrategy.LOCAL)

        output = console.file.getvalue()
        assert "test.txt" in output
        assert "local" in output.lower()


class TestDisplayConflict:
    """Tests for conflict display (Requirements 4.2, 4.4)."""

    def test_display_conflict_shows_path(self, resolver, sample_change, console):
        """Requirement 4.2: Display format `[Conflict] <file_path>`."""
        resolver.display_conflict(sample_change)

        output = console.file.getvalue()
        assert "[Conflict]" in output
        assert "test.txt" in output

    def test_display_conflict_shows_diff(self, resolver, sample_change, console):
        """Requirement 4.4: Display both local and remote versions in diff output."""
        resolver.display_conflict(sample_change)

        output = console.file.getvalue()
        # Diff output should be displayed
        assert "Diff" in output or "diff" in output.lower()

    def test_display_conflict_shows_change_type(self, resolver, sample_change, console):
        """Test that change type is displayed."""
        resolver.display_conflict(sample_change)

        output = console.file.getvalue()
        # Should show some indication of the change type
        assert "modified" in output.lower() or "Type" in output

    def test_display_conflict_shows_file_locations(self, resolver, sample_change, console):
        """Test that file locations are displayed."""
        resolver.display_conflict(sample_change)

        output = console.file.getvalue()
        # Should show local and remote paths
        assert "Local" in output or "local" in output
        assert "Remote" in output or "remote" in output

    def test_display_conflict_binary_warning(self, resolver, binary_change, console):
        """Requirement 5.7: Show warning for binary files."""
        resolver.display_conflict(binary_change)

        output = console.file.getvalue()
        assert "binary" in output.lower()


class TestDisplayConflictsSummary:
    """Tests for conflicts summary display (Requirement 4.3)."""

    def test_display_conflicts_summary_lists_all(self, resolver, console, tmp_path):
        """Requirement 4.3: List all conflicts before prompting for resolution."""
        changes = [
            FileChange(
                path=f"file{i}.txt",
                change_type=ChangeType.MODIFIED,
                local_path=tmp_path / f"local{i}.txt",
                remote_path=tmp_path / f"remote{i}.txt",
                is_binary=False,
            )
            for i in range(3)
        ]

        resolver.display_conflicts_summary(changes)

        output = console.file.getvalue()
        assert "3 conflict" in output.lower()
        assert "file0.txt" in output
        assert "file1.txt" in output
        assert "file2.txt" in output

    def test_display_conflicts_summary_empty_list(self, resolver, console):
        """Test display with no conflicts."""
        resolver.display_conflicts_summary([])

        output = console.file.getvalue()
        assert "No conflicts" in output or "no conflict" in output.lower()

    def test_display_conflicts_summary_shows_binary_indicator(self, resolver, binary_change, console):
        """Test that binary files are indicated in summary."""
        resolver.display_conflicts_summary([binary_change])

        output = console.file.getvalue()
        assert "binary" in output.lower()


class TestPromptResolution:
    """Tests for resolution prompting (Requirement 5.1)."""

    def test_prompt_resolution_local_choice(self, sample_change, console):
        """Requirement 5.1: User can select [l]ocal."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='l'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_LOCAL

    def test_prompt_resolution_remote_choice(self, sample_change, console):
        """Requirement 5.1: User can select [r]emote."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='r'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_REMOTE

    def test_prompt_resolution_merge_choice(self, sample_change, console):
        """Requirement 5.1: User can select [m]erge."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='m'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.MERGE

    def test_prompt_resolution_skip_choice(self, sample_change, console):
        """Requirement 5.1: User can select [s]kip."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='s'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.SKIP

    def test_prompt_resolution_binary_no_merge(self, binary_change, console):
        """Requirement 5.7: Merge option disabled for binary files."""
        resolver = ConflictResolver(console=console)

        # First try 'm', then 'l' when merge is rejected
        inputs = iter(['m', 'l'])
        with patch.object(console, 'input', side_effect=lambda _: next(inputs)):
            result = resolver.prompt_resolution(binary_change)

        # Should end up with local since merge is not available
        assert result == Resolution.USE_LOCAL

    def test_prompt_resolution_invalid_then_valid(self, sample_change, console):
        """Test that invalid input prompts again."""
        resolver = ConflictResolver(console=console)

        # First invalid, then valid
        inputs = iter(['x', 'l'])
        with patch.object(console, 'input', side_effect=lambda _: next(inputs)):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_LOCAL

    def test_prompt_resolution_keyboard_interrupt(self, sample_change, console):
        """Test that Ctrl+C results in skip."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', side_effect=KeyboardInterrupt):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.SKIP

    def test_prompt_resolution_eof(self, sample_change, console):
        """Test that EOF results in skip."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', side_effect=EOFError):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.SKIP

    def test_prompt_resolution_uppercase_input(self, sample_change, console):
        """Test that uppercase input is accepted."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='L'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_LOCAL

    def test_prompt_resolution_word_input(self, sample_change, console):
        """Test that full word input uses first character."""
        resolver = ConflictResolver(console=console)

        with patch.object(console, 'input', return_value='local'):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_LOCAL


class TestResolveInteractive:
    """Tests for interactive conflict resolution."""

    def test_resolve_interactive_local(self, sample_change, console):
        """Requirement 5.2: Local selection returns USE_LOCAL resolution."""
        resolver = ConflictResolver(console=console)
        merge_engine = MergeEngine()

        with patch.object(console, 'input', return_value='l'):
            result = resolver.resolve_interactive(sample_change, merge_engine)

        assert result.resolution == Resolution.USE_LOCAL
        assert result.file_change is sample_change
        assert result.merged_content is None

    def test_resolve_interactive_remote(self, sample_change, console):
        """Requirement 5.3: Remote selection returns USE_REMOTE resolution."""
        resolver = ConflictResolver(console=console)
        merge_engine = MergeEngine()

        with patch.object(console, 'input', return_value='r'):
            result = resolver.resolve_interactive(sample_change, merge_engine)

        assert result.resolution == Resolution.USE_REMOTE
        assert result.file_change is sample_change
        assert result.merged_content is None

    def test_resolve_interactive_skip(self, sample_change, console):
        """Requirement 5.5: Skip selection returns SKIP resolution."""
        resolver = ConflictResolver(console=console)
        merge_engine = MergeEngine()

        with patch.object(console, 'input', return_value='s'):
            result = resolver.resolve_interactive(sample_change, merge_engine)

        assert result.resolution == Resolution.SKIP
        assert result.file_change is sample_change
        assert result.merged_content is None

    def test_resolve_interactive_merge_success(self, sample_change, console):
        """Test successful merge returns merged content."""
        resolver = ConflictResolver(console=console)

        # Mock merge engine to return successful merge
        merge_engine = MagicMock(spec=MergeEngine)
        merge_engine.merge_files.return_value = MergeResult(
            success=True,
            merged_content="merged content\n",
            has_conflicts=False,
            conflict_markers=[],
        )

        with patch.object(console, 'input', return_value='m'):
            result = resolver.resolve_interactive(sample_change, merge_engine)

        assert result.resolution == Resolution.MERGE
        assert result.merged_content == "merged content\n"

    def test_resolve_interactive_merge_with_conflicts(self, sample_change, console):
        """Test merge with conflicts still returns content."""
        resolver = ConflictResolver(console=console)

        # Mock merge engine to return merge with conflicts
        merge_engine = MagicMock(spec=MergeEngine)
        merge_engine.merge_files.return_value = MergeResult(
            success=False,
            merged_content="<<<<<<< local\nlocal\n=======\nremote\n>>>>>>> remote\n",
            has_conflicts=True,
            conflict_markers=[(1, 5)],
        )

        with patch.object(console, 'input', return_value='m'):
            result = resolver.resolve_interactive(sample_change, merge_engine)

        assert result.resolution == Resolution.MERGE
        assert result.merged_content is not None
        assert "<<<<<<" in result.merged_content

    def test_resolve_interactive_displays_conflict(self, sample_change, console):
        """Test that conflict is displayed before prompting."""
        resolver = ConflictResolver(console=console)
        merge_engine = MergeEngine()

        with patch.object(console, 'input', return_value='l'):
            resolver.resolve_interactive(sample_change, merge_engine)

        output = console.file.getvalue()
        assert "[Conflict]" in output
        assert "test.txt" in output


class TestChangeTypeIndicators:
    """Tests for change type display."""

    def test_added_local_indicator(self, resolver, console, tmp_path):
        """Test indicator for files only in project."""
        change = FileChange(
            path="new_local.txt",
            change_type=ChangeType.ADDED_LOCAL,
            local_path=tmp_path / "new_local.txt",
            remote_path=None,
            is_binary=False,
        )

        resolver.display_conflict(change)

        output = console.file.getvalue()
        assert "project" in output.lower() or "local" in output.lower()

    def test_added_remote_indicator(self, resolver, console, tmp_path):
        """Test indicator for files only in store."""
        change = FileChange(
            path="new_remote.txt",
            change_type=ChangeType.ADDED_REMOTE,
            local_path=None,
            remote_path=tmp_path / "new_remote.txt",
            is_binary=False,
        )

        resolver.display_conflict(change)

        output = console.file.getvalue()
        assert "store" in output.lower() or "remote" in output.lower()

    def test_modified_indicator(self, resolver, sample_change, console):
        """Test indicator for modified files."""
        resolver.display_conflict(sample_change)

        output = console.file.getvalue()
        assert "modified" in output.lower() or "both" in output.lower()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_change_without_diff_output(self, resolver, console, tmp_path):
        """Test display when diff_output is None."""
        change = FileChange(
            path="test.txt",
            change_type=ChangeType.MODIFIED,
            local_path=tmp_path / "local.txt",
            remote_path=tmp_path / "remote.txt",
            is_binary=False,
            diff_output=None,
        )

        # Should not raise an error
        resolver.display_conflict(change)

        output = console.file.getvalue()
        assert "[Conflict]" in output

    def test_change_without_local_path(self, resolver, console, tmp_path):
        """Test display when local_path is None."""
        change = FileChange(
            path="remote_only.txt",
            change_type=ChangeType.ADDED_REMOTE,
            local_path=None,
            remote_path=tmp_path / "remote.txt",
            is_binary=False,
        )

        # Should not raise an error
        resolver.display_conflict(change)

        output = console.file.getvalue()
        assert "[Conflict]" in output

    def test_change_without_remote_path(self, resolver, console, tmp_path):
        """Test display when remote_path is None."""
        change = FileChange(
            path="local_only.txt",
            change_type=ChangeType.ADDED_LOCAL,
            local_path=tmp_path / "local.txt",
            remote_path=None,
            is_binary=False,
        )

        # Should not raise an error
        resolver.display_conflict(change)

        output = console.file.getvalue()
        assert "[Conflict]" in output

    def test_merge_without_both_paths(self, console, tmp_path):
        """Test merge fails gracefully when paths are missing."""
        resolver = ConflictResolver(console=console)
        merge_engine = MergeEngine()

        change = FileChange(
            path="test.txt",
            change_type=ChangeType.ADDED_LOCAL,
            local_path=tmp_path / "local.txt",
            remote_path=None,  # Missing remote
            is_binary=False,
        )

        # First try merge, then skip when it fails
        inputs = iter(['m', 's'])
        with patch.object(console, 'input', side_effect=lambda _: next(inputs)):
            result = resolver.resolve_interactive(change, merge_engine)

        # Should fall back to skip
        assert result.resolution == Resolution.SKIP

    def test_empty_input_prompts_again(self, sample_change, console):
        """Test that empty input prompts again."""
        resolver = ConflictResolver(console=console)

        # Empty string, then valid input
        inputs = iter(['', 'l'])
        with patch.object(console, 'input', side_effect=lambda _: next(inputs)):
            result = resolver.prompt_resolution(sample_change)

        assert result == Resolution.USE_LOCAL
