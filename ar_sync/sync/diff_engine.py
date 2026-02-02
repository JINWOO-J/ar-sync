"""
ar_sync.sync.diff_engine - File comparison engine using git diff.

This module provides the DiffEngine class for comparing files and directories
between Project and Store using content-based comparison.

Requirements:
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

import subprocess
from pathlib import Path

from ar_sync.sync.models import ChangeType, FileChange


class DiffEngine:
    """Engine for comparing files and directories between Project and Store.

    Uses content-based comparison to detect changes and generates diff output
    using `git diff --no-index` for consistent, familiar formatting.
    """

    # Common text file extensions (explicitly text)
    TEXT_EXTENSIONS = frozenset({
        # Source code
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
        # Markup/Config
        '.md', '.markdown', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini',
        '.xml', '.html', '.htm', '.css', '.scss', '.sass', '.less',
        # Shell/Scripts
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        # Documentation
        '.rst', '.tex', '.adoc', '.org',
        # Other text
        '.csv', '.tsv', '.log', '.sql', '.env', '.gitignore', '.gitattributes',
    })

    # Common binary file extensions
    BINARY_EXTENSIONS = frozenset({
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.svg',
        '.tiff', '.tif', '.psd', '.ai', '.eps',
        # Audio/Video
        '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv', '.flac', '.ogg',
        '.m4a', '.m4v', '.webm',
        # Archives
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.xz', '.zst',
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Executables/Libraries
        '.exe', '.dll', '.so', '.dylib', '.a', '.o', '.pyc', '.pyo',
        '.class', '.jar', '.war', '.ear',
        # Fonts
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # Database
        '.db', '.sqlite', '.sqlite3',
        # Other
        '.bin', '.dat', '.iso', '.dmg',
    })

    def compare_directories(
        self,
        project_dir: Path,
        store_dir: Path,
        targets: list[str],
    ) -> list[FileChange]:
        """Compare target files/directories between Project and Store.

        Recursively compares all files within the specified targets,
        categorizing each as ADDED_LOCAL, ADDED_REMOTE, MODIFIED, or UNCHANGED.

        Args:
            project_dir: Path to the project directory
            store_dir: Path to the store directory (project-specific subdirectory)
            targets: List of target file/directory names to compare
                    (e.g., ['.kiro', '.cursor', 'AGENTS.md'])

        Returns:
            List of FileChange objects representing all detected changes.
            Files with no differences (UNCHANGED) are excluded from the output.

        Validates:
            - Requirement 2.1: Files only in Project → ADDED_LOCAL
            - Requirement 2.2: Files only in Store → ADDED_REMOTE
            - Requirement 2.3: Different content → MODIFIED
            - Requirement 2.5: Symlinks to Store are skipped
            - Requirement 2.6: Recursive comparison
            - Requirement 3.5: UNCHANGED files excluded
        """
        changes: list[FileChange] = []

        # Collect all files from both directories for the given targets
        project_files = self._collect_files(project_dir, targets, store_dir)
        store_files = self._collect_files(store_dir, targets, store_dir=None)

        # Get all unique relative paths
        all_paths = set(project_files.keys()) | set(store_files.keys())

        for rel_path in sorted(all_paths):
            local_path = project_files.get(rel_path)
            remote_path = store_files.get(rel_path)

            change = self._compare_single_file(
                rel_path=rel_path,
                local_path=local_path,
                remote_path=remote_path,
            )

            # Requirement 3.5: Exclude files with no differences
            if change.change_type != ChangeType.UNCHANGED:
                changes.append(change)

        return changes

    def _collect_files(
        self,
        base_dir: Path,
        targets: list[str],
        store_dir: Path | None = None,
    ) -> dict[str, Path]:
        """Collect all files from targets within base directory.

        Args:
            base_dir: Base directory to search in
            targets: List of target file/directory names
            store_dir: Store directory path for symlink detection (None to skip)

        Returns:
            Dictionary mapping relative paths to absolute paths
        """
        files: dict[str, Path] = {}

        for target in targets:
            target_path = base_dir / target

            if not target_path.exists():
                continue

            if target_path.is_file():
                # Skip symlinks pointing to store (Requirement 2.5)
                if store_dir and self._is_symlink_to_store(target_path, store_dir):
                    continue
                files[target] = target_path
            elif target_path.is_dir():
                # Recursively collect files (Requirement 2.6)
                for file_path in target_path.rglob('*'):
                    if file_path.is_file():
                        # Skip symlinks pointing to store
                        if store_dir and self._is_symlink_to_store(file_path, store_dir):
                            continue
                        rel_path = str(file_path.relative_to(base_dir))
                        files[rel_path] = file_path

        return files

    def _is_symlink_to_store(self, path: Path, store_dir: Path) -> bool:
        """Check if path is a symlink pointing to store directory.

        Validates: Requirement 2.5 - Skip symlinks pointing to Store

        Args:
            path: Path to check
            store_dir: Store directory path

        Returns:
            True if path is a symlink pointing to store, False otherwise
        """
        if not path.is_symlink():
            return False

        try:
            # Resolve the symlink target
            target = path.resolve()
            store_resolved = store_dir.resolve()

            # Check if target is within store directory
            try:
                target.relative_to(store_resolved)
                return True
            except ValueError:
                return False
        except (OSError, RuntimeError):
            # Broken symlink or other error
            return False

    def _compare_single_file(
        self,
        rel_path: str,
        local_path: Path | None,
        remote_path: Path | None,
    ) -> FileChange:
        """Compare a single file between Project and Store.

        Args:
            rel_path: Relative path of the file
            local_path: Path to file in Project (None if not exists)
            remote_path: Path to file in Store (None if not exists)

        Returns:
            FileChange object with comparison result
        """
        # Requirement 2.1: File only in Project
        if local_path and not remote_path:
            is_binary = self.is_binary_file(local_path)
            return FileChange(
                path=rel_path,
                change_type=ChangeType.ADDED_LOCAL,
                local_path=local_path,
                remote_path=None,
                is_binary=is_binary,
                diff_output=None,
            )

        # Requirement 2.2: File only in Store
        if remote_path and not local_path:
            is_binary = self.is_binary_file(remote_path)
            return FileChange(
                path=rel_path,
                change_type=ChangeType.ADDED_REMOTE,
                local_path=None,
                remote_path=remote_path,
                is_binary=is_binary,
                diff_output=None,
            )

        # Both exist - compare content (Requirement 2.3, 2.4)
        assert local_path is not None and remote_path is not None

        is_binary = self.is_binary_file(local_path) or self.is_binary_file(remote_path)

        # Content-based comparison (Requirement 2.4)
        if self._files_have_same_content(local_path, remote_path):
            return FileChange(
                path=rel_path,
                change_type=ChangeType.UNCHANGED,
                local_path=local_path,
                remote_path=remote_path,
                is_binary=is_binary,
                diff_output=None,
            )

        # Files differ - generate diff output
        diff_output = None
        if not is_binary:
            diff_output = self.get_diff_output(local_path, remote_path)

        return FileChange(
            path=rel_path,
            change_type=ChangeType.MODIFIED,
            local_path=local_path,
            remote_path=remote_path,
            is_binary=is_binary,
            diff_output=diff_output,
        )

    def _files_have_same_content(self, path1: Path, path2: Path) -> bool:
        """Check if two files have identical content.

        Validates: Requirement 2.4 - Content-based comparison (not timestamp)

        Args:
            path1: First file path
            path2: Second file path

        Returns:
            True if files have identical content, False otherwise
        """
        try:
            content1 = path1.read_bytes()
            content2 = path2.read_bytes()
            return content1 == content2
        except OSError:
            return False

    def compare_files(
        self,
        local_path: Path,
        remote_path: Path,
    ) -> FileChange:
        """Compare two specific files and generate diff.

        This is a convenience method for comparing individual files
        without the full directory comparison context.

        Args:
            local_path: Path to the local (Project) file
            remote_path: Path to the remote (Store) file

        Returns:
            FileChange object with comparison result and diff output
        """
        # Determine relative path from local_path name
        rel_path = local_path.name

        local_exists = local_path.exists()
        remote_exists = remote_path.exists()

        return self._compare_single_file(
            rel_path=rel_path,
            local_path=local_path if local_exists else None,
            remote_path=remote_path if remote_exists else None,
        )

    def get_diff_output(
        self,
        local_path: Path,
        remote_path: Path,
    ) -> str:
        """Generate diff output using git diff --no-index.

        Validates: Requirement 3.1 - Use `git diff --no-index` format

        Args:
            local_path: Path to the local (Project) file
            remote_path: Path to the remote (Store) file

        Returns:
            Diff output string in git diff format.
            Returns empty string if files are identical or on error.
        """
        try:
            # git diff --no-index returns exit code 1 if files differ
            # and exit code 0 if files are identical
            result = subprocess.run(
                [
                    'git', 'diff', '--no-index',
                    '--', str(remote_path), str(local_path)
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Exit code 0 = identical, 1 = different, other = error
            if result.returncode in (0, 1):
                return result.stdout

            return ''
        except subprocess.TimeoutExpired:
            return ''
        except (subprocess.SubprocessError, OSError):
            return ''

    def is_binary_file(self, path: Path) -> bool:
        """Check if a file is binary.

        Uses a combination of extension checking and content inspection
        to determine if a file is binary.

        Args:
            path: Path to the file to check

        Returns:
            True if the file is binary, False if it's text
        """
        # Check for known text extensions first (fast path)
        if path.suffix.lower() in self.TEXT_EXTENSIONS:
            return False

        # Check by binary extension (fast path)
        if path.suffix.lower() in self.BINARY_EXTENSIONS:
            return True

        # Check content for binary indicators
        try:
            # Read first 8KB to check for binary content
            with open(path, 'rb') as f:
                chunk = f.read(8192)

            # Empty file is not binary
            if not chunk:
                return False

            # Check for null bytes (strong indicator of binary)
            if b'\x00' in chunk:
                return True

            # Check for high ratio of non-text bytes
            # Text files typically have mostly printable ASCII + common control chars
            text_chars = set(range(32, 127)) | {9, 10, 13}  # printable + tab, LF, CR
            non_text_count = sum(1 for byte in chunk if byte not in text_chars)

            # If more than 30% non-text characters, consider it binary
            if non_text_count / len(chunk) > 0.3:
                return True

            return False
        except OSError:
            # If we can't read the file, assume it's not binary
            return False
