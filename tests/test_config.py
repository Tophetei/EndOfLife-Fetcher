"""Tests for configuration loading."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from endoflife_fetcher import Config, find_config_files, load_config, parse_args


class TestConfigDataclass:
    """Tests for Config dataclass defaults."""

    def test_default_values(self):
        """Test Config has correct default values."""
        config = Config()
        assert config.timeout == 15.0
        assert config.max_retries == 3
        assert config.warn_days == 0
        assert config.quiet is False
        assert config.one_file is False
        assert config.lts is False
        assert config.active is False
        assert config.output_dir == "Output"
        assert config.combined_filename == "all-products-eol.json"
        assert config.products == []
        assert config.groups == {}


class TestFindConfigFiles:
    """Tests for config file discovery."""

    def test_no_config_files(self, tmp_path, monkeypatch):
        """Test returns empty list when no config files exist."""
        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            files = find_config_files()
        assert files == []

    def test_user_config_only(self, tmp_path, monkeypatch):
        """Test finds user config in ~/.config."""
        home = tmp_path / "home"
        config_dir = home / ".config" / "endoflife-fetcher"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.toml"
        config_file.write_text("timeout = 30")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            files = find_config_files()

        assert len(files) == 1
        assert files[0] == config_file

    def test_local_config_only(self, tmp_path, monkeypatch):
        """Test finds local endoflife-fetcher.toml."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("timeout = 20")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            files = find_config_files()

        assert len(files) == 1
        assert files[0].resolve() == config_file.resolve()

    def test_both_user_and_local(self, tmp_path, monkeypatch):
        """Test finds both user and local configs in correct order."""
        home = tmp_path / "home"
        user_config = home / ".config" / "endoflife-fetcher" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("timeout = 30")

        local_config = tmp_path / "endoflife-fetcher.toml"
        local_config.write_text("timeout = 20")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            files = find_config_files()

        assert len(files) == 2
        assert files[0] == user_config  # User first (lower priority)
        # Local second (higher priority)
        assert files[1].resolve() == local_config.resolve()


class TestLoadConfig:
    """Tests for configuration loading and merging."""

    def test_defaults_when_no_config(self, tmp_path, monkeypatch):
        """Test returns defaults when no config files exist."""
        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        assert config.timeout == 15.0
        assert config.warn_days == 0
        assert config.quiet is False
        assert config.one_file is False
        assert config.output_dir == "Output"
        assert config.combined_filename == "all-products-eol.json"
        assert config.products == []

    def test_loads_timeout(self, tmp_path, monkeypatch):
        """Test loading timeout from config."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("timeout = 45.5")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        assert config.timeout == 45.5

    def test_loads_all_options(self, tmp_path, monkeypatch):
        """Test loading all configuration options."""
        config_content = """
timeout = 30.0
max_retries = 5
warn_days = 90
quiet = true
one_file = true
lts = true
active = true
output_dir = "data"
combined_filename = "eol-report.json"
products = ["python", "nodejs"]

[groups]
backend = ["python", "nodejs"]
"""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text(config_content)

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        assert config.timeout == 30.0
        assert config.max_retries == 5
        assert config.warn_days == 90
        assert config.quiet is True
        assert config.one_file is True
        assert config.lts is True
        assert config.active is True
        assert config.output_dir == "data"
        assert config.combined_filename == "eol-report.json"
        assert config.products == ["python", "nodejs"]
        assert config.groups == {"backend": ["python", "nodejs"]}

    def test_local_overrides_user(self, tmp_path, monkeypatch):
        """Test local config overrides user config."""
        home = tmp_path / "home"
        user_config = home / ".config" / "endoflife-fetcher" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("timeout = 30\nwarn_days = 60")

        local_config = tmp_path / "endoflife-fetcher.toml"
        local_config.write_text("timeout = 10")  # Override timeout only

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            config = load_config()

        assert config.timeout == 10  # Local override
        assert config.warn_days == 60  # From user config

    def test_groups_merge_across_configs(self, tmp_path, monkeypatch):
        """Test groups from multiple configs are merged."""
        home = tmp_path / "home"
        user_config = home / ".config" / "endoflife-fetcher" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text('[groups]\nbackend = ["python", "nodejs"]')

        local_config = tmp_path / "endoflife-fetcher.toml"
        local_config.write_text('[groups]\nfrontend = ["react", "vue"]')

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            config = load_config()

        # Both groups should be present
        assert "backend" in config.groups
        assert "frontend" in config.groups
        assert config.groups["backend"] == ["python", "nodejs"]
        assert config.groups["frontend"] == ["react", "vue"]

    def test_groups_local_overrides_user(self, tmp_path, monkeypatch):
        """Test local group definition overrides user config."""
        home = tmp_path / "home"
        user_config = home / ".config" / "endoflife-fetcher" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text('[groups]\nbackend = ["python", "nodejs"]')

        local_config = tmp_path / "endoflife-fetcher.toml"
        local_config.write_text('[groups]\nbackend = ["go", "rust"]')  # Override

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            config = load_config()

        # Local should override user
        assert config.groups["backend"] == ["go", "rust"]

    def test_invalid_toml_warns(self, tmp_path, monkeypatch, capsys):
        """Test invalid TOML shows warning but doesn't crash."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("invalid [ toml")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        # Should return defaults
        assert config.timeout == 15.0
        # Should print warning
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "Invalid TOML" in captured.err

    def test_unreadable_config_warns(self, tmp_path, monkeypatch, capsys):
        """Test unreadable config file shows warning but doesn't crash."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("timeout = 30")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            # Mock open to raise OSError (permission denied)
            original_open = open

            def mock_open(path, *args, **kwargs):
                if str(path).endswith("endoflife-fetcher.toml"):
                    raise OSError("Permission denied")
                return original_open(path, *args, **kwargs)

            with patch("builtins.open", mock_open):
                config = load_config()

        # Should return defaults
        assert config.timeout == 15.0
        # Should print warning
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "Could not read" in captured.err

    def test_partial_config(self, tmp_path, monkeypatch):
        """Test config with only some options set."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("quiet = true")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        assert config.quiet is True
        assert config.timeout == 15.0  # Default preserved

    def test_unknown_keys_ignored(self, tmp_path, monkeypatch):
        """Test unknown config keys are silently ignored."""
        config_file = tmp_path / "endoflife-fetcher.toml"
        config_file.write_text("unknown_key = 'value'\ntimeout = 25")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=tmp_path / "home"):
            config = load_config()

        assert config.timeout == 25
        assert not hasattr(config, "unknown_key")


class TestLoadConfigExplicitPath:
    """Tests for load_config with explicit config_path."""

    def test_explicit_path_loads_file(self, tmp_path):
        """Test explicit config path loads that file."""
        config_file = tmp_path / "custom.toml"
        config_file.write_text("timeout = 99")

        config = load_config(config_path=config_file)

        assert config.timeout == 99

    def test_explicit_path_not_found(self, tmp_path):
        """Test explicit config path raises FileNotFoundError if missing."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(config_path=tmp_path / "nonexistent.toml")

        assert "Config file not found" in str(exc_info.value)

    def test_explicit_path_ignores_auto_discovery(self, tmp_path, monkeypatch):
        """Test explicit path skips auto-discovery."""
        # Create both auto-discovered and explicit configs
        home = tmp_path / "home"
        user_config = home / ".config" / "endoflife-fetcher" / "config.toml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("timeout = 30")

        local_config = tmp_path / "endoflife-fetcher.toml"
        local_config.write_text("timeout = 20")

        explicit_config = tmp_path / "explicit.toml"
        explicit_config.write_text("timeout = 50")

        monkeypatch.chdir(tmp_path)
        with patch.object(Path, "home", return_value=home):
            config = load_config(config_path=explicit_config)

        # Should use explicit config value, not auto-discovered
        assert config.timeout == 50

    def test_explicit_path_as_string(self, tmp_path):
        """Test explicit config path works with string path."""
        config_file = tmp_path / "custom.toml"
        config_file.write_text("warn_days = 45")

        config = load_config(config_path=str(config_file))

        assert config.warn_days == 45


class TestParseArgsWithConfig:
    """Tests for argparse integration with config."""

    def test_config_provides_defaults(self):
        """Test config values become argparse defaults."""
        config = Config(timeout=45, quiet=True, warn_days=30)

        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args(config)

        assert args.timeout == 45
        assert args.quiet is True
        assert args.warn_days == 30

    def test_cli_overrides_config(self):
        """Test CLI arguments override config values."""
        config = Config(timeout=45)

        test_args = ["endoflife_fetcher.py", "python", "-t", "10"]
        with patch.object(sys, "argv", test_args):
            args = parse_args(config)

        assert args.timeout == 10  # CLI wins

    def test_cli_overrides_config_warn_days(self):
        """Test CLI --warn-days overrides config value."""
        config = Config(warn_days=60)

        test_args = ["endoflife_fetcher.py", "python", "--warn-days", "7"]
        with patch.object(sys, "argv", test_args):
            args = parse_args(config)

        assert args.warn_days == 7

    def test_config_argument_present(self):
        """Test --config argument is available."""
        test_args = [
            "endoflife_fetcher.py",
            "--config",
            "/path/to/config.toml",
            "python",
        ]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

        assert args.config == "/path/to/config.toml"

    def test_no_config_uses_defaults(self):
        """Test parse_args without config uses built-in defaults."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()

        assert args.timeout == 15.0
        assert args.warn_days == 0
        assert args.quiet is False
