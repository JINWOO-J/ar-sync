# ar-sync: Principal Architect for AI Context & Governance

## Project Context & Operations

ar-sync is a Python CLI tool for synchronizing AI IDE configuration files across multiple machines using Git as a storage backend. The tool manages configuration files for 12+ AI IDEs (Claude, Cursor, Windsurf, Kiro, etc.) through symlink-based architecture and bidirectional synchronization.

**Business Goal:** Enable developers to maintain consistent AI IDE configurations across multiple development environments with version control and conflict resolution.

**Tech Stack:** Python 3.10+, Typer, GitPython, PyYAML, Rich, pytest, hypothesis

### Operational Commands

```bash
make install-dev          # Install with dev dependencies
make run                  # Run CLI during development
python -m ar_sync.cli     # Direct CLI execution
make test                 # Run all tests (489 tests)
make test-cov             # With coverage report
make lint                 # Ruff linter
make type-check           # Mypy strict mode
make format               # Code formatting
make verify               # Full CI/CD checks (lint + type-check + tests)
ars setup --backend git --path ~/ar-sync-store --repo-url git@github.com:user/repo.git
ars init                  # Initialize project
ars sync                  # Bidirectional sync
ars status                # View status
```

## Golden Rules

### Immutable Constraints

1. **Test Isolation:** ALL tests MUST use `isolate_config_and_store` fixture from `tests/conftest.py`. Production config (`~/.config/ar-sync/config.yaml`) and store (`~/.ar-sync-store/`) must NEVER be modified by tests.

2. **Type Safety:** Strict mypy mode is enforced. All functions must have complete type hints. No `Any` types without explicit justification.

3. **Backward Compatibility:** Configuration file format (`version: 1`) must remain compatible. Breaking changes require migration path.

4. **Git Safety:** Never force push to remote. Always handle merge conflicts through interactive resolution.

5. **Cross-Platform:** Code must work on macOS, Linux, and Windows. Use `Path` from `pathlib`, not string concatenation.

### Do's & Don'ts

**DO:**
- Use `Path.expanduser()` for home directory paths
- Use `monkeypatch` in pytest fixtures for environment isolation
- Validate user input before file operations
- Create backups before overwriting files
- Write property-based tests for data transformations
- Use English for all user-facing messages
- Follow TDD: write test first, then minimal implementation
- Run `make format` before committing
- Run `make lint` to verify code quality
- Run `make verify` before pushing
- Remove trailing whitespace and unused imports/variables

**DON'T:**
- Use `cat` for files >100 lines (use `rg` or `grep` instead)
- Hardcode paths (use config or constants)
- Modify production config/store in tests
- Use symbolic links in tests without cleanup
- Skip error handling for file operations
- Use emojis in code or documentation
- Commit without running `make verify`
- Break existing CLI command signatures
- Leave trailing whitespace or unused code

## Standards & References

### Code Conventions

- Line length: 100 characters (Ruff enforced)
- Import order: stdlib → third-party → local (Ruff I rule)
- Naming: snake_case for functions/variables, PascalCase for classes
- Docstrings: Google style for public APIs
- Error messages: Clear, actionable, English only
- Linting workflow: `make format` → `make lint` → `make type-check` → `make verify`
- Common Ruff rules: W291 (trailing whitespace), W293 (blank line whitespace), F401 (unused import), F841 (unused variable)

### Git Strategy

- Branch: `main` (protected)
- Commit format: `<type>: <description>` (e.g., `feat: add bidirectional sync`)
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- PR requirements: All tests pass, type check clean, no coverage regression

### Testing Strategy

- Unit tests: `tests/test_*.py` (one file per module)
- Integration tests: `tests/test_*_integration.py`
- Property tests: `tests/test_properties_*.py` (hypothesis)
- Coverage target: >90% (current: 77%)
- Test naming: `test_<function>_<scenario>_<expected>`

### Maintenance Policy

When code and rules diverge:
1. Identify the discrepancy (code review, test failure, user report)
2. Determine correct behavior (requirements, design docs)
3. Update code OR update rules (with justification)
4. Add regression test to prevent recurrence
5. Update related documentation

## Context Map (Action-Based Routing)

- **[CLI Commands](./ar_sync/cli.py)** — Typer-based CLI entry point, command definitions (setup, init, sync, status, etc.)

- **[Configuration Management](./ar_sync/config_manager.py)** — LocalConfig loading/saving, YAML serialization, path expansion

- **[Data Models](./ar_sync/models.py)** — LocalConfig, StoreMetadata, ProjectInfo dataclasses with validation

- **[Git Backend](./ar_sync/git_backend.py)** — Git operations (clone, pull, push, commit), remote synchronization

- **[Project Manager](./ar_sync/project_manager.py)** — Project registration, symlink creation, file operations

- **[Store Manager](./ar_sync/store_manager.py)** — Store metadata management, project tracking

- **[Bidirectional Sync Engine](./ar_sync/sync/AGENTS.md)** — Conflict detection, resolution, merge strategies

- **[Template System](./ar_sync/template_manager.py)** — Template scanning, metadata parsing, interactive selection

- **[Error Handling](./ar_sync/errors.py)** — Custom exceptions (ARSyncError, ConfigError, SyncError, etc.)

- **[Test Suite](./tests/AGENTS.md)** — Unit, integration, property-based tests with isolation fixtures

- **[Spec Documents](./.kiro/specs/)** — Requirements, design, tasks for features

## Architecture Notes

### Symlink-Based Design

Projects use symlinks pointing to store:
```
~/my-project/.cursor -> ~/ar-sync-store/my-project/.cursor
```

Benefits: Single source of truth, automatic sync, no file duplication
Tradeoffs: Requires symlink support (Windows Developer Mode)

### Bidirectional Sync Flow

```
Local Project <--pull/push--> Store <--sync--> Remote Git
```

- `ars pull`: remote → store → project
- `ars push`: project → store → remote
- `ars sync`: bidirectional with conflict resolution

### Conflict Resolution Strategy

1. Detect conflicts (DiffEngine)
2. Classify: only_in_local, only_in_store, modified_both
3. Interactive prompt with smart defaults
4. Apply resolution (MergeEngine)
5. Atomic operations with rollback on failure

## Performance Targets

- `ars status`: <500ms
- `ars sync` (no conflicts): <2s
- `ars init`: <1s
- Test suite: <30s (full run)
