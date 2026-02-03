"""
Global pytest configuration for ar-sync tests.

This module provides fixtures that ensure test isolation from production config and store.
"""

import os
from pathlib import Path

import pytest

from ar_sync.config_manager import ConfigManager


@pytest.fixture(scope="function", autouse=True)
def isolate_config_and_store(tmp_path, monkeypatch):
    """
    Automatically isolate all tests from production config and store.

    This fixture runs automatically for every test function and ensures:
    1. ConfigManager uses a temporary directory instead of ~/.config/ar-sync
    2. Store operations use temporary directory instead of ~/.ar-sync-store
    3. Tests cannot accidentally modify production configuration or store
    4. Each test gets a clean, isolated environment

    Args:
        tmp_path: pytest's temporary directory fixture
        monkeypatch: pytest's monkeypatch fixture for safe patching
    """
    # Create isolated config directory for this test
    test_config_dir = tmp_path / "test_config"
    test_config_dir.mkdir(parents=True, exist_ok=True)
    test_config_path = test_config_dir / "config.yaml"

    # Create isolated store directory for this test
    test_store_dir = tmp_path / "test_store"
    test_store_dir.mkdir(parents=True, exist_ok=True)

    # Patch ConfigManager to use test directory
    monkeypatch.setattr(ConfigManager, "CONFIG_PATH", test_config_path)

    # Store original Path methods
    original_expanduser = Path.expanduser

    def safe_expanduser(self):
        """Prevent tests from accessing real home directory paths."""
        result = original_expanduser(self)
        result_str = str(result)

        # Redirect config directory
        if ".config/ar-sync" in result_str:
            return test_config_dir / result.name

        # Redirect store directory
        if ".ar-sync-store" in result_str:
            return test_store_dir / result.name

        return result

    def safe_home():
        """Return test home directory instead of real home."""
        return tmp_path / "home"

    monkeypatch.setattr(Path, "expanduser", safe_expanduser)
    monkeypatch.setattr(Path, "home", staticmethod(safe_home))

    # Also patch os.path.expanduser for string paths
    original_os_expanduser = os.path.expanduser

    def safe_os_expanduser(path):
        """Prevent os.path.expanduser from accessing real home."""
        result = original_os_expanduser(path)

        # Redirect config directory
        if ".config/ar-sync" in result:
            return str(test_config_dir / Path(result).name)

        # Redirect store directory
        if ".ar-sync-store" in result:
            return str(test_store_dir / Path(result).name)

        return result

    monkeypatch.setattr(os.path, "expanduser", safe_os_expanduser)

    yield {
        "config_path": test_config_path,
        "config_dir": test_config_dir,
        "store_dir": test_store_dir,
    }

    # Cleanup is automatic via tmp_path


@pytest.fixture(scope="function")
def isolated_store(tmp_path):
    """
    Provide an isolated store directory for tests.

    Note: This is now redundant with isolate_config_and_store,
    but kept for backward compatibility with existing tests.

    Returns:
        Path: Temporary store directory path
    """
    store_dir = tmp_path / "test_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir
