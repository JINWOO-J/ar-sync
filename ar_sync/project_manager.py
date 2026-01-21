"""Project management for ar-sync.

This module handles project registration and linking operations:
- Adding projects: copying target files to store
- Linking projects: creating symlinks from project directory to store
- Backing up existing files before overwriting
- Scanning for target files in project directories
"""

import shutil
import socket
from datetime import datetime
from pathlib import Path


class ProjectManager:
    """Manages project registration and linking operations.

    Attributes:
        store_path: Path to the store directory
        backup_dir: Path to the backup directory
    """

    def __init__(self, store_path: Path, backup_dir: Path):
        """Initialize ProjectManager.

        Args:
            store_path: Path to the store directory where projects are stored
            backup_dir: Path to the directory where backups are stored
        """
        self.store_path = store_path
        self.backup_dir = backup_dir

    def add_project(self, project_dir: Path, project_name: str, targets: list[str]) -> None:
        """Copy project targets to store.

        Copies all specified target files/directories from the project directory
        to the store, preserving directory structure within each target.

        Args:
            project_dir: Path to the project directory
            project_name: Name of the project (used as subdirectory in store)
            targets: List of target file/directory names to copy (e.g., [".cursor", ".kiro"])

        Raises:
            FileNotFoundError: If project_dir does not exist
        """
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {project_dir}")

        # Create project directory in store
        project_store_dir = self.store_path / project_name
        project_store_dir.mkdir(parents=True, exist_ok=True)

        # Copy each target to store
        for target in targets:
            source = project_dir / target
            if not source.exists():
                continue

            dest = project_store_dir / target

            if source.is_dir():
                # Remove existing directory if present
                if dest.exists():
                    shutil.rmtree(dest)
                # Copy directory tree
                shutil.copytree(source, dest)
            else:
                # Ensure parent directory exists
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Copy file
                shutil.copy2(source, dest)

    def link_project(self, project_dir: Path, project_name: str,
                    targets: list[str], force: bool = False) -> list[str]:
        """Create symlinks from project directory to store.

        Creates symbolic links in the project directory pointing to the
        corresponding files/directories in the store.

        Args:
            project_dir: Path to the project directory where symlinks will be created
            project_name: Name of the project in the store
            targets: List of target file/directory names to link
            force: If True, overwrite existing files; if False, raise error on conflict

        Returns:
            List of backed up file paths (empty if no backups were made)

        Raises:
            FileNotFoundError: If project does not exist in store
            FileExistsError: If target exists and force is False
        """
        project_store_dir = self.store_path / project_name

        if not project_store_dir.exists():
            raise FileNotFoundError(f"Project not found in store: {project_name}")

        backed_up_files = []

        for target in targets:
            source = project_store_dir / target
            link = project_dir / target

            if not source.exists():
                continue

            # Handle existing files
            if link.exists() or link.is_symlink():
                if not force:
                    raise FileExistsError(
                        f"Target already exists: {link}. Use --force to overwrite."
                    )

                # Backup existing file
                backup_path = self._backup_file(link, project_name)
                backed_up_files.append(str(backup_path))

                # Remove existing file/symlink
                if link.is_dir() and not link.is_symlink():
                    shutil.rmtree(link)
                else:
                    link.unlink()

            # Create symlink
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(source)

        return backed_up_files

    def _backup_file(self, path: Path, project_name: str) -> Path:
        """Backup existing file before overwriting.

        Creates a backup of the file/directory in the backup directory with
        a timestamp to prevent conflicts.

        Args:
            path: Path to the file/directory to backup
            project_name: Name of the project (used in backup directory name)

        Returns:
            Path to the backup location

        Raises:
            OSError: If backup operation fails
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{project_name}_{timestamp}"
        backup_path = self.backup_dir / backup_name / path.name

        # Create backup directory
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file or directory to backup
        if path.is_dir() and not path.is_symlink():
            shutil.copytree(path, backup_path)
        else:
            shutil.copy2(path, backup_path)

        return backup_path

    @staticmethod
    def get_hostname() -> str:
        """Get current machine hostname.

        Returns:
            Hostname of the current machine
        """
        return socket.gethostname()

    @staticmethod
    def get_current_project_name() -> str:
        """Get project name from current directory.

        Uses the name of the current working directory as the project name.

        Returns:
            Name of the current directory
        """
        return Path.cwd().name

    def pull_from_store(self, project_dir: Path, project_name: str, targets: list[str]) -> None:
        """Copy files from store to project directory.

        Copies all specified target files/directories from the store to the project
        directory, overwriting existing files.

        Args:
            project_dir: Path to the project directory
            project_name: Name of the project in the store
            targets: List of target file/directory names to copy

        Raises:
            FileNotFoundError: If project does not exist in store
        """
        project_store_dir = self.store_path / project_name

        if not project_store_dir.exists():
            raise FileNotFoundError(f"Project not found in store: {project_name}")

        for target in targets:
            source = project_store_dir / target
            if not source.exists():
                continue

            dest = project_dir / target

            # Remove existing file/directory
            if dest.exists() or dest.is_symlink():
                if dest.is_dir() and not dest.is_symlink():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()

            # Copy from store to project
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)

    def push_to_store(self, project_dir: Path, project_name: str, targets: list[str]) -> None:
        """Copy files from project directory to store.

        This is an alias for add_project() to maintain consistency with pull_from_store().

        Args:
            project_dir: Path to the project directory
            project_name: Name of the project (used as subdirectory in store)
            targets: List of target file/directory names to copy

        Raises:
            FileNotFoundError: If project_dir does not exist
        """
        self.add_project(project_dir, project_name, targets)

    @staticmethod
    def scan_targets(project_dir: Path, default_targets: list[str]) -> list[str]:
        """Scan directory for target files/directories.

        Checks which of the default targets exist in the project directory.

        Args:
            project_dir: Path to the project directory to scan
            default_targets: List of target names to look for

        Returns:
            List of target names that exist in the project directory
        """
        found_targets = []
        for target in default_targets:
            if (project_dir / target).exists():
                found_targets.append(target)
        return found_targets
