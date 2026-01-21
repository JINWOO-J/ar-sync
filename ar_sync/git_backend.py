"""Git backend implementation for ar-sync."""

import socket
from datetime import datetime, timezone
from pathlib import Path

try:
    from git import GitCommandError, Repo
except ImportError:
    raise ImportError(
        "GitPython is required for git backend. "
        "Install it with: pip install GitPython"
    )


class GitBackend:
    """Git backend for managing repository operations."""

    def __init__(self, store_path: Path, repo_url: str):
        """
        Initialize Git backend.

        Args:
            store_path: Path to the local store directory
            repo_url: URL of the remote Git repository
        """
        self.store_path = Path(store_path)
        self.repo_url = repo_url
        self.repo: Repo | None = None

    def initialize(self) -> None:
        """
        Initialize Git repository at store path.

        If the store path already contains a Git repository, it will be opened.
        Otherwise, a new repository will be created and the remote will be added.

        Raises:
            RuntimeError: If repository initialization fails
            ValueError: If repository is bare
        """
        git_dir = self.store_path / ".git"

        if self.store_path.exists() and git_dir.exists():
            # Repository already exists, just open it
            self.repo = Repo(self.store_path)
            self._verify_repo()
        else:
            # Create new repository
            self.store_path.mkdir(parents=True, exist_ok=True)
            self.repo = Repo.init(self.store_path)

            # Add remote
            if 'origin' not in [remote.name for remote in self.repo.remotes]:
                self.repo.create_remote('origin', self.repo_url)

    def _verify_repo(self) -> None:
        """
        Verify repository is valid.

        Raises:
            RuntimeError: If repository is not initialized
            ValueError: If repository is bare
        """
        if self.repo is None:
            raise RuntimeError("Repository not initialized")

        if self.repo.bare:
            raise ValueError("Store repository cannot be bare")

    def commit_and_push(self, message: str | None = None) -> dict[str, bool | int]:
        """
        Commit all changes and push to remote.

        Args:
            message: Commit message. If None, a default message will be generated.

        Returns:
            Dictionary with 'committed' (bool), 'files_changed' (int), 'pushed' (bool)

        Raises:
            RuntimeError: If repository is not initialized or push fails
        """
        if self.repo is None:
            raise RuntimeError("Repository not initialized")

        result = {'committed': False, 'files_changed': 0, 'pushed': False}

        # Check if there are changes
        if not self.repo.is_dirty(untracked_files=True):
            return result

        # Count changed files
        changed_files = len(self.repo.index.diff(None)) + len(self.repo.untracked_files)
        result['files_changed'] = changed_files

        # Add all changes
        self.repo.index.add('*')

        # Create commit
        if message is None:
            hostname = socket.gethostname()
            timestamp = datetime.now(timezone.utc).isoformat()
            message = f"Auto-sync from {hostname} at {timestamp}"

        self.repo.index.commit(message)
        result['committed'] = True

        # Push to remote
        try:
            origin = self.repo.remotes.origin
            # Get current branch name (usually 'master' or 'main')
            if self.repo.heads:
                current_branch = self.repo.active_branch.name
                origin.push(f'{current_branch}:{current_branch}', set_upstream=True)
                result['pushed'] = True
        except GitCommandError as e:
            raise RuntimeError(f"Failed to push to remote: {e}")

        return result

    def pull(self) -> dict[str, bool | int]:
        """
        Pull changes from remote.

        Returns:
            Dictionary with 'pulled' (bool) and 'files_changed' (int)

        Raises:
            RuntimeError: If repository is not initialized or pull fails
        """
        if self.repo is None:
            raise RuntimeError("Repository not initialized")

        result = {'pulled': False, 'files_changed': 0}

        # Get current HEAD before pull
        try:
            old_commit = self.repo.head.commit if self.repo.heads else None
        except Exception:
            old_commit = None

        try:
            origin = self.repo.remotes.origin
            # Get current branch name dynamically (usually 'master' or 'main')
            if self.repo.heads:
                current_branch = self.repo.active_branch.name
                pull_info = origin.pull(current_branch)
                result['pulled'] = True

                # Count changed files
                if old_commit and pull_info:
                    new_commit = self.repo.head.commit
                    if old_commit != new_commit:
                        diff = old_commit.diff(new_commit)
                        result['files_changed'] = len(list(diff))
            else:
                # If no branches exist yet, try to pull from default branch
                # This will fail gracefully if remote is empty
                try:
                    pull_info = origin.pull('main')
                    result['pulled'] = True
                except GitCommandError:
                    # Try master as fallback
                    pull_info = origin.pull('master')
                    result['pulled'] = True
        except GitCommandError as e:
            if "CONFLICT" in str(e):
                raise RuntimeError(
                    "Git conflict detected. Please resolve manually:\n"
                    f"1. cd {self.store_path}\n"
                    "2. Resolve conflicts\n"
                    "3. git add .\n"
                    "4. git commit\n"
                    "5. Run 'ars sync' again"
                )
            raise RuntimeError(f"Failed to pull from remote: {e}")

        return result

    def needs_pull(self) -> bool:
        """
        Check if local store is behind remote.

        Returns:
            True if remote has changes that are not in local store

        Raises:
            RuntimeError: If repository is not initialized
        """
        if self.repo is None:
            raise RuntimeError("Repository not initialized")

        try:
            origin = self.repo.remotes.origin

            # Fetch remote refs without pulling
            origin.fetch()

            # Get current branch
            if not self.repo.heads:
                return True  # No local commits, definitely need to pull

            current_branch = self.repo.active_branch.name
            local_commit = self.repo.head.commit

            # Get remote commit
            try:
                remote_commit = self.repo.refs[f'origin/{current_branch}'].commit
            except (IndexError, AttributeError):
                return False  # Remote branch doesn't exist

            # Check if local is behind remote
            return local_commit != remote_commit and \
                   self.repo.is_ancestor(local_commit, remote_commit)
        except GitCommandError:
            # If fetch fails, assume we need to pull
            return True

    def sync(self, message: str | None = None, pull_only: bool = False,
             push_only: bool = False) -> None:
        """
        Synchronize with remote (pull then push).

        Args:
            message: Commit message for push operation
            pull_only: If True, only pull without pushing
            push_only: If True, only push without pulling

        Raises:
            RuntimeError: If repository is not initialized or sync fails
        """
        if not push_only:
            self.pull()

        if not pull_only:
            self.commit_and_push(message)
