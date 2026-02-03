"""Unit tests for GitBackend."""

from unittest.mock import patch

import pytest
from git import Repo

from ar_sync.git_backend import GitBackend


class TestGitBackendVerifyRemoteAccess:
    """Tests for GitBackend.verify_remote_access()."""

    def test_verify_remote_access_success(self):
        """Test that verify_remote_access returns True when remote is accessible."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == [
                "git",
                "ls-remote",
                "--exit-code",
                "git@github.com:user/repo.git",
            ]
            assert call_args[1]["timeout"] == 10

    def test_verify_remote_access_failure(self):
        """Test that verify_remote_access returns False when remote is not accessible."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 128
            result = GitBackend.verify_remote_access("git@github.com:user/nonexistent.git")
            assert result is False

    def test_verify_remote_access_timeout(self):
        """Test that verify_remote_access returns False on timeout."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
            result = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert result is False

    def test_verify_remote_access_subprocess_error(self):
        """Test that verify_remote_access returns False on subprocess error."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Command failed")
            result = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert result is False

    def test_verify_remote_access_os_error(self):
        """Test that verify_remote_access returns False when git is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("git not found")
            result = GitBackend.verify_remote_access("git@github.com:user/repo.git")
            assert result is False


class TestGitBackendInitialize:
    """Tests for GitBackend.initialize()."""

    def test_initialize_creates_new_repo(self, tmp_path):
        """Test that initialize creates a new Git repository."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        assert store_path.exists()
        assert (store_path / ".git").exists()
        assert backend.repo is not None
        assert not backend.repo.bare

    def test_initialize_opens_existing_repo(self, tmp_path):
        """Test that initialize opens an existing Git repository."""
        store_path = tmp_path / "store"
        store_path.mkdir()

        # Create a Git repository manually
        Repo.init(store_path)

        repo_url = "git@github.com:user/repo.git"
        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        assert backend.repo is not None
        assert not backend.repo.bare

    def test_initialize_adds_remote(self, tmp_path):
        """Test that initialize adds remote to new repository."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        assert "origin" in [remote.name for remote in backend.repo.remotes]
        assert backend.repo.remotes.origin.url == repo_url

    def test_initialize_does_not_duplicate_remote(self, tmp_path):
        """Test that initialize does not duplicate remote if it already exists."""
        store_path = tmp_path / "store"
        store_path.mkdir()
        repo_url = "git@github.com:user/repo.git"

        # Create repo with remote
        repo = Repo.init(store_path)
        repo.create_remote("origin", repo_url)

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Should have exactly one origin remote
        origin_remotes = [r for r in backend.repo.remotes if r.name == "origin"]
        assert len(origin_remotes) == 1


class TestGitBackendCommitAndPush:
    """Tests for GitBackend.commit_and_push()."""

    def test_commit_and_push_with_no_changes(self, tmp_path):
        """Test that commit_and_push does nothing when there are no changes."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Should not raise an error
        backend.commit_and_push()

    def test_commit_and_push_with_changes(self, tmp_path):
        """Test that commit_and_push commits changes."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Create a file
        test_file = store_path / "test.txt"
        test_file.write_text("test content")

        # Commit (push will fail without remote, but commit should work)
        try:
            backend.commit_and_push("Test commit")
        except RuntimeError as e:
            # Push will fail, but commit should have succeeded
            assert "Failed to push to remote" in str(e)

        # Verify commit was created
        assert len(list(backend.repo.iter_commits())) > 0
        assert backend.repo.head.commit.message == "Test commit"

    def test_commit_and_push_with_default_message(self, tmp_path):
        """Test that commit_and_push uses default message when none provided."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Create a file
        test_file = store_path / "test.txt"
        test_file.write_text("test content")

        # Commit with default message
        try:
            backend.commit_and_push()
        except RuntimeError:
            # Push will fail, but commit should have succeeded
            pass

        # Verify default message format
        commit_message = backend.repo.head.commit.message
        assert "Auto-sync from" in commit_message
        assert "at" in commit_message

    def test_commit_and_push_without_initialize(self, tmp_path):
        """Test that commit_and_push raises error if not initialized."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)

        with pytest.raises(RuntimeError, match="Repository not initialized"):
            backend.commit_and_push()


class TestGitBackendPull:
    """Tests for GitBackend.pull()."""

    def test_pull_without_initialize(self, tmp_path):
        """Test that pull raises error if not initialized."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)

        with pytest.raises(RuntimeError, match="Repository not initialized"):
            backend.pull()

    def test_pull_without_remote(self, tmp_path):
        """Test that pull raises error when remote is not available."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Pull will fail without a real remote
        with pytest.raises(RuntimeError, match="Failed to pull from remote"):
            backend.pull()

    def test_pull_with_unstaged_changes_auto_commits(self, tmp_path):
        """Test that pull automatically commits unstaged changes before pulling."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Create a test file and commit it
        test_file = store_path / "test.txt"
        test_file.write_text("test content")
        backend.repo.index.add([str(test_file)])
        backend.repo.index.commit("Initial commit")

        # Modify the file to create unstaged changes
        test_file.write_text("modified content")

        # Verify there are unstaged changes
        assert backend.repo.is_dirty(untracked_files=False)

        # Pull should auto-commit the changes (will fail on actual pull, but commit should happen)
        try:
            backend.pull()
        except RuntimeError:
            # Pull will fail because there's no real remote, but that's OK
            pass

        # Verify the changes were auto-committed
        assert not backend.repo.is_dirty(untracked_files=False)
        assert "Auto-commit before sync" in backend.repo.head.commit.message


class TestGitBackendSync:
    """Tests for GitBackend.sync()."""

    def test_sync_pull_only(self, tmp_path):
        """Test that sync with pull_only=True only pulls (and auto-commits if needed)."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Create a file (will be auto-committed during pull)
        test_file = store_path / "test.txt"
        test_file.write_text("test content")

        # Sync with pull_only (will auto-commit, then fail on pull)
        with pytest.raises(RuntimeError):
            backend.sync(pull_only=True)

        # Verify the file was auto-committed (repo is clean now)
        assert not backend.repo.is_dirty(untracked_files=True)
        # Verify a commit was made
        assert len(list(backend.repo.iter_commits())) > 0
        assert "Auto-commit before sync" in backend.repo.head.commit.message

    def test_sync_push_only(self, tmp_path):
        """Test that sync with push_only=True only pushes."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)
        backend.initialize()

        # Create a file
        test_file = store_path / "test.txt"
        test_file.write_text("test content")

        # Sync with push_only (will fail on push, but should commit)
        try:
            backend.sync(push_only=True)
        except RuntimeError:
            pass

        # Verify commit was made
        assert len(list(backend.repo.iter_commits())) > 0

    def test_sync_without_initialize(self, tmp_path):
        """Test that sync raises error if not initialized."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)

        with pytest.raises(RuntimeError, match="Repository not initialized"):
            backend.sync()


class TestGitBackendVerify:
    """Tests for GitBackend._verify_repo()."""

    def test_verify_repo_not_initialized(self, tmp_path):
        """Test that _verify_repo raises error if repo is None."""
        store_path = tmp_path / "store"
        repo_url = "git@github.com:user/repo.git"

        backend = GitBackend(store_path, repo_url)

        with pytest.raises(RuntimeError, match="Repository not initialized"):
            backend._verify_repo()
