"""
Integration tests for the CLI entry point.

These tests verify that the installed `endoflife-fetcher` command works correctly.
They run the actual command as a subprocess, testing the full integration.
"""

import shutil
import subprocess
import sys

import pytest


class TestModuleImport:
    """Tests for module import."""

    def test_main_module_import(self):
        """Test that __main__ module can be imported."""
        import endoflife_fetcher.__main__ as main_module

        assert hasattr(main_module, "main")


class TestCLIEntrypoint:
    """Tests for the installed CLI entry point."""

    def test_version_flag(self):
        """Test --version flag returns version info."""
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_version_short_flag(self):
        """Test -V flag returns version info."""
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher", "-V"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_help_flag(self):
        """Test --help flag shows usage information."""
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "endoflife" in result.stdout.lower()

    def test_no_args_shows_error(self):
        """Test running without arguments shows error."""
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "no products specified" in result.stderr.lower()
        assert "--list-products" in result.stderr


class TestInstalledEntrypoint:
    """Tests for the installed `endoflife-fetcher` command.

    These tests only run if the package is installed (pip install -e .).
    """

    @pytest.fixture(autouse=True)
    def skip_if_not_installed(self):
        """Skip tests if endoflife-fetcher command is not installed."""
        if shutil.which("endoflife-fetcher") is None:
            pytest.skip("endoflife-fetcher not installed (run: pip install -e .)")

    def test_installed_entrypoint_version(self):
        """Test installed entry point --version flag."""
        result = subprocess.run(
            ["endoflife-fetcher", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_installed_entrypoint_help(self):
        """Test installed entry point --help flag."""
        result = subprocess.run(
            ["endoflife-fetcher", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()


class TestConfigFlag:
    """Tests for the --config flag integration."""

    def test_config_flag_file_not_found(self, tmp_path):
        """Test --config with non-existent file shows error."""
        nonexistent = tmp_path / "nonexistent.toml"
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher", "--config", str(nonexistent)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Config file not found" in result.stderr

    def test_config_flag_equals_syntax_file_not_found(self, tmp_path):
        """Test --config= syntax with non-existent file shows error."""
        nonexistent = tmp_path / "nonexistent.toml"
        result = subprocess.run(
            [sys.executable, "-m", "endoflife_fetcher", f"--config={nonexistent}"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Config file not found" in result.stderr

    def test_config_flag_loads_file(self, tmp_path):
        """Test --config loads and applies config file."""
        config_file = tmp_path / "test-config.toml"
        config_file.write_text("timeout = 99")

        # Use --help to verify config loads without needing API call
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "endoflife_fetcher",
                "--config",
                str(config_file),
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # The help text should show the config's timeout as default
        assert "99" in result.stdout

    def test_config_flag_equals_syntax_loads_file(self, tmp_path):
        """Test --config= syntax loads and applies config file."""
        config_file = tmp_path / "test-config.toml"
        config_file.write_text("timeout = 77")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "endoflife_fetcher",
                f"--config={config_file}",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "77" in result.stdout
