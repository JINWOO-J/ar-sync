# Test Suite

## Module Context

Comprehensive test suite for ar-sync CLI tool covering unit tests, integration tests, and property-based tests. Ensures code quality, correctness, and prevents regressions.

**Role:** Validate all functionality with 95%+ coverage while maintaining test isolation from production environment.

**Dependencies:**
- pytest 7.4+ (test framework)
- pytest-cov (coverage reporting)
- hypothesis 6.92+ (property-based testing)
- All ar_sync modules

**Test Count:** 472 tests (471 passing, 1 property test skipped)

## Tech Stack & Constraints

**Testing Stack:**
- pytest with fixtures and parametrize
- hypothesis for property-based tests
- monkeypatch for environment isolation
- tmp_path for temporary file operations
- Rich for output capture testing

**Critical Constraint:**
- Tests MUST NEVER modify production config (`~/.config/ar-sync/config.yaml`)
- Tests MUST NEVER modify production store (`~/.ar-sync-store/`)
- All tests MUST use `isolate_config_and_store` fixture from `conftest.py`

## Implementation Patterns

### Test File Structure

```
tests/
├── conftest.py                          # Global fixtures (CRITICAL)
├── test_config_manager.py               # ConfigManager tests
├── test_models.py                       # Data model tests
├── test_git_backend.py                  # Git operations tests
├── test_project_manager_integration.py  # Project management tests
├── test_store_manager.py                # Store metadata tests
├── test_cli_workflows.py                # CLI command tests
├── test_cli_commands_integration.py     # CLI integration tests
├── test_diff_engine.py                  # Diff detection tests
├── test_merge_engine.py                 # Merge operation tests
├── test_conflict_resolver.py            # Conflict UI tests
├── test_bidirectional_sync.py           # Sync orchestration tests
├── test_atomic_ops.py                   # Atomic operations tests
├── test_template_manager.py             # Template system tests
├── test_template_selector.py            # Template UI tests
├── test_template_copier.py              # Template copy tests
├── test_error_handling.py               # Error handling tests
├── test_properties_config.py            # Property-based config tests
└── test_properties_store.py             # Property-based store tests
```

### Critical Fixture: isolate_config_and_store

**Location:** `tests/conftest.py`

**Purpose:** Automatically isolate ALL tests from production environment

**Implementation:**
```python
@pytest.fixture(autouse=True)
def isolate_config_and_store(tmp_path, monkeypatch):
    """Isolate tests from production config and store."""
    test_home = tmp_path / "test_home"
    test_home.mkdir()
    
    test_config = test_home / ".config" / "ar-sync"
    test_store = test_home / ".ar-sync-store"
    
    # Patch ConfigManager
    monkeypatch.setattr(
        "ar_sync.config_manager.ConfigManager.CONFIG_PATH",
        test_config / "config.yaml"
    )
    
    # Patch Path.expanduser()
    def mock_expanduser(self):
        s = str(self)
        if s.startswith("~/.config/ar-sync"):
            return test_config / s[len("~/.config/ar-sync/"):]
        elif s.startswith("~/.ar-sync-store"):
            return test_store / s[len("~/.ar-sync-store/"):]
        elif s.startswith("~/"):
            return test_home / s[2:]
        return self
    
    monkeypatch.setattr(Path, "expanduser", mock_expanduser)
    
    # Patch Path.home()
    monkeypatch.setattr(Path, "home", lambda: test_home)
    
    # Patch os.path.expanduser()
    def mock_os_expanduser(path):
        if path.startswith("~/.config/ar-sync"):
            return str(test_config / path[len("~/.config/ar-sync/"):])
        elif path.startswith("~/.ar-sync-store"):
            return str(test_store / path[len("~/.ar-sync-store/"):])
        elif path.startswith("~/"):
            return str(test_home / path[2:])
        return path
    
    monkeypatch.setattr("os.path.expanduser", mock_os_expanduser)
    
    yield test_home
```

**Usage:** Automatically applied to all tests (autouse=True)

### Test Naming Convention

```python
def test_<function>_<scenario>_<expected>():
    """Test that <function> <scenario> results in <expected>."""
```

Examples:
- `test_setup_creates_config_file()`
- `test_init_with_existing_files_creates_backup()`
- `test_sync_with_conflicts_prompts_user()`
- `test_pull_missing_targets_copies_from_store()`

### Parametrized Tests

```python
@pytest.mark.parametrize("backend,repo_url", [
    ("git", "git@github.com:user/repo.git"),
    ("local", None),
])
def test_setup_with_different_backends(backend, repo_url):
    """Test setup works with different backend types."""
```

### Mocking User Input

```python
def test_conflict_resolution_with_enter_key(monkeypatch):
    """Test that Enter key uses smart default."""
    monkeypatch.setattr('builtins.input', lambda _: '')
    resolver = ConflictResolver()
    resolution = resolver.prompt_resolution(change, local, store)
    assert resolution == ConflictResolution.USE_REMOTE
```

### Testing CLI Commands

```python
from typer.testing import CliRunner
from ar_sync.cli import app

def test_status_command_shows_projects():
    """Test that status command displays registered projects."""
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Registered projects" in result.stdout
```

### Testing File Operations

```python
def test_atomic_copy_with_rollback(tmp_path):
    """Test that atomic operations rollback on failure."""
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("source")
    dst.write_text("original")
    
    atomic = AtomicOperations()
    try:
        atomic.copy_file(src, dst)
        raise Exception("Simulated failure")
    except:
        atomic.rollback()
    
    assert dst.read_text() == "original"
```

## Testing Strategy

### Unit Tests

**Scope:** Individual functions and classes in isolation

**Pattern:**
```python
def test_config_manager_load_creates_default():
    """Test that load creates default config if not exists."""
    manager = ConfigManager()
    config = manager.load()
    assert config.backend == "git"
    assert config.store_path is not None
```

**Coverage Target:** 100% for core modules

### Integration Tests

**Scope:** Multiple components working together

**Pattern:**
```python
def test_full_sync_workflow(tmp_path):
    """Test complete sync workflow: init → modify → sync → pull."""
    # Setup
    setup_store(tmp_path)
    project_path = tmp_path / "project"
    
    # Init
    init_project(project_path)
    
    # Modify
    (project_path / ".cursor" / "rules.md").write_text("new rules")
    
    # Sync
    sync_result = sync_project(project_path)
    assert sync_result.success
    
    # Pull on another machine
    other_path = tmp_path / "other"
    pull_result = pull_project(other_path)
    assert (other_path / ".cursor" / "rules.md").read_text() == "new rules"
```

**Coverage Target:** 90%+ for workflows

### Property-Based Tests

**Scope:** Invariants and edge cases

**Pattern:**
```python
from hypothesis import given, strategies as st

@given(st.lists(st.text(min_size=1, max_size=100)))
def test_diff_engine_detects_all_changes(file_list):
    """Test that diff engine detects all file changes."""
    assume(len(file_list) > 0)
    
    local = create_files(tmp_path / "local", file_list)
    store = create_files(tmp_path / "store", file_list[:len(file_list)//2])
    
    changes = diff_engine.detect_changes(local, store, file_list)
    
    # Invariant: detected changes should match actual differences
    assert len(changes) == len(file_list) - len(file_list)//2
```

**Coverage Target:** Critical algorithms only

## Test Commands

```bash
# Run all tests
make test
pytest

# Run with coverage
make test-cov
pytest --cov=ar_sync --cov-report=html

# Run specific test file
pytest tests/test_config_manager.py -v

# Run specific test
pytest tests/test_config_manager.py::test_load_creates_default -v

# Run tests matching pattern
pytest -k "sync" -v

# Run with debug output
pytest -v -s

# Run property-based tests only
pytest tests/test_properties*.py -v

# Run integration tests only
pytest tests/test_*_integration.py -v

# Run with coverage report
pytest --cov=ar_sync --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=ar_sync --cov-report=html
open htmlcov/index.html
```

## Local Golden Rules

### Do's

1. **Always use isolate_config_and_store fixture** (automatic via autouse)
2. **Use tmp_path for file operations** (pytest built-in fixture)
3. **Use monkeypatch for environment variables** and function patching
4. **Mock external dependencies** (Git remote, network calls)
5. **Test both success and failure paths**
6. **Use descriptive test names** following convention
7. **Add docstrings to tests** explaining what is tested
8. **Parametrize similar tests** to reduce duplication
9. **Use CliRunner for CLI tests** (Typer testing utility)
10. **Assert specific error messages** not just exception types

### Don'ts

1. **Never access production config** (`~/.config/ar-sync/config.yaml`)
2. **Never access production store** (`~/.ar-sync-store/`)
3. **Never use absolute paths** in tests (use tmp_path)
4. **Never skip cleanup** (fixtures handle this automatically)
5. **Never use sleep()** for timing (use mocks or events)
6. **Never test implementation details** (test behavior)
7. **Never commit commented-out tests** (delete or fix)
8. **Never use print()** for debugging (use pytest -s or logging)
9. **Never assume test execution order** (tests must be independent)
10. **Never create symbolic links** without cleanup in fixture

## Common Test Patterns

### Testing Error Handling

```python
def test_setup_with_invalid_backend_raises_error():
    """Test that setup raises error for invalid backend."""
    with pytest.raises(ConfigError, match="Invalid backend"):
        setup(backend="invalid")
```

### Testing File Existence

```python
def test_init_creates_symlinks(tmp_path):
    """Test that init creates symlinks to store."""
    project = tmp_path / "project"
    store = tmp_path / "store"
    
    init_project(project, store)
    
    cursor_link = project / ".cursor"
    assert cursor_link.is_symlink()
    assert cursor_link.resolve() == store / "project" / ".cursor"
```

### Testing CLI Output

```python
def test_status_shows_project_info():
    """Test that status command shows project information."""
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    
    assert result.exit_code == 0
    assert "Registered projects" in result.stdout
    assert "my-project" in result.stdout
```

### Testing Conflict Resolution

```python
def test_conflict_resolver_smart_default_only_in_store(monkeypatch):
    """Test smart default for only_in_store conflict."""
    monkeypatch.setattr('builtins.input', lambda _: '')  # Enter key
    
    change = FileChange(
        path=".cursor/rules.md",
        change_type=ChangeType.ONLY_IN_STORE
    )
    
    resolver = ConflictResolver()
    resolution = resolver.prompt_resolution(change, local, store)
    
    assert resolution == ConflictResolution.USE_REMOTE
```

## Debugging Failed Tests

```bash
# Run with verbose output
pytest tests/test_failing.py -vv

# Run with stdout/stderr
pytest tests/test_failing.py -s

# Run with pdb on failure
pytest tests/test_failing.py --pdb

# Run with last failed only
pytest --lf

# Run with coverage to find untested code
pytest --cov=ar_sync --cov-report=term-missing
```

## Coverage Analysis

```bash
# Generate coverage report
pytest --cov=ar_sync --cov-report=html

# View in browser
open htmlcov/index.html

# Check coverage percentage
pytest --cov=ar_sync --cov-report=term

# Find uncovered lines
pytest --cov=ar_sync --cov-report=term-missing
```

## CI/CD Integration

```bash
# Full verification (runs in CI)
make verify

# Equivalent to:
make lint          # Ruff linter
make type-check    # Mypy strict
make test-cov      # Tests with coverage
```

## Performance Testing

```bash
# Measure test execution time
pytest --durations=10

# Profile slow tests
pytest --profile

# Run with minimal output
pytest -q
```
