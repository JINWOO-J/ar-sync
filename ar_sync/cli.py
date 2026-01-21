"""Command-line interface for ar-sync.

This module provides the CLI commands for ar-sync using Typer framework.
"""

import logging
import shutil
import sys
from pathlib import Path

import typer

from ar_sync.config_manager import ConfigManager
from ar_sync.errors import ARSyncError, ErrorCategory
from ar_sync.git_backend import GitBackend
from ar_sync.models import LocalConfig
from ar_sync.project_manager import ProjectManager
from ar_sync.store_manager import StoreManager

# Global debug flag
DEBUG_MODE = False

# Configure logging
logger = logging.getLogger("ar_sync")


def setup_logging(debug: bool = False) -> None:
    """Configure logging based on debug mode.

    Args:
        debug: Enable debug logging if True
    """
    global DEBUG_MODE
    DEBUG_MODE = debug

    level = logging.DEBUG if debug else logging.WARNING
    handler = logging.StreamHandler(sys.stderr)

    if debug:
        formatter = logging.Formatter(
            '[%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s'
        )
    else:
        formatter = logging.Formatter('[%(levelname)s] %(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

    # Also configure root logger for third-party libraries
    logging.basicConfig(level=level, handlers=[handler], force=True)


def debug_log(message: str) -> None:
    """Log a debug message.

    Note: Due to Typer's internal behavior, this may be called twice.
    This is normal and does not affect functionality.

    Args:
        message: Log message
    """
    logger.debug(message)


app = typer.Typer(
    name="ar-sync",
    help="Synchronize AI IDE settings across machines using Git",
    add_completion=False,
    no_args_is_help=True
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from ar_sync.__version__ import __version__
        typer.echo(f"ar-sync version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True
    )
) -> None:
    """Callback to handle global options."""
    pass


@app.command()
def setup(
    backend: str = typer.Option(None, help="Storage backend: 'git' or 'local'"),
    path: str = typer.Option(None, help="Local store path"),
    repo_url: str = typer.Option(None, help="Git repository URL (required for 'git' backend)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Initialize ar-sync global configuration and storage backend.

    This is a one-time setup command that creates the global configuration
    and initializes the storage backend (Git repository or local directory).

    Examples:
        ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git
        ars setup --backend local --path ~/Dropbox/ar-sync-store
        ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git --debug
    """
    setup_logging(debug)

    try:
        # 1. Check for existing config and use defaults
        config_manager = ConfigManager()
        existing_config = None
        try:
            existing_config = config_manager.load()
        except FileNotFoundError:
            pass

        # Use existing values as defaults if not provided
        if backend is None:
            if existing_config:
                backend = existing_config.backend
            else:
                backend = "git"  # Default to git if no existing config

        # 2. Validate backend
        if backend not in ['git', 'local']:
            raise ARSyncError(
                f"Unsupported backend: {backend}",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Use 'git' or 'local' as the backend",
                    "Example (git): ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git",
                    "Example (local): ars setup --backend local --path ~/Dropbox/ar-sync-store"
                ]
            )

        # 3. Use existing values as defaults if not provided
        if path is None:
            if existing_config:
                path = existing_config.store_path
            else:
                raise ARSyncError(
                    "Store path is required",
                    ErrorCategory.USER_INPUT,
                    recovery_steps=[
                        "Provide --path option",
                        "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                    ]
                )

        if repo_url is None:
            if existing_config:
                repo_url = existing_config.repo_url
            elif backend == 'git':
                raise ARSyncError(
                    "Repository URL is required for 'git' backend",
                    ErrorCategory.USER_INPUT,
                    recovery_steps=[
                        "Provide --repo-url option",
                        "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                    ]
                )
            else:
                repo_url = ""  # Not required for local backend

        # 4. Expand path and convert to Path object
        store_path = Path(path).expanduser().resolve()

        # 3. Create LocalConfig
        config = LocalConfig(
            version=1,
            backend=backend,
            store_path=str(store_path),
            repo_url=repo_url,
            default_targets=[".cursor", ".kiro", ".gemini", ".qwen", "AGENTS.md"],
            auto_sync=False,
            backup_originals=True,
            backup_dir=str(Path.home() / ".config" / "ar-sync" / "backups")
        )

        # 4. Save configuration using ConfigManager
        config_manager.save(config)

        typer.echo(f"✓ Configuration saved to {ConfigManager.CONFIG_PATH}")

        # 5. Initialize Git repository (only for git backend)
        if backend == 'git':
            git_backend = GitBackend(store_path, repo_url)
            git_backend.initialize()
            typer.echo(f"✓ Git repository initialized at {store_path}")
        else:
            # For local backend, just ensure directory exists
            store_path.mkdir(parents=True, exist_ok=True)
            typer.echo(f"✓ Store directory created at {store_path}")

        # 6. Initialize store metadata using StoreManager
        store_manager = StoreManager(store_path)
        store_manager.initialize()

        typer.echo(f"✓ Store metadata created at {store_path / StoreManager.METADATA_FILENAME}")

        typer.echo("\n✓ Initialization complete!")
        typer.echo(f"\nBackend: {backend}")
        typer.echo(f"Store location: {store_path}")
        if backend == 'git':
            typer.echo(f"Remote repository: {repo_url}")
        typer.echo("\nNext steps:")
        typer.echo("  1. cd to your project directory")
        typer.echo("  2. Run 'ars init' to initialize the project")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during setup")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Initialization failed: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that the path is valid and writable",
                "Ensure Git is installed and available in PATH",
                "Verify the repository URL is correct"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during setup")
        raise typer.Exit(code=1)


@app.command()
def add(
    name: str | None = typer.Option(None, help="Project name (defaults to current directory name)"),
    targets: str | None = typer.Option(None, help="Comma-separated targets (defaults to .cursor,.kiro,.gemini,.qwen,AGENTS.md)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Add current project to store.

    Copies target files to store, updates metadata, and syncs to remote.

    Examples:
        ars add
        ars add --name my-project
        ars add --targets .cursor,.kiro,.vscode,AGENTS.md
        ars add --debug
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend local --path ~/Dropbox/ar-sync-store"
                ]
            )

        # 2. Determine project name
        project_name = name if name else ProjectManager.get_current_project_name()

        # 3. Determine targets
        if targets:
            target_list = [t.strip() for t in targets.split(',')]
        else:
            target_list = config.default_targets

        # 4. Scan for targets in current directory
        project_dir = Path.cwd()
        found_targets = ProjectManager.scan_targets(project_dir, target_list)

        if not found_targets:
            raise ARSyncError(
                "No target files found in current directory",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    f"Expected targets: {', '.join(target_list)}",
                    "Make sure you're in the correct project directory",
                    "Or specify custom targets with --targets option"
                ]
            )

        typer.echo(f"Found targets: {', '.join(found_targets)}")

        # 5. Copy files to store
        store_path = Path(config.store_path)
        backup_dir = Path(config.backup_dir)
        project_manager = ProjectManager(store_path, backup_dir)

        typer.echo("Copying files to store...")
        project_manager.add_project(project_dir, project_name, found_targets)

        typer.echo(f"✓ Files copied to {store_path / project_name}")

        # 6. Update store metadata
        hostname = ProjectManager.get_hostname()
        store_manager = StoreManager(store_path)
        store_manager.add_project(project_name, found_targets, hostname)

        typer.echo("✓ Store metadata updated")

        # 7. Commit and push (only for git backend)
        if config.backend == 'git':
            git_backend = GitBackend(store_path, config.repo_url)
            git_backend.initialize()

            typer.echo("Committing and pushing changes...")
            commit_message = f"Add project: {project_name} (targets: {', '.join(found_targets)})"
            git_backend.commit_and_push(commit_message)

            typer.echo("✓ Changes pushed to remote")
        else:
            typer.echo("✓ Changes saved to local store")

        typer.echo(f"\n✓ Project '{project_name}' added successfully!")
        typer.echo("\nNext steps:")
        typer.echo(f"  - On another machine, run 'ars link --project {project_name}' to link these settings")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during add")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Failed to add project: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that you have write permissions to the store directory",
                "Verify Git is configured correctly",
                "Ensure the remote repository is accessible"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during add")
        raise typer.Exit(code=1)


@app.command()
def init(
    name: str | None = typer.Option(None, help="Project name (defaults to current directory name)"),
    targets: str | None = typer.Option(None, help="Comma-separated targets (defaults to .cursor,.kiro,.gemini,.qwen,AGENTS.md)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Initialize current project and add to store.

    This command adds the current project to the store and, if using local backend,
    automatically creates symlinks. This is the recommended way to set up a new project.

    Examples:
        ars init
        ars init --name my-project
        ars init --targets .cursor,.kiro,.vscode,AGENTS.md
        ars init --debug
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Global configuration not found",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize global configuration",
                    "Example: ars setup --backend local --path ~/Dropbox/ar-sync-store"
                ]
            )

        # 2. Determine project name
        project_name = name if name else ProjectManager.get_current_project_name()

        # 3. Determine targets
        if targets:
            target_list = [t.strip() for t in targets.split(',')]
        else:
            target_list = config.default_targets

        # 4. Scan for targets in current directory
        project_dir = Path.cwd()
        found_targets = ProjectManager.scan_targets(project_dir, target_list)

        if not found_targets:
            raise ARSyncError(
                "No target files found in current directory",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    f"Expected targets: {', '.join(target_list)}",
                    "Make sure you're in the correct project directory",
                    "Or specify custom targets with --targets option"
                ]
            )

        typer.echo(f"Found targets: {', '.join(found_targets)}")

        # 5. Copy files to store
        store_path = Path(config.store_path)
        backup_dir = Path(config.backup_dir)
        project_manager = ProjectManager(store_path, backup_dir)

        typer.echo("Copying files to store...")
        project_manager.add_project(project_dir, project_name, found_targets)

        typer.echo(f"✓ Files copied to {store_path / project_name}")

        # 6. Update store metadata
        hostname = ProjectManager.get_hostname()
        store_manager = StoreManager(store_path)
        store_manager.add_project(project_name, found_targets, hostname)

        typer.echo("✓ Store metadata updated")

        # 7. Commit and push (only for git backend)
        if config.backend == 'git':
            git_backend = GitBackend(store_path, config.repo_url)
            git_backend.initialize()

            typer.echo("Committing and pushing changes...")
            commit_message = f"Add project: {project_name} (targets: {', '.join(found_targets)})"
            git_backend.commit_and_push(commit_message)

            typer.echo("✓ Changes pushed to remote")
        else:
            typer.echo("✓ Changes saved to local store")

        # 8. For local backend, automatically create symlinks
        if config.backend == 'local':
            typer.echo("\nCreating symlinks...")

            # Remove existing files/directories before linking
            for target in found_targets:
                target_path = project_dir / target
                if target_path.exists() or target_path.is_symlink():
                    if target_path.is_dir() and not target_path.is_symlink():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()

            # Create symlinks
            backed_up_files = project_manager.link_project(project_dir, project_name, found_targets, force=True)

            if backed_up_files:
                typer.echo("\n⚠️  Original files were backed up:")
                for backup_path in backed_up_files:
                    typer.echo(f"   → {backup_path}")
                typer.echo(f"\nBackup location: {backup_dir}")

            typer.echo("✓ Symlinks created")

        typer.echo(f"\n✓ Project '{project_name}' initialized successfully!")

        if config.backend == 'git':
            typer.echo("\nNext steps:")
            typer.echo("  - On another machine, run 'ars link' to link these settings")
        else:
            typer.echo(f"\nYour project is now synced via {store_path}")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during init")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Failed to initialize project: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that you have write permissions to the store directory",
                "Verify the store directory is accessible",
                "Ensure you're in the correct project directory"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during init")
        raise typer.Exit(code=1)


@app.command()
def link(
    project: str | None = typer.Option(None, help="Project name (defaults to current directory name)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Link store settings to current directory.

    Creates symlinks from current directory to store. Backs up existing files unless --force is used.

    Examples:
        ars link
        ars link --project my-project
        ars link --force
        ars link --debug
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # 2. Determine project name
        project_name = project if project else ProjectManager.get_current_project_name()

        # 3. Check if store directory exists
        store_path = Path(config.store_path)
        if not store_path.exists():
            raise ARSyncError(
                f"Store directory does not exist: {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store directory may have been deleted or moved",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize",
                    "Or update the store path: ars config --path /path/to/store"
                ]
            )

        # 4. Get project info from store
        store_manager = StoreManager(store_path)

        try:
            project_info = store_manager.get_project(project_name)
        except FileNotFoundError:
            raise ARSyncError(
                f"Store metadata file not found at {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store may not be properly initialized",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        if project_info is None:
            raise ARSyncError(
                f"Project '{project_name}' not found in store",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars status' to see available projects",
                    "Or run 'ars add' to add this project first"
                ]
            )

        typer.echo(f"Linking project: {project_name}")
        typer.echo(f"Targets: {', '.join(project_info.targets)}")

        # 5. Check if project directory exists in store
        project_store_dir = store_path / project_name
        if not project_store_dir.exists():
            raise ARSyncError(
                f"Project directory not found in store: {project_store_dir}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The project metadata exists but the directory is missing",
                    "Run 'ars add' to recreate the project in store",
                    "Or check if the store directory has been modified manually"
                ]
            )

        # 6. Create symlinks
        project_dir = Path.cwd()
        backup_dir = Path(config.backup_dir)
        project_manager = ProjectManager(store_path, backup_dir)

        try:
            backed_up_files = project_manager.link_project(project_dir, project_name, project_info.targets, force)
        except FileExistsError as e:
            raise ARSyncError(
                str(e),
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Use --force to overwrite existing files",
                    "Or manually remove/rename the existing files"
                ]
            )

        # Show backup information if files were backed up
        if backed_up_files:
            typer.echo("\n⚠️  Existing files were backed up:")
            for backup_path in backed_up_files:
                typer.echo(f"   → {backup_path}")
            typer.echo(f"\nBackup location: {backup_dir}")

        typer.echo("✓ Symlinks created")

        # 7. Update store metadata with current machine
        hostname = ProjectManager.get_hostname()
        store_manager.add_project(project_name, project_info.targets, hostname)

        typer.echo("✓ Store metadata updated")

        typer.echo(f"\n✓ Project '{project_name}' linked successfully!")
        typer.echo(f"Machine: {hostname}")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during link")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Failed to link project: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that you have write permissions in the current directory",
                "On Windows, ensure Developer Mode is enabled for symlink support",
                "Verify the store directory is accessible"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during link")
        raise typer.Exit(code=1)


@app.command()
def status(
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Show registered projects and sync status.

    Displays all projects, their targets, and linked machines.

    Example:
        ars status
        ars status --debug
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # 2. Check if store directory exists
        store_path = Path(config.store_path)
        if not store_path.exists():
            raise ARSyncError(
                f"Store directory does not exist: {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store directory may have been deleted or moved",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize",
                    "Or update the store path: ars config --path /path/to/store"
                ]
            )

        # 3. Load store metadata
        store_manager = StoreManager(store_path)

        try:
            metadata = store_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                f"Store metadata file not found at {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store may not be properly initialized",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        # 4. Get current project name
        current_project = ProjectManager.get_current_project_name()

        # 4.5. Sync metadata with actual store contents for all projects
        synced_projects = []
        for project_name in metadata.projects.keys():
            if store_manager.sync_metadata_with_store(project_name):
                synced_projects.append(project_name)

        # Reload metadata if any projects were synced
        if synced_projects:
            metadata = store_manager.load()
            typer.echo(f"Synced metadata for projects: {', '.join(synced_projects)}\n", err=True)

        # 5. Display status
        if not metadata.projects:
            typer.echo("No projects registered yet.")
            typer.echo("\nRun 'ars add' in a project directory to add it to the store.")
            return

        typer.echo(f"Store: {store_path}")
        typer.echo(f"Remote: {config.repo_url}")
        typer.echo(f"\nRegistered projects ({len(metadata.projects)}):\n")

        for project_name, project_info in metadata.projects.items():
            # Highlight current project
            is_current = project_name == current_project
            prefix = "→ " if is_current else "  "

            typer.echo(f"{prefix}{project_name}")
            typer.echo(f"    Targets: {', '.join(project_info.targets)}")
            typer.echo(f"    Machines ({len(project_info.machines)}):")

            for machine in project_info.machines:
                typer.echo(f"      - {machine.hostname} (linked: {machine.linked_at})")

            typer.echo()

        if current_project in metadata.projects:
            typer.echo(f"→ Current directory is registered as '{current_project}'")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during status")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Failed to get status: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that the store directory is accessible",
                "Verify the metadata file is not corrupted"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during status")
        raise typer.Exit(code=1)


@app.command()
def sync(
    message: str | None = typer.Option(None, "-m", help="Commit message"),
    pull_only: bool = typer.Option(False, "--pull", help="Pull only, don't push"),
    push_only: bool = typer.Option(False, "--push", help="Push only, don't pull"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Synchronize store with remote repository (git backend only).

    This command synchronizes the STORE directory with the remote Git repository.
    It does NOT sync project files - use 'ars pull' or 'ars push' for that.

    Operations:
    1. Pull: Fetch changes from remote to store
    2. Push: Commit local store changes and push to remote

    Examples:
        ars sync                    # Full sync (pull + push)
        ars sync -m "Update"        # Full sync with custom commit message
        ars sync --pull             # Only pull from remote
        ars sync --push             # Only push to remote
        ars sync --debug            # Show detailed logs
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # 2. Check backend type
        if config.backend != 'git':
            raise ARSyncError(
                f"Sync command is only available for 'git' backend (current: {config.backend})",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "For 'local' backend, files are automatically synced via cloud storage (Dropbox, iCloud, etc.)",
                    "Or switch to 'git' backend: ars config --backend git --repo-url git@github.com:user/repo.git"
                ]
            )

        # 3. Initialize Git backend
        store_path = Path(config.store_path)
        git_backend = GitBackend(store_path, config.repo_url)
        git_backend.initialize()

        # 4. Perform sync
        if pull_only and push_only:
            raise ARSyncError(
                "Cannot use --pull and --push together",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Use --pull for pull only",
                    "Use --push for push only",
                    "Or use neither for full sync"
                ]
            )

        if not push_only:
            typer.echo("[1/2] Pulling changes from remote repository...")
            pull_result = git_backend.pull()
            if pull_result['files_changed'] > 0:
                typer.echo(f"✓ Pulled {pull_result['files_changed']} file(s) from remote")
            else:
                typer.echo("✓ No changes from remote (already up to date)")

        if not pull_only:
            typer.echo("[2/2] Committing and pushing local changes...")
            push_result = git_backend.commit_and_push(message)
            if push_result['committed']:
                typer.echo(f"✓ Committed {push_result['files_changed']} file(s)")
                typer.echo("✓ Pushed to remote")
            else:
                typer.echo("✓ No local changes to push")

        typer.echo("\n✓ Store synchronization complete!")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during sync")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Synchronization failed: {str(e)}",
            ErrorCategory.GIT,
            recovery_steps=[
                "Check your network connection",
                "Verify Git credentials are configured",
                "Ensure the remote repository is accessible",
                "If there are conflicts, resolve them manually in the store directory"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during sync")
        raise typer.Exit(code=1)


@app.command()
def pull(
    project: str | None = typer.Option(None, help="Project name (defaults to current directory name)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Pull changes from store to current project directory.

    This command copies files from the store to your project directory.
    For git backend: pulls from remote to store first, then copies to project.
    For local backend: directly copies from store to project.

    Operations (git backend):
    1. Pull remote changes to store
    2. Copy files from store to project directory

    Operations (local backend):
    1. Copy files from store to project directory

    Examples:
        ars pull                    # Pull to current directory
        ars pull --project my-proj  # Pull specific project
        ars pull --debug            # Show detailed logs
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # 2. Determine project name
        project_name = project if project else ProjectManager.get_current_project_name()

        # 3. Check if store directory exists
        store_path = Path(config.store_path)
        if not store_path.exists():
            raise ARSyncError(
                f"Store directory does not exist: {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store directory may have been deleted or moved",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        # 4. For git backend, check if we need to sync first
        if config.backend == 'git':
            git_backend = GitBackend(store_path, config.repo_url)
            git_backend.initialize()

            # Smart detection: check if store is behind remote
            if git_backend.needs_pull():
                typer.echo("Store is behind remote. Syncing first...")
                typer.echo("[1/2] Pulling changes from remote repository to store...")
                pull_result = git_backend.pull()
                if pull_result['files_changed'] > 0:
                    typer.echo(f"✓ Pulled {pull_result['files_changed']} file(s) from remote to store")
                else:
                    typer.echo("✓ Store is up to date with remote")
            else:
                typer.echo("[1/2] Store is already up to date with remote")

        # 5. Get project info from store
        store_manager = StoreManager(store_path)

        try:
            project_info = store_manager.get_project(project_name)
        except FileNotFoundError:
            raise ARSyncError(
                f"Store metadata file not found at {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store may not be properly initialized",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        if project_info is None:
            raise ARSyncError(
                f"Project '{project_name}' not found in store",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars status' to see available projects",
                    "Or run 'ars add' to add this project first"
                ]
            )

        # 6. Copy files from store to project directory
        project_dir = Path.cwd()
        backup_dir = Path(config.backup_dir)
        project_manager = ProjectManager(store_path, backup_dir)

        step_num = "[2/2]" if config.backend == 'git' else "[1/1]"
        typer.echo(f"{step_num} Copying files from store to project directory...")
        typer.echo(f"  Project: {project_name}")
        typer.echo(f"  Targets: {', '.join(project_info.targets)}")

        project_manager.pull_from_store(project_dir, project_name, project_info.targets)

        typer.echo(f"✓ Files copied to {project_dir}")
        typer.echo("\n✓ Pull complete!")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during pull")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Pull failed: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that you have write permissions in the current directory",
                "Verify the store directory is accessible",
                "For git backend, ensure network connection is available"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during pull")
        raise typer.Exit(code=1)


@app.command()
def push(
    project: str | None = typer.Option(None, help="Project name (defaults to current directory name)"),
    message: str | None = typer.Option(None, "-m", help="Commit message (git backend only)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """Push changes from current project directory to store.

    For git backend: copies files to store, then commits and pushes to remote.
    For local backend: copies files to store.

    Examples:
        ars push
        ars push --project my-project
        ars push -m "Update settings"
        ars push --debug
    """
    setup_logging(debug)

    try:
        # 1. Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Store not initialized",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize the store",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # 2. Determine project name
        project_name = project if project else ProjectManager.get_current_project_name()

        # 3. Check if store directory exists
        store_path = Path(config.store_path)
        if not store_path.exists():
            raise ARSyncError(
                f"Store directory does not exist: {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store directory may have been deleted or moved",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        # 4. Get project info from store
        store_manager = StoreManager(store_path)

        try:
            project_info = store_manager.get_project(project_name)
        except FileNotFoundError:
            raise ARSyncError(
                f"Store metadata file not found at {store_path}",
                ErrorCategory.FILE_SYSTEM,
                recovery_steps=[
                    "The store may not be properly initialized",
                    f"Run 'ars setup --backend {config.backend} --path {store_path}' to reinitialize"
                ]
            )

        if project_info is None:
            raise ARSyncError(
                f"Project '{project_name}' not found in store",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars status' to see available projects",
                    "Or run 'ars add' to add this project first"
                ]
            )

        # 5. Copy files from project directory to store
        project_dir = Path.cwd()
        backup_dir = Path(config.backup_dir)
        project_manager = ProjectManager(store_path, backup_dir)

        typer.echo("Copying files from project directory to store...")
        typer.echo(f"Targets: {', '.join(project_info.targets)}")

        project_manager.push_to_store(project_dir, project_name, project_info.targets)

        typer.echo(f"✓ Files copied to {store_path / project_name}")

        # 6. For git backend, commit and push to remote
        if config.backend == 'git':
            git_backend = GitBackend(store_path, config.repo_url)
            git_backend.initialize()

            typer.echo("Committing and pushing changes to remote...")

            if message is None:
                message = f"Update project: {project_name}"

            git_backend.commit_and_push(message)

            typer.echo("✓ Changes pushed to remote")
        else:
            typer.echo("✓ Changes saved to local store")

        typer.echo("\n✓ Push complete!")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during push")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Push failed: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check that you have write permissions to the store directory",
                "Verify the store directory is accessible",
                "For git backend, ensure network connection and Git credentials are configured"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during push")
        raise typer.Exit(code=1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    backend: str | None = typer.Option(None, "--backend", help="Set backend (git or local)"),
    path: str | None = typer.Option(None, "--path", help="Set store path"),
    repo_url: str | None = typer.Option(None, "--repo-url", help="Set repository URL"),
    targets: str | None = typer.Option(None, "--targets", help="Set default targets (comma-separated)"),
    debug: bool = typer.Option(False, "-d", "--debug", help="Enable debug logging")
) -> None:
    """View or modify configuration settings.

    Shows current config or updates specific settings.

    Examples:
        ars config --show
        ars config --backend git
        ars config --path ~/new-store-path
        ars config --repo-url git@github.com:user/new-repo.git
        ars config --targets .cursor,.kiro,.vscode
        ars config --debug
    """
    setup_logging(debug)

    try:
        # Load existing configuration
        config_manager = ConfigManager()
        try:
            current_config = config_manager.load()
        except FileNotFoundError:
            raise ARSyncError(
                "Configuration not found",
                ErrorCategory.USER_INPUT,
                recovery_steps=[
                    "Run 'ars setup' first to initialize configuration",
                    "Example: ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git"
                ]
            )

        # If show flag is set or no options provided, display current config
        if show or (backend is None and path is None and repo_url is None and targets is None):
            typer.echo("Current configuration:\n")
            typer.echo(f"Backend:         {current_config.backend}")
            typer.echo(f"Store path:      {current_config.store_path}")
            typer.echo(f"Repository URL:  {current_config.repo_url if current_config.repo_url else '(not set)'}")
            typer.echo(f"Default targets: {', '.join(current_config.default_targets)}")
            typer.echo(f"Auto sync:       {current_config.auto_sync}")
            typer.echo(f"Backup originals: {current_config.backup_originals}")
            typer.echo(f"Backup directory: {current_config.backup_dir}")
            typer.echo(f"\nConfig file: {ConfigManager.CONFIG_PATH}")
            return

        # Update configuration
        updated = False

        if backend is not None:
            if backend not in ['git', 'local']:
                raise ARSyncError(
                    f"Invalid backend: {backend}",
                    ErrorCategory.USER_INPUT,
                    recovery_steps=[
                        "Use 'git' or 'local' as the backend"
                    ]
                )
            current_config.backend = backend
            updated = True
            typer.echo(f"✓ Backend set to: {backend}")

        if path is not None:
            expanded_path = str(Path(path).expanduser().resolve())
            current_config.store_path = expanded_path
            updated = True
            typer.echo(f"✓ Store path set to: {expanded_path}")

        if repo_url is not None:
            current_config.repo_url = repo_url
            updated = True
            typer.echo(f"✓ Repository URL set to: {repo_url}")

        if targets is not None:
            target_list = [t.strip() for t in targets.split(',')]
            current_config.default_targets = target_list
            updated = True
            typer.echo(f"✓ Default targets set to: {', '.join(target_list)}")

        if updated:
            config_manager.save(current_config)
            typer.echo(f"\n✓ Configuration updated and saved to {ConfigManager.CONFIG_PATH}")

    except ARSyncError as e:
        typer.echo(e.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("ARSyncError occurred during config")
        raise typer.Exit(code=1)
    except Exception as e:
        error = ARSyncError(
            f"Configuration operation failed: {str(e)}",
            ErrorCategory.FILE_SYSTEM,
            recovery_steps=[
                "Check file permissions",
                "Ensure configuration file is not corrupted"
            ]
        )
        typer.echo(error.format_error(), err=True)
        if DEBUG_MODE:
            logger.exception("Unexpected error occurred during config")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
