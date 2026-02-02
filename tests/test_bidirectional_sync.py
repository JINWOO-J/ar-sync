"""
Unit tests for BidirectionalSync orchestrator.

Tests the main synchronization flow including:
- Pull phase
- Change detection
- Conflict resolution
- Apply changes
- Push phase
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from ar_sync.sync.bidirectional_sync import BidirectionalSync
from ar_sync.sync.models import (
    ChangeType,
    FileChange,
    Resolution,
    ResolutionStrategy,
    ResolvedChange,
    SyncOptions,
    SyncResult,
)


class TestBidirectionalSyncInit:
    """Test BidirectionalSync initialization."""
    
    def test_init_with_required_params(self, tmp_path: Path):
        """Test initialization with required parameters only."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro", "AGENTS.md"],
        )
        
        assert sync.project_dir == project_dir
        assert sync.store_path == store_path
        assert sync.project_name == "test-project"
        assert sync.targets == [".kiro", "AGENTS.md"]
        assert sync.git_backend is None
        assert sync.diff_engine is not None
        assert sync.merge_engine is not None
        assert sync.conflict_resolver is not None
    
    def test_init_with_git_backend(self, tmp_path: Path):
        """Test initialization with git backend."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        assert sync.git_backend is mock_backend


class TestSyncNoChanges:
    """Test sync when no changes are detected."""
    
    def test_sync_no_changes_displays_up_to_date(self, tmp_path: Path):
        """When no changes exist, should display 'already in sync' message."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create identical files in both directories
        (project_dir / "test.txt").write_text("same content")
        (store_path / "test.txt").write_text("same content")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        options = SyncOptions()
        result = sync.sync(options)
        
        assert result.conflicts_resolved == 0
        assert result.skipped_files == []
        assert result.errors == []


class TestSyncDiffOnly:
    """Test sync with diff_only option."""
    
    def test_diff_only_does_not_modify_files(self, tmp_path: Path):
        """Validates: Requirement 3.3 - diff option displays without sync."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create different files
        project_file = project_dir / "test.txt"
        store_file = store_path / "test.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")
        
        # Record initial state
        initial_project = project_file.read_text()
        initial_store = store_file.read_text()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        options = SyncOptions(diff_only=True)
        result = sync.sync(options)
        
        # Verify no changes were made
        assert project_file.read_text() == initial_project
        assert store_file.read_text() == initial_store
        assert result.conflicts_resolved == 0


class TestSyncDryRun:
    """Test sync with dry_run option."""
    
    def test_dry_run_does_not_modify_files(self, tmp_path: Path):
        """Validates: Requirement 7.4 - dry-run does not modify files."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create different files
        project_file = project_dir / "test.txt"
        store_file = store_path / "test.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")
        
        # Record initial state
        initial_project = project_file.read_text()
        initial_store = store_file.read_text()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        # Use automatic LOCAL strategy to avoid interactive prompts
        options = SyncOptions(dry_run=True, strategy=ResolutionStrategy.LOCAL)
        result = sync.sync(options)
        
        # Verify no changes were made
        assert project_file.read_text() == initial_project
        assert store_file.read_text() == initial_store


class TestPullPhase:
    """Test pull phase operations."""
    
    def test_pull_phase_without_git_backend(self, tmp_path: Path):
        """Pull phase should return 0 when no git backend is configured."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
        )
        
        options = SyncOptions()
        pulled = sync._pull_phase(options)
        
        assert pulled == 0
    
    def test_pull_phase_with_git_backend(self, tmp_path: Path):
        """Pull phase should call git backend pull method."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.pull.return_value = {'pulled': True, 'files_changed': 3}
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        options = SyncOptions()
        pulled = sync._pull_phase(options)
        
        assert pulled == 3
        mock_backend.pull.assert_called_once()
    
    def test_pull_phase_displays_up_to_date(self, tmp_path: Path):
        """Validates: Requirement 1.3 - display 'already up to date' when no changes."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.pull.return_value = {'pulled': True, 'files_changed': 0}
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        options = SyncOptions()
        pulled = sync._pull_phase(options)
        
        assert pulled == 0


class TestPushPhase:
    """Test push phase operations."""
    
    def test_push_phase_without_git_backend(self, tmp_path: Path):
        """Push phase should return 0 when no git backend is configured."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
        )
        
        pushed = sync._push_phase([])
        
        assert pushed == 0
    
    def test_push_phase_skips_when_no_changes(self, tmp_path: Path):
        """Validates: Requirement 8.5 - skip commit and push when no changes."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        pushed = sync._push_phase([])
        
        assert pushed == 0
        mock_backend.commit_and_push.assert_not_called()
    
    def test_push_phase_commits_with_descriptive_message(self, tmp_path: Path):
        """Validates: Requirement 8.1, 8.2 - commit with descriptive message including file list."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.commit_and_push.return_value = {
            'committed': True,
            'files_changed': 2,
            'pushed': True,
        }
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        # Create resolved changes
        resolved = [
            ResolvedChange(
                file_change=FileChange(
                    path="test1.txt",
                    change_type=ChangeType.MODIFIED,
                    local_path=project_dir / "test1.txt",
                    remote_path=store_path / "test1.txt",
                ),
                resolution=Resolution.USE_LOCAL,
            ),
            ResolvedChange(
                file_change=FileChange(
                    path="test2.txt",
                    change_type=ChangeType.ADDED_LOCAL,
                    local_path=project_dir / "test2.txt",
                    remote_path=None,
                ),
                resolution=Resolution.USE_LOCAL,
            ),
        ]
        
        pushed = sync._push_phase(resolved)
        
        assert pushed == 2
        mock_backend.commit_and_push.assert_called_once()
        
        # Verify commit message contains file list
        call_args = mock_backend.commit_and_push.call_args
        # commit_and_push is called with message=... keyword argument
        message = call_args.kwargs.get('message')
        if message is None and call_args.args:
            message = call_args.args[0]
        
        assert message is not None, f"Expected message in call_args: {call_args}"
        assert "test1.txt" in message
        assert "test2.txt" in message


class TestApplyChanges:
    """Test file operation application."""
    
    def test_apply_use_local_copies_to_store(self, tmp_path: Path):
        """Validates: Requirement 5.2 - local selection copies Project to Store."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create project file
        project_file = project_dir / "test.txt"
        project_file.write_text("local content")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=project_file,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify file was copied to store
        store_file = store_path / "test.txt"
        assert store_file.exists()
        assert store_file.read_text() == "local content"
    
    def test_apply_use_remote_copies_to_project(self, tmp_path: Path):
        """Validates: Requirement 5.3 - remote selection copies Store to Project."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create store file
        store_file = store_path / "test.txt"
        store_file.write_text("remote content")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_REMOTE,
                local_path=None,
                remote_path=store_file,
            ),
            resolution=Resolution.USE_REMOTE,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify file was copied to project
        project_file = project_dir / "test.txt"
        assert project_file.exists()
        assert project_file.read_text() == "remote content"
    
    def test_apply_skip_does_nothing(self, tmp_path: Path):
        """Validates: Requirement 5.5 - skip leaves both versions unchanged."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create different files
        project_file = project_dir / "test.txt"
        store_file = store_path / "test.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = [
            ResolvedChange(
                file_change=FileChange(
                    path="test.txt",
                    change_type=ChangeType.MODIFIED,
                    local_path=project_file,
                    remote_path=store_file,
                ),
                resolution=Resolution.SKIP,
            )
        ]
        
        applied = sync._apply_changes(resolved)
        
        # Verify no changes were made
        assert project_file.read_text() == "local content"
        assert store_file.read_text() == "remote content"
        assert len(applied) == 0
    
    def test_apply_merge_writes_to_both(self, tmp_path: Path):
        """Test that merge resolution writes content to both locations."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create files
        project_file = project_dir / "test.txt"
        store_file = store_path / "test.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.MODIFIED,
                local_path=project_file,
                remote_path=store_file,
            ),
            resolution=Resolution.MERGE,
            merged_content="merged content",
        )
        
        sync._apply_single_change(resolved)
        
        # Verify merged content was written to both
        assert project_file.read_text() == "merged content"
        assert store_file.read_text() == "merged content"


class TestCommitMessage:
    """Test commit message generation."""
    
    def test_build_commit_message_includes_files(self, tmp_path: Path):
        """Validates: Requirement 8.2 - include list of synced files in commit message."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
        )
        
        resolved = [
            ResolvedChange(
                file_change=FileChange(
                    path=".kiro/config.yaml",
                    change_type=ChangeType.MODIFIED,
                    local_path=project_dir / ".kiro/config.yaml",
                    remote_path=store_path / ".kiro/config.yaml",
                ),
                resolution=Resolution.USE_LOCAL,
            ),
            ResolvedChange(
                file_change=FileChange(
                    path="AGENTS.md",
                    change_type=ChangeType.ADDED_LOCAL,
                    local_path=project_dir / "AGENTS.md",
                    remote_path=None,
                ),
                resolution=Resolution.USE_LOCAL,
            ),
        ]
        
        message = sync._build_commit_message(resolved)
        
        assert ".kiro/config.yaml" in message
        assert "AGENTS.md" in message
        assert "local" in message  # Resolution type


class TestMetadataPreservation:
    """Test file metadata preservation during sync operations.
    
    Validates:
    - Requirement 10.1: Preserve file permissions (chmod)
    - Requirement 10.2: Preserve file modification timestamps
    - Requirement 10.3: Preserve directory structure and permissions
    """
    
    def test_copy_to_store_preserves_file_permissions(self, tmp_path: Path):
        """Validates: Requirement 10.1 - preserve file permissions when copying to store."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create project file with specific permissions
        project_file = project_dir / "script.sh"
        project_file.write_text("#!/bin/bash\necho hello")
        project_file.chmod(0o755)  # Executable permission
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["script.sh"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="script.sh",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=project_file,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify permissions are preserved
        store_file = store_path / "script.sh"
        assert store_file.exists()
        assert (store_file.stat().st_mode & 0o777) == 0o755
    
    def test_copy_to_project_preserves_file_permissions(self, tmp_path: Path):
        """Validates: Requirement 10.1 - preserve file permissions when copying to project."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create store file with specific permissions
        store_file = store_path / "script.sh"
        store_file.write_text("#!/bin/bash\necho hello")
        store_file.chmod(0o755)  # Executable permission
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["script.sh"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="script.sh",
                change_type=ChangeType.ADDED_REMOTE,
                local_path=None,
                remote_path=store_file,
            ),
            resolution=Resolution.USE_REMOTE,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify permissions are preserved
        project_file = project_dir / "script.sh"
        assert project_file.exists()
        assert (project_file.stat().st_mode & 0o777) == 0o755
    
    def test_copy_to_store_preserves_modification_timestamp(self, tmp_path: Path):
        """Validates: Requirement 10.2 - preserve modification timestamps when copying to store."""
        import os
        import time
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create project file with specific timestamp
        project_file = project_dir / "test.txt"
        project_file.write_text("content")
        
        # Set a specific modification time (1 hour ago)
        old_mtime = time.time() - 3600
        os.utime(project_file, (old_mtime, old_mtime))
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=project_file,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify timestamp is preserved (within 1 second tolerance)
        store_file = store_path / "test.txt"
        assert store_file.exists()
        assert abs(store_file.stat().st_mtime - old_mtime) < 1
    
    def test_copy_to_project_preserves_modification_timestamp(self, tmp_path: Path):
        """Validates: Requirement 10.2 - preserve modification timestamps when copying to project."""
        import os
        import time
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create store file with specific timestamp
        store_file = store_path / "test.txt"
        store_file.write_text("content")
        
        # Set a specific modification time (1 hour ago)
        old_mtime = time.time() - 3600
        os.utime(store_file, (old_mtime, old_mtime))
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_REMOTE,
                local_path=None,
                remote_path=store_file,
            ),
            resolution=Resolution.USE_REMOTE,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify timestamp is preserved (within 1 second tolerance)
        project_file = project_dir / "test.txt"
        assert project_file.exists()
        assert abs(project_file.stat().st_mtime - old_mtime) < 1
    
    def test_copy_directory_preserves_structure_and_permissions(self, tmp_path: Path):
        """Validates: Requirement 10.3 - preserve directory structure and permissions."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create directory structure in project
        kiro_dir = project_dir / ".kiro"
        kiro_dir.mkdir()
        (kiro_dir / "config.yaml").write_text("key: value")
        (kiro_dir / "config.yaml").chmod(0o644)
        
        specs_dir = kiro_dir / "specs"
        specs_dir.mkdir()
        (specs_dir / "feature.md").write_text("# Feature")
        (specs_dir / "feature.md").chmod(0o644)
        
        # Set directory permissions
        specs_dir.chmod(0o755)
        kiro_dir.chmod(0o755)
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path=".kiro",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=kiro_dir,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        sync._apply_single_change(resolved)
        
        # Verify directory structure is preserved
        store_kiro = store_path / ".kiro"
        assert store_kiro.exists()
        assert store_kiro.is_dir()
        assert (store_kiro / "config.yaml").exists()
        assert (store_kiro / "specs" / "feature.md").exists()
        
        # Verify file permissions are preserved
        assert (store_kiro / "config.yaml").stat().st_mode & 0o777 == 0o644
        assert (store_kiro / "specs" / "feature.md").stat().st_mode & 0o777 == 0o644
    
    def test_merge_preserves_original_file_permissions(self, tmp_path: Path):
        """Validates: Requirement 10.1 - preserve permissions when writing merged content."""
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create files with specific permissions
        project_file = project_dir / "script.sh"
        store_file = store_path / "script.sh"
        project_file.write_text("#!/bin/bash\necho local")
        store_file.write_text("#!/bin/bash\necho remote")
        project_file.chmod(0o755)
        store_file.chmod(0o755)
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["script.sh"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="script.sh",
                change_type=ChangeType.MODIFIED,
                local_path=project_file,
                remote_path=store_file,
            ),
            resolution=Resolution.MERGE,
            merged_content="#!/bin/bash\necho merged",
        )
        
        sync._apply_single_change(resolved)
        
        # Verify permissions are preserved after merge
        assert (project_file.stat().st_mode & 0o777) == 0o755
        assert (store_file.stat().st_mode & 0o777) == 0o755
    
    def test_merge_preserves_original_modification_timestamp(self, tmp_path: Path):
        """Validates: Requirement 10.2 - preserve timestamps when writing merged content."""
        import os
        import time
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create files with specific timestamps
        project_file = project_dir / "test.txt"
        store_file = store_path / "test.txt"
        project_file.write_text("local content")
        store_file.write_text("remote content")
        
        # Set specific modification time (1 hour ago)
        old_mtime = time.time() - 3600
        os.utime(project_file, (old_mtime, old_mtime))
        os.utime(store_file, (old_mtime, old_mtime))
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.MODIFIED,
                local_path=project_file,
                remote_path=store_file,
            ),
            resolution=Resolution.MERGE,
            merged_content="merged content",
        )
        
        sync._apply_single_change(resolved)
        
        # Verify timestamps are preserved (within 1 second tolerance)
        assert abs(project_file.stat().st_mtime - old_mtime) < 1
        assert abs(store_file.stat().st_mtime - old_mtime) < 1


class TestErrorHandling:
    """Test error handling in sync operations.
    
    Validates:
    - Requirement 1.4: Display error message with recovery steps on network error
    - Requirement 1.5: Display instructions for manual resolution on Git conflict
    - Requirement 8.4: Display error message with recovery steps on push failure
    - Requirement 11.1: Display the specific file and error reason
    - Requirement 11.3: Provide actionable recovery steps
    """
    
    def test_pull_phase_network_error_raises_sync_error(self, tmp_path: Path):
        """Validates: Requirement 1.4 - network error displays error with recovery steps."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.pull.side_effect = RuntimeError("fatal: unable to access remote")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        options = SyncOptions()
        
        with pytest.raises(SyncError) as exc_info:
            sync._pull_phase(options)
        
        assert exc_info.value.category == ErrorCategory.GIT
        assert "network" in exc_info.value.message.lower() or "fatal" in exc_info.value.message.lower()
        assert len(exc_info.value.recovery_steps) > 0
    
    def test_pull_phase_git_conflict_raises_sync_error(self, tmp_path: Path):
        """Validates: Requirement 1.5 - Git conflict displays instructions for manual resolution."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.pull.side_effect = RuntimeError("CONFLICT (content): Merge conflict in file.txt")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        options = SyncOptions()
        
        with pytest.raises(SyncError) as exc_info:
            sync._pull_phase(options)
        
        assert exc_info.value.category == ErrorCategory.GIT
        assert "conflict" in exc_info.value.message.lower()
        assert len(exc_info.value.recovery_steps) > 0
    
    def test_push_phase_network_error_raises_sync_error(self, tmp_path: Path):
        """Validates: Requirement 8.4 - push failure displays error with recovery steps."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.commit_and_push.side_effect = RuntimeError("fatal: unable to access remote")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        # Create resolved changes
        resolved = [
            ResolvedChange(
                file_change=FileChange(
                    path="test.txt",
                    change_type=ChangeType.MODIFIED,
                    local_path=project_dir / "test.txt",
                    remote_path=store_path / "test.txt",
                ),
                resolution=Resolution.USE_LOCAL,
            ),
        ]
        
        with pytest.raises(SyncError) as exc_info:
            sync._push_phase(resolved)
        
        assert exc_info.value.category == ErrorCategory.GIT
        assert len(exc_info.value.recovery_steps) > 0
    
    def test_apply_single_change_permission_error_raises_sync_error(self, tmp_path: Path):
        """Validates: Requirement 11.1 - file operation failure displays specific file and error."""
        from ar_sync.errors import SyncError, ErrorCategory
        import os
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create project file
        project_file = project_dir / "test.txt"
        project_file.write_text("local content")
        
        # Make store directory read-only to cause permission error
        store_path.chmod(0o444)
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=project_file,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        try:
            with pytest.raises(SyncError) as exc_info:
                sync._apply_single_change(resolved)
            
            assert exc_info.value.category == ErrorCategory.FILE_SYSTEM
            assert exc_info.value.file_path == "test.txt"
            assert len(exc_info.value.recovery_steps) > 0
        finally:
            # Restore permissions for cleanup
            store_path.chmod(0o755)
    
    def test_apply_single_change_io_error_includes_file_path(self, tmp_path: Path):
        """Validates: Requirement 11.1, 11.3 - error includes file path and recovery steps."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        # Create a file change with non-existent local path
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=["test.txt"],
        )
        
        # Create a change pointing to a non-existent file
        non_existent_path = project_dir / "non_existent.txt"
        
        resolved = ResolvedChange(
            file_change=FileChange(
                path="test.txt",
                change_type=ChangeType.ADDED_LOCAL,
                local_path=non_existent_path,
                remote_path=None,
            ),
            resolution=Resolution.USE_LOCAL,
        )
        
        with pytest.raises(SyncError) as exc_info:
            sync._apply_single_change(resolved)
        
        assert exc_info.value.category == ErrorCategory.FILE_SYSTEM
        assert exc_info.value.file_path == "test.txt"
        assert len(exc_info.value.recovery_steps) > 0
    
    def test_sync_error_format_includes_recovery_steps(self, tmp_path: Path):
        """Validates: Requirement 11.3 - error provides actionable recovery steps."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        error = SyncError(
            message="Permission denied",
            category=ErrorCategory.FILE_SYSTEM,
            file_path="test.txt",
        )
        
        formatted = error.format_error()
        
        assert "Permission denied" in formatted
        assert "test.txt" in formatted
        assert "resolve" in formatted.lower() or "To resolve" in formatted
    
    def test_pull_phase_generic_runtime_error_raises_sync_error(self, tmp_path: Path):
        """Test that generic RuntimeError is wrapped in SyncError."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.pull.side_effect = RuntimeError("Unknown git error")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        options = SyncOptions()
        
        with pytest.raises(SyncError) as exc_info:
            sync._pull_phase(options)
        
        assert exc_info.value.category == ErrorCategory.GIT
        assert "Unknown git error" in exc_info.value.message
    
    def test_push_phase_authentication_error_raises_sync_error(self, tmp_path: Path):
        """Test that authentication errors are properly handled."""
        from ar_sync.errors import SyncError, ErrorCategory
        
        project_dir = tmp_path / "project"
        store_path = tmp_path / "store"
        project_dir.mkdir()
        store_path.mkdir()
        
        mock_backend = Mock()
        mock_backend.commit_and_push.side_effect = RuntimeError("Authentication failed for remote")
        
        sync = BidirectionalSync(
            project_dir=project_dir,
            store_path=store_path,
            project_name="test-project",
            targets=[".kiro"],
            git_backend=mock_backend,
        )
        
        resolved = [
            ResolvedChange(
                file_change=FileChange(
                    path="test.txt",
                    change_type=ChangeType.MODIFIED,
                    local_path=project_dir / "test.txt",
                    remote_path=store_path / "test.txt",
                ),
                resolution=Resolution.USE_LOCAL,
            ),
        ]
        
        with pytest.raises(SyncError) as exc_info:
            sync._push_phase(resolved)
        
        assert exc_info.value.category == ErrorCategory.GIT
        assert "authentication" in exc_info.value.message.lower()
