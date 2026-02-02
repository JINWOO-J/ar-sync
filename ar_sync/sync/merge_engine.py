"""
ar_sync.sync.merge_engine - 3-way merge engine using git merge-file.

This module provides the MergeEngine class for performing 3-way merges
between base, local, and remote versions of files.

Requirements:
- 5.4: When user selects `m` (merge) for a text file, perform 3-way merge using `git merge-file`
- 5.6: When merge produces conflicts, display conflict markers and prompt user to edit manually
- 5.7: If the file is binary, disable the merge option and only allow local/remote/skip
"""

import subprocess
import tempfile
from pathlib import Path

from ar_sync.sync.models import MergeResult


class MergeEngine:
    """Engine for performing 3-way merges using git merge-file.

    This class handles:
    - 3-way merge when base version is available
    - 2-way merge (diff3-style) when base is not available
    - Conflict marker detection and location tracking
    - Binary file rejection

    Validates:
    - Requirement 5.4: 3-way merge using git merge-file
    - Requirement 5.6: Conflict marker detection
    - Requirement 5.7: Binary file merge restriction
    """

    # Conflict marker patterns
    CONFLICT_START = "<<<<<<<"
    CONFLICT_MIDDLE = "======="
    CONFLICT_END = ">>>>>>>"

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

    def merge_files(
        self,
        base_path: Path | None,
        local_path: Path,
        remote_path: Path,
    ) -> MergeResult:
        """Perform 3-way merge (or 2-way if base is None).

        Args:
            base_path: Path to the common ancestor file (None for 2-way merge)
            local_path: Path to the local (Project) version
            remote_path: Path to the remote (Store) version

        Returns:
            MergeResult with success status, merged content, and conflict info

        Validates:
        - Requirement 5.4: 3-way merge using git merge-file
        - Requirement 5.6: Conflict marker detection
        - Requirement 5.7: Binary file rejection
        """
        # Check for binary files - reject merge
        if self._is_binary_file(local_path) or self._is_binary_file(remote_path):
            return MergeResult(
                success=False,
                merged_content=None,
                has_conflicts=False,
                conflict_markers=[],
            )

        # If no base, create an empty base for 2-way merge
        if base_path is None:
            return self._merge_without_base(local_path, remote_path)

        # Perform 3-way merge
        return self._merge_with_base(base_path, local_path, remote_path)

    def _merge_with_base(
        self,
        base_path: Path,
        local_path: Path,
        remote_path: Path,
    ) -> MergeResult:
        """Perform 3-way merge with a base file.

        Args:
            base_path: Path to the common ancestor file
            local_path: Path to the local version
            remote_path: Path to the remote version

        Returns:
            MergeResult with merge outcome
        """
        exit_code, merged_content = self._run_git_merge_file(
            base_path, local_path, remote_path
        )

        # git merge-file exit codes:
        # 0: merge successful, no conflicts
        # >0: number of conflicts (or error if negative)
        # <0: error occurred

        if exit_code < 0:
            # Error occurred
            return MergeResult(
                success=False,
                merged_content=None,
                has_conflicts=False,
                conflict_markers=[],
            )

        has_conflicts = exit_code > 0
        conflict_markers = self._detect_conflict_markers(merged_content) if has_conflicts else []

        return MergeResult(
            success=not has_conflicts,
            merged_content=merged_content,
            has_conflicts=has_conflicts,
            conflict_markers=conflict_markers,
        )

    def _merge_without_base(
        self,
        local_path: Path,
        remote_path: Path,
    ) -> MergeResult:
        """Perform 2-way merge by creating an empty base.

        When no common ancestor exists, we create an empty file as the base.
        This results in a merge that shows both versions as additions.

        Args:
            local_path: Path to the local version
            remote_path: Path to the remote version

        Returns:
            MergeResult with merge outcome
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.base', delete=False) as f:
            empty_base = Path(f.name)
            f.write("")  # Empty base file

        try:
            return self._merge_with_base(empty_base, local_path, remote_path)
        finally:
            # Clean up temporary file
            if empty_base.exists():
                empty_base.unlink()

    def _run_git_merge_file(
        self,
        base: Path,
        local: Path,
        remote: Path,
    ) -> tuple[int, str]:
        """Execute git merge-file and return result.

        git merge-file incorporates changes from remote into local,
        using base as the common ancestor.

        Args:
            base: Path to the base (ancestor) file
            local: Path to the local file (will be modified in-place by git)
            remote: Path to the remote file

        Returns:
            Tuple of (exit_code, merged_content)
            - exit_code: 0 for clean merge, >0 for number of conflicts, <0 for error
            - merged_content: The merged file content

        Validates:
        - Requirement 5.4: Uses git merge-file for 3-way merge
        """
        # Create a temporary copy of local file since git merge-file modifies in-place
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.local',
            delete=False,
            encoding='utf-8'
        ) as f:
            local_copy = Path(f.name)
            f.write(local.read_text(encoding='utf-8'))

        try:
            # Run git merge-file
            # -p: send results to stdout instead of overwriting local
            # --diff3: show base version in conflicts (more informative)
            result = subprocess.run(
                [
                    "git", "merge-file",
                    "-p",  # Print to stdout
                    "--diff3",  # Include base in conflict markers
                    str(local_copy),
                    str(base),
                    str(remote),
                ],
                capture_output=True,
                text=True,
            )

            # git merge-file returns:
            # - stdout: merged content
            # - exit code: 0 for success, >0 for conflict count, <0 for error
            merged_content = result.stdout

            # Handle error case (negative exit code or stderr with no stdout)
            if result.returncode < 0 or (result.stderr and not result.stdout):
                return (-1, "")

            return (result.returncode, merged_content)

        finally:
            # Clean up temporary file
            if local_copy.exists():
                local_copy.unlink()

    def _detect_conflict_markers(self, content: str) -> list[tuple[int, int]]:
        """Detect conflict marker locations in merged content.

        Finds all conflict regions marked by:
        - <<<<<<< (start)
        - ======= (middle)
        - >>>>>>> (end)

        Args:
            content: The merged file content

        Returns:
            List of (start_line, end_line) tuples for each conflict region
            Line numbers are 1-indexed.

        Validates:
        - Requirement 5.6: Conflict marker detection
        """
        if not content:
            return []

        lines = content.split('\n')
        conflict_markers: list[tuple[int, int]] = []

        start_line: int | None = None

        for i, line in enumerate(lines, start=1):  # 1-indexed line numbers
            if line.startswith(self.CONFLICT_START):
                start_line = i
            elif line.startswith(self.CONFLICT_END) and start_line is not None:
                conflict_markers.append((start_line, i))
                start_line = None

        return conflict_markers

    def _is_binary_file(self, path: Path) -> bool:
        """Check if a file is binary.

        Uses extension checking first, then content inspection as fallback.

        Args:
            path: Path to the file to check

        Returns:
            True if the file appears to be binary, False otherwise

        Validates:
        - Requirement 5.7: Binary file detection for merge restriction
        """
        if not path.exists():
            return False

        # Check for known text extensions first (fast path)
        if path.suffix.lower() in self.TEXT_EXTENSIONS:
            return False

        # Check by binary extension (fast path)
        if path.suffix.lower() in self.BINARY_EXTENSIONS:
            return True

        try:
            # Read first 8KB to check for binary content
            chunk_size = 8192
            with open(path, 'rb') as f:
                chunk = f.read(chunk_size)

            # Empty file is not binary
            if not chunk:
                return False

            # Check for null bytes (strong indicator of binary)
            if b'\x00' in chunk:
                return True

            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8')
                return False
            except UnicodeDecodeError:
                return True

        except OSError:
            # If we can't read the file, assume it's not binary
            return False
