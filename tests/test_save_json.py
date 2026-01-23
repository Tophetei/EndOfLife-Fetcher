"""
Tests for the save_json function.
"""

import json
from unittest.mock import patch

import pytest

from endoflife_fetcher import FileSaveError, save_json


class TestSaveJsonSuccess:
    """Tests for successful save_json operations."""

    def test_save_json_success(self, tmp_path):
        """Test successful JSON file save."""
        test_data = {"cycle": "3.12", "eol": "2028-10-02"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        assert output_file.exists()
        with open(output_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_creates_directory(self, tmp_path):
        """Test that save_json creates parent directories."""
        test_data = {"test": "data"}
        output_file = tmp_path / "subdir" / "nested" / "test.json"

        save_json(test_data, str(output_file))

        assert output_file.exists()
        with open(output_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_file_without_directory(self, tmp_path, monkeypatch):
        """Test saving to a filename without directory path."""
        monkeypatch.chdir(tmp_path)

        test_data = {"test": "data"}
        output_file = "just_filename.json"

        save_json(test_data, output_file)

        assert (tmp_path / output_file).exists()
        with open(tmp_path / output_file, encoding="utf-8") as f:
            assert json.load(f) == test_data

    def test_save_json_overwrites_existing_file(self, tmp_path):
        """Test that save_json overwrites existing files."""
        output_file = tmp_path / "existing.json"

        # Create initial file
        initial_data = {"version": 1}
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f)

        # Overwrite with new data
        new_data = {"version": 2, "extra": "field"}
        save_json(new_data, str(output_file))

        with open(output_file, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data == new_data
        assert saved_data != initial_data


class TestSaveJsonFormatting:
    """Tests for JSON formatting options."""

    def test_save_json_indentation(self, tmp_path):
        """Test that JSON output is indented."""
        test_data = {"name": "Python", "version": "3.12"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        with open(output_file, encoding="utf-8") as f:
            content = f.read()

        # Check 2-space indentation
        assert "  " in content

    def test_save_json_utf8_encoding(self, tmp_path):
        """Test that UTF-8 characters are preserved (not escaped)."""
        test_data = {"name": "café", "emoji": "🐍", "chinese": "中文"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        with open(output_file, encoding="utf-8") as f:
            content = f.read()

        # Characters should be preserved, not escaped as \\uXXXX
        assert "café" in content
        assert "🐍" in content
        assert "中文" in content


class TestSaveJsonErrors:
    """Tests for save_json error handling."""

    def test_save_json_permission_error(self):
        """Test handling of permission errors."""
        test_data = {"test": "data"}
        output_file = "/some/path/test.json"

        with patch("builtins.open", side_effect=OSError("Permission denied")):
            with pytest.raises(FileSaveError) as exc_info:
                save_json(test_data, output_file)

            assert "Failed to write file" in str(exc_info.value)

    def test_save_json_invalid_path(self):
        """Test handling of invalid file paths."""
        test_data = {"test": "data"}
        invalid_path = "/invalid/path/test.json"

        with patch("os.makedirs", side_effect=OSError("Cannot create directory")):
            with pytest.raises(FileSaveError):
                save_json(test_data, invalid_path)
