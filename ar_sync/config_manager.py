"""Configuration manager for ar-sync local configuration.

This module handles reading, writing, and validating the local configuration file
stored at ~/.config/ar-sync/config.yaml. It ensures atomic writes to prevent
corruption and validates required fields.
"""

from pathlib import Path

import yaml

from ar_sync.models import LocalConfig


class ConfigManager:
    """Manages local configuration file for ar-sync.

    The configuration file is stored at ~/.config/ar-sync/config.yaml and contains
    settings like backend type, store path, and repository URL.

    Attributes:
        CONFIG_PATH: Path to the configuration file
        config: Currently loaded configuration (None if not loaded)
    """

    CONFIG_PATH = Path.home() / ".config" / "ar-sync" / "config.yaml"

    def __init__(self) -> None:
        """Initialize ConfigManager with no loaded configuration."""
        self.config: LocalConfig | None = None

    def load(self) -> LocalConfig:
        """Load configuration from disk.

        Reads the YAML configuration file and parses it into a LocalConfig object.
        Automatically migrates 'github' backend to 'git' for backward compatibility.

        Returns:
            LocalConfig: Parsed configuration object

        Raises:
            FileNotFoundError: If configuration file does not exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        if not self.CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Configuration file not found at {self.CONFIG_PATH}. "
                "Please run 'ars setup' to initialize."
            )

        with open(self.CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Migrate 'github' to 'git' for backward compatibility
        if data.get("backend") == "github":
            data["backend"] = "git"
            # Save migrated config
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        # Create LocalConfig from loaded data
        config = LocalConfig(
            version=data["version"],
            backend=data["backend"],
            store_path=data["store_path"],
            repo_url=data.get("repo_url"),  # Optional field
            default_targets=data.get("default_targets", []),
            auto_sync=data.get("auto_sync", False),
            backup_originals=data.get("backup_originals", True),
            backup_dir=data.get("backup_dir", ""),
        )

        # Validate before returning
        self.validate(config)

        self.config = config
        return self.config

    def save(self, config: LocalConfig) -> None:
        """Save configuration to disk with atomic write.

        Uses atomic write pattern (write to temp file, then rename) to prevent
        corruption if the write operation is interrupted.

        Args:
            config: Configuration object to save

        Raises:
            ValueError: If configuration validation fails
            OSError: If file write operation fails
        """
        # Validate before saving
        self.validate(config)

        # Ensure parent directory exists
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data for YAML serialization
        data = {
            "version": config.version,
            "backend": config.backend,
            "store_path": config.store_path,
            "default_targets": config.default_targets,
            "auto_sync": config.auto_sync,
            "backup_originals": config.backup_originals,
            "backup_dir": config.backup_dir,
        }

        # Add repo_url only if it's set
        if config.repo_url:
            data["repo_url"] = config.repo_url

        # Atomic write: write to temp file then rename
        temp_path = self.CONFIG_PATH.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

            # Atomic rename
            temp_path.replace(self.CONFIG_PATH)
        except Exception:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

        self.config = config

    def validate(self, config: LocalConfig) -> None:
        """Validate configuration fields.

        Checks that all required fields are present and have valid values.

        Args:
            config: Configuration object to validate

        Raises:
            ValueError: If any validation check fails
        """
        # Validate backend
        if not config.backend:
            raise ValueError("backend field is required")

        if config.backend not in ["git", "local"]:
            raise ValueError(
                f"Unsupported backend: {config.backend}. Supported backends: 'git', 'local'"
            )

        # Validate store_path
        if not config.store_path:
            raise ValueError("store_path field is required")

        # repo_url is optional (can use git backend locally without remote)

        # Validate version
        if config.version != 1:
            raise ValueError(
                f"Unsupported configuration version: {config.version}. Expected version 1."
            )
