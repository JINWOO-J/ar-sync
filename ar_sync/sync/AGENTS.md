# Bidirectional Sync Module

## Module Context

This module implements the core bidirectional synchronization engine for ar-sync. It handles conflict detection, resolution, and merge operations between local projects and the central store.

**Role:** Provide safe, atomic, and user-friendly synchronization with intelligent conflict resolution.

**Dependencies:**
- `ar_sync.models` (LocalConfig, StoreMetadata)
- `ar_sync.git_backend` (GitBackend for remote operations)
- `pathlib.Path` (file system operations)
- `rich` (terminal UI for conflict prompts)

**Used By:**
- `ar_sync.cli` (sync, pull, push commands)
- Integration tests

## Tech Stack & Constraints

**Libraries:**
- Rich 13.0+ for terminal UI (Table, Prompt, Syntax highlighting)
- Python 3.10+ with dataclasses
- No external diff tools (pure Python implementation)

**Constraints:**
- All file operations must be atomic (rollback on failure)
- Conflict resolution must be interactive (no silent overwrites)
- File previews limited to 20 lines or 1000 chars
- All messages in English only

## Implementation Patterns

### File Structure

```
ar_sync/sync/
├── __init__.py              # Module exports
├── models.py                # SyncOptions, FileChange, ConflictResolution
├── diff_engine.py           # DiffEngine: detect changes
├── merge_engine.py          # MergeEngine: apply resolutions
├── conflict_resolver.py     # ConflictResolver: interactive UI
├── bidirectional_sync.py    # BidirectionalSync: orchestrator
└── atomic_ops.py            # AtomicOperations: safe file ops
```

### Core Classes

**DiffEngine:**
```python
def detect_changes(
    local_path: Path,
    store_path: Path,
    targets: list[str]
) -> list[FileChange]:
    """Detect differences between local and store."""
```

**MergeEngine:**
```python
def apply_resolution(
    change: FileChange,
    resolution: ConflictResolution,
    local_path: Path,
    store_path: Path
) -> bool:
    """Apply user's conflict resolution choice."""
```

**ConflictResolver:**
```python
def prompt_resolution(
    change: FileChange,
    local_path: Path,
    store_path: Path
) -> ConflictResolution:
    """Interactive prompt with smart defaults."""
```

**BidirectionalSync:**
```python
def sync(self, options: SyncOptions) -> SyncResult:
    """Main sync orchestrator: pull → resolve → push."""
```

### Naming Conventions

- Files: `snake_case.py`
- Classes: `PascalCase` (e.g., `DiffEngine`)
- Functions: `snake_case` (e.g., `detect_changes`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_PREVIEW_LINES`)
- Test files: `test_<module>.py`

### Error Handling Pattern

```python
from ar_sync.errors import SyncError

try:
    result = operation()
except FileNotFoundError as e:
    raise SyncError(f"File not found: {e}") from e
except PermissionError as e:
    raise SyncError(f"Permission denied: {e}") from e
```

### Atomic Operations Pattern

```python
from ar_sync.sync.atomic_ops import AtomicOperations

atomic = AtomicOperations()
try:
    atomic.copy_file(src, dst)
    atomic.delete_file(old)
    atomic.commit()  # All or nothing
except Exception:
    atomic.rollback()  # Restore original state
    raise
```

## Testing Strategy

### Test Files

- `tests/test_diff_engine.py` — DiffEngine unit tests
- `tests/test_merge_engine.py` — MergeEngine unit tests
- `tests/test_conflict_resolver.py` — ConflictResolver UI tests
- `tests/test_bidirectional_sync.py` — Integration tests
- `tests/test_atomic_ops.py` — Atomic operations tests

### Test Commands

```bash
# Run sync module tests only
pytest tests/test_*sync*.py tests/test_*engine*.py tests/test_*resolver*.py -v

# With coverage
pytest tests/test_*sync*.py --cov=ar_sync.sync --cov-report=term-missing

# Run specific test
pytest tests/test_conflict_resolver.py::test_prompt_resolution_only_in_store -v
```

### Test Patterns

**Mocking User Input:**
```python
def test_prompt_with_default(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: '')  # Simulate Enter key
    resolver = ConflictResolver()
    resolution = resolver.prompt_resolution(change, local, store)
    assert resolution == ConflictResolution.USE_REMOTE
```

**Testing Atomic Operations:**
```python
def test_atomic_rollback(tmp_path):
    atomic = AtomicOperations()
    original = tmp_path / "file.txt"
    original.write_text("original")
    
    try:
        atomic.copy_file(src, original)
        raise Exception("Simulated failure")
    except:
        atomic.rollback()
    
    assert original.read_text() == "original"  # Restored
```

**Property-Based Testing:**
```python
from hypothesis import given, strategies as st

@given(st.lists(st.text(min_size=1)))
def test_diff_engine_symmetry(file_paths):
    """Changes detected should be symmetric."""
    changes_a_to_b = diff_engine.detect_changes(path_a, path_b, file_paths)
    changes_b_to_a = diff_engine.detect_changes(path_b, path_a, file_paths)
    assert len(changes_a_to_b) == len(changes_b_to_a)
```

## Local Golden Rules

### Do's

1. **Always use atomic operations** for file modifications
2. **Show file previews** for "only in X" conflicts (first 20 lines)
3. **Provide smart defaults** based on conflict type
4. **Use Rich tables** for conflict summaries
5. **Validate paths** before operations (exists, readable, writable)
6. **Log operations** at DEBUG level for troubleshooting
7. **Test with monkeypatch** for user input simulation

### Don'ts

1. **Never modify files** without user confirmation in interactive mode
2. **Never skip backups** before overwriting
3. **Never use shell commands** for file operations (use pathlib)
4. **Never assume file encoding** (always specify UTF-8)
5. **Never show full file content** in prompts (use preview limits)
6. **Never use Korean** in user-facing messages (English only)
7. **Never commit partial changes** (atomic or rollback)

## Conflict Resolution UX

### Message Format

```
Status: <conflict_type>
Description: <clear explanation>
  Local: <local_path>
  Remote: <store_path>

--- <Local/Remote> file preview ---
<first 20 lines or 1000 chars>
---

Choose resolution: [l]ocal / [r]emote / [m]erge / [s]kip
(Press Enter for default: <smart_default>)
>
```

### Smart Defaults

- `only_in_store` → Default: `[r]emote` (copy to local)
- `only_in_local` → Default: `[l]ocal` (copy to store)
- `modified_both` → No default (explicit choice required)

### Conflict Types

1. **only_in_local:** File exists in project but not in store
   - Description: "This file exists in the current project but not in Store"
   - Default action: Copy to store

2. **only_in_store:** File exists in store but not in project
   - Description: "This file exists in Store but not in the current project"
   - Default action: Copy to local

3. **modified_both:** File modified differently in both locations
   - Description: "This file has been modified differently in both local and Store"
   - No default (user must choose)

## Performance Considerations

- File hashing: Use MD5 for change detection (fast, collision unlikely for config files)
- Lazy loading: Only read file content when needed (preview, merge)
- Batch operations: Group file operations to reduce I/O
- Progress indicators: Show progress for operations >1s

## Debug Commands

```bash
# Enable debug logging
ars sync -d

# Check diff without applying
ars sync --dry-run

# View conflict details
ars status --verbose
```

## Common Issues

**Issue:** Symlinks break after sync
**Solution:** Use `ars link --force` to recreate symlinks

**Issue:** Conflicts on every sync
**Solution:** Check file permissions, ensure write access to both local and store

**Issue:** Preview shows binary content
**Solution:** Add file extension to binary exclusion list in constants.py

**Issue:** Tests modify production store
**Solution:** Ensure `isolate_config_and_store` fixture is used (check tests/conftest.py)
