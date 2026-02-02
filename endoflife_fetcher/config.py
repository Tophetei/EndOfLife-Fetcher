"""Configuration loading and management."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pragma: no cover


@dataclass
class Config:
    """Configuration container with defaults."""

    timeout: float = 15.0
    max_retries: int = 3
    warn_days: int = 0
    quiet: bool = False
    one_file: bool = False
    lts: bool = False
    active: bool = False
    output_dir: str = "Output"
    combined_filename: str = "all-products-eol.json"
    products: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)


def find_config_files() -> list[Path]:
    """
    Find config files in priority order (lowest to highest).

    Returns:
        List of existing config file paths:
        - ~/.config/endoflife-fetcher/config.toml (user config)
        - ./endoflife-fetcher.toml (local config)
    """
    config_files = []

    # 1. User config (XDG standard)
    user_config = Path.home() / ".config" / "endoflife-fetcher" / "config.toml"
    if user_config.exists():
        config_files.append(user_config)

    # 2. Local config
    local_config = Path("endoflife-fetcher.toml")
    if local_config.exists():
        config_files.append(local_config)

    return config_files


def load_config(config_path: Path | str | None = None) -> Config:
    """
    Load and merge configuration from files.

    Args:
        config_path: Explicit config file path (if provided, only this file is loaded)

    Priority (lowest to highest):
    1. Built-in defaults
    2. User config (~/.config/endoflife-fetcher/config.toml)
    3. Local config (./endoflife-fetcher.toml)
    4. Explicit --config path (replaces auto-discovery)

    Returns:
        Config object with merged settings

    Raises:
        FileNotFoundError: If explicit config_path doesn't exist
    """
    config = Config()  # Start with defaults

    # Determine which files to load
    if config_path is not None:
        # Explicit path: only load this file, error if not found
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        config_files = [path]
    else:
        # Auto-discovery
        config_files = find_config_files()

    # Mapping of config keys to their type converters
    field_types: dict[str, type] = {
        "timeout": float,
        "max_retries": int,
        "warn_days": int,
        "quiet": bool,
        "one_file": bool,
        "lts": bool,
        "active": bool,
        "output_dir": str,
        "combined_filename": str,
    }

    for file_path in config_files:
        try:
            with open(file_path, "rb") as f:
                file_config = tomllib.load(f)

            # Apply typed fields
            for key, converter in field_types.items():
                if key in file_config:
                    setattr(config, key, converter(file_config[key]))

            # Handle special cases
            if "products" in file_config:
                config.products = list(file_config["products"])
            if "groups" in file_config:
                config.groups.update(file_config["groups"])

        except tomllib.TOMLDecodeError as e:
            # Warn but don't fail - config errors shouldn't break the tool
            print(f"Warning: Invalid TOML in {file_path}: {e}", file=sys.stderr)
        except OSError as e:
            # File exists but can't be read - warn
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return config
