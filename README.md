# ar-sync

A Python CLI tool for synchronizing AI IDE configuration files across multiple machines. Uses Git as a storage backend to version control and synchronize configuration files like `.cursor`, `.kiro`, `.gemini`, `.qwen`, and `AGENTS.md`.

## Key Features

- Automatic synchronization through Git
- Symlink-based architecture to protect original files while connecting to central storage
- Safe backup of existing files
- Cross-platform support: macOS, Linux, Windows
- Simple and intuitive CLI commands

## Installation

### Install via pip

```bash
pip install ar-sync
```

### Install from source

```bash
git clone https://github.com/JINWOO-J/ar-sync.git
cd ar-sync
pip install -e .
```

## Requirements

- Python 3.10 or higher
- Git 2.0 or higher
- GitHub account and repository

## Quick Start

### 1. Initialize Global Configuration

First, create a GitHub repository to store configuration files, then initialize ar-sync:

```bash
# Create GitHub repository (via web or gh CLI)
gh repo create ar-sync-store --private

# Initialize ar-sync global configuration
ars setup \
  --backend git \
  --path ~/ar-sync-store \
  --repo-url git@github.com:JINWOO-J/ar-sync-store.git
```

### 2. Initialize Project

Add configuration files from your project directory to the store:

```bash
cd ~/my-project
ars init
```

By default, `.cursor`, `.kiro`, `.gemini`, `.qwen`, and `AGENTS.md` files/directories are synchronized.

Alternatively, to explicitly add only:

```bash
ars add
```

You can also specify a custom project name or custom targets:

```bash
# Specify project name
ars init --name my-custom-name

# Specify custom targets
ars init --targets .cursor,.kiro,.vscode,AGENTS.md
```

### 3. Connect from Another Machine

To use the same configuration on another machine:

```bash
# 1. Initialize ar-sync global configuration (use the same repository)
ars setup \
  --backend git \
  --path ~/ar-sync-store \
  --repo-url git@github.com:JINWOO-J/ar-sync-store.git

# 2. Navigate to project directory
cd ~/my-project

# 3. Link configuration (for git backend)
ars link

# Or use pull (file copy method)
ars pull
```

If existing files are present, use the `--force` option to overwrite:

```bash
ars link --force
```

### 4. Check Status

View registered projects and synchronization status:

```bash
ars status
```

Example output:
```
Store: /Users/username/ar-sync-store
Remote: git@github.com:JINWOO-J/ar-sync-store.git

Registered projects (2):

→ my-project
    Targets: .cursor, .kiro, .gemini, .qwen, AGENTS.md
    Machines (2):
      - macbook-pro (linked: 2025-01-21T10:00:00Z)
      - office-desktop (linked: 2025-01-22T09:00:00Z)

  other-project
    Targets: .cursor, AGENTS.md
    Machines (1):
      - macbook-pro (linked: 2025-01-20T15:00:00Z)

→ Current directory is registered as 'my-project'
```

### 5. Synchronization

Synchronize changes with the remote repository:

```bash
# Full synchronization (pull + push)
ars sync

# Specify commit message
ars sync -m "Update cursor rules"

# Pull only
ars sync --pull

# Push only
ars sync --push
```

### 6. Pull and Push (Project-Level Synchronization)

`ars sync` performs synchronization between the store and remote repository. Use `pull` and `push` commands for synchronization between project directory and store:

```bash
# Copy files from store to project (includes remote pull for git backend)
ars pull

# Copy files from project to store (includes remote push for git backend)
ars push

# Specify commit message (git backend)
ars push -m "Update project settings"
```

**Workflow Example (git backend):**

Changes on Machine A:
```bash
cd ~/my-project
# Modify files...
ars push -m "Update settings"  # project → store → remote
```

Synchronize on Machine B:
```bash
cd ~/my-project
ars pull  # remote → store → project
```

## Command Reference

### `ars setup`

Initialize global configuration and storage backend. This is a one-time setup command.

**Options:**
- `--backend`: Storage backend type (`git` or `local`)
- `--path`: Local path for the store
- `--repo-url`: Git repository URL (required for git backend)

**Examples:**
```bash
# Configure with git backend
ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git

# Configure with local backend (Dropbox, iCloud, etc.)
ars setup --backend local --path ~/Dropbox/ar-sync-store
```

### `ars init`

Initialize current project and add to store. 
For local backend, symlinks are automatically created.

**Options:**
- `--name`: Project name (default: current directory name)
- `--targets`: Comma-separated target list (default: `.cursor,.kiro,.gemini,.qwen,AGENTS.md`)

**Examples:**
```bash
# Initialize with default targets
ars init

# Specify project name
ars init --name my-project

# Specify custom targets
ars init --targets .cursor,.kiro,.vscode,AGENTS.md
```

### `ars add`

Add current project to store.

**Options:**
- `--name`: Project name (default: current directory name)
- `--targets`: Comma-separated target list (default: `.cursor,.kiro,.gemini,.qwen,AGENTS.md`)

**Examples:**
```bash
# Add with default targets
ars add

# Specify project name
ars add --name my-project

# Specify custom targets
ars add --targets .cursor,.kiro,.vscode,AGENTS.md
```

### `ars link`

Link store configuration to current directory.

**Options:**
- `--project`: Project name (default: current directory name)
- `--force, -f`: Overwrite existing files without backup

**Examples:**
```bash
# Link using current directory name
ars link

# Link specific project
ars link --project my-project

# Overwrite existing files
ars link --force
```

### `ars status`

Display registered projects and synchronization status.

**Example:**
```bash
ars status
```

### `ars sync`

Synchronize with remote repository (store ↔ remote).

**Options:**
- `-m`: Commit message (default: auto-generated)
- `--pull`: Pull only
- `--push`: Push only

**Examples:**
```bash
# Full synchronization
ars sync

# Specify commit message
ars sync -m "Update settings"

# Pull only
ars sync --pull

# Push only
ars sync --push
```

### `ars pull`

Copy files from store to current project directory (store → project).
For git backend, pulls from remote to store first.

**Options:**
- `--project`: Project name (default: current directory name)

**Examples:**
```bash
# Pull to current directory
ars pull

# Pull specific project
ars pull --project my-project
```

### `ars push`

Copy files from current project directory to store (project → store).
For git backend, also pushes from store to remote.

**Options:**
- `--project`: Project name (default: current directory name)
- `-m`: Commit message (git backend only, default: "Update project: {project_name}")

**Examples:**
```bash
# Push from current directory
ars push

# Specify commit message
ars push -m "Update cursor rules"

# Push specific project
ars push --project my-project
```

### `ars config`

View or modify configuration settings.

**Options:**
- `--show`: Display current configuration (same as running without options)
- `--backend`: Change backend (`git` or `local`)
- `--path`: Change store path
- `--repo-url`: Change repository URL
- `--targets`: Change default targets

**Examples:**
```bash
# View current configuration
ars config
ars config --show

# Change backend
ars config --backend local

# Change store path
ars config --path ~/new-store-path

# Change repository URL
ars config --repo-url git@github.com:user/new-repo.git

# Change default targets
ars config --targets .cursor,.kiro,.vscode
```

## Configuration Files

### Local Configuration (~/.config/ar-sync/config.yaml)

```yaml
version: 1
backend: git  # 'git' or 'local'
store_path: /Users/username/ar-sync-store
repo_url: git@github.com:username/ar-sync-store.git  # git backend only
default_targets:
  - .cursor
  - .kiro
  - .gemini
  - .qwen
  - AGENTS.md
auto_sync: false
backup_originals: true
backup_dir: /Users/username/.config/ar-sync/backups
```

### Store Metadata ({store_path}/.ar-sync.yaml)

```yaml
version: 1
created_at: 2025-01-21T10:00:00Z
projects:
  my-project:
    added_at: 2025-01-21T10:00:00Z
    targets:
      - .cursor
      - .kiro
      - .gemini
      - .qwen
      - AGENTS.md
    machines:
      - hostname: macbook-pro
        linked_at: 2025-01-21T10:00:00Z
      - hostname: office-desktop
        linked_at: 2025-01-22T09:00:00Z
```

## File Structure

```
~/.config/ar-sync/
├── config.yaml              # Local configuration
└── backups/                 # Backup directory
    └── my-project_20250121_100000/
        └── .cursor/

~/ar-sync-store/             # Store directory
├── .git/                    # Git repository
├── .ar-sync.yaml            # Store metadata
├── my-project/
│   ├── .cursor/
│   ├── .kiro/
│   ├── .gemini/
│   ├── .qwen/
│   └── AGENTS.md
└── other-project/
    ├── .cursor/
    └── AGENTS.md
```

## Platform-Specific Notes

### Windows

To create symlinks on Windows, Developer Mode must be enabled:

1. Settings > Update & Security > For developers
2. Enable "Developer Mode"
3. Restart terminal

Alternatively, run commands with administrator privileges.

### macOS / Linux

Generally no additional configuration is required. If file permission issues occur:

```bash
chmod +w ~/my-project
```

## Troubleshooting

### Git Authentication Errors

Verify SSH keys are configured:

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add SSH key to GitHub
cat ~/.ssh/id_ed25519.pub
# Add to GitHub Settings > SSH and GPG keys
```

### Symlink Creation Failures

- **Windows**: Enable Developer Mode or use administrator privileges
- **macOS/Linux**: Check directory write permissions

### Conflicts

If Git conflicts occur, resolve manually:

```bash
cd ~/ar-sync-store
# Resolve conflicts
git add .
git commit
ars sync
```

## Development

### Development Environment Setup

```bash
# Clone repository
git clone https://github.com/JINWOO-J/ar-sync.git
cd ar-sync

# Install development dependencies
make install-dev
# or
pip install -e ".[dev]"
```

### Makefile Commands

The project automates common development tasks through Makefile:

```bash
# View help
make help

# Install in development mode
make install-dev

# Run CLI (during development)
make run
# or run directly
python -m ar_sync.cli --help

# Testing
make test              # Run all tests
make test-cov          # Include coverage report
make test-verbose      # Verbose output

# Code quality
make lint              # Run Ruff linter
make type-check        # Run Mypy type checker
make format            # Format code

# Build and deployment
make clean             # Remove build artifacts
make build             # Build distribution package
make publish-test      # Deploy to TestPyPI
make publish           # Deploy to PyPI

# Full verification (CI/CD)
make verify            # Run all checks
```

### Running Tests

```bash
# Using Makefile
make test
make test-cov

# Direct execution
pytest
pytest --cov=ar_sync --cov-report=html

# Run property-based tests only
pytest tests/test_properties*.py -v
```

### Type Checking

```bash
make type-check
# or
mypy --strict ar_sync/
```

### PyPI Deployment

```bash
# 1. Deploy to TestPyPI first for testing
make publish-test

# 2. Deploy to actual PyPI after testing
make publish
```

