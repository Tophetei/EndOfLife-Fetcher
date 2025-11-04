"""
Unit tests for endoflife_fetcher module.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import responses

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

import endoflife_fetcher
from endoflife_fetcher import (
    BASE_URL,
    EOLDAPIError,
    FileSaveError,
    ProductNotFoundError,
    fetch_product,
    main,
    parse_args,
    save_json,
)


class TestFetchProduct:
    """Tests for the fetch_product function."""

    @responses.activate
    def test_fetch_product_success(self):
        """Test successful product fetch."""
        product = "python"
        mock_data = [
            {
                "cycle": "3.12",
                "releaseDate": "2023-10-02",
                "eol": "2028-10-02",
                "latest": "3.12.0",
                "lts": False,
            }
        ]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        result = fetch_product(product)
        assert result == mock_data
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Accept"] == "application/json"

    @responses.activate
    def test_fetch_product_not_found(self):
        """Test product not found (404 error)."""
        product = "invalid-product"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=404,
        )

        with pytest.raises(ProductNotFoundError) as exc_info:
            fetch_product(product)

        assert "invalid-product" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    @responses.activate
    def test_fetch_product_server_error(self):
        """Test server error (5xx status codes)."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=500,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "500" in str(exc_info.value)
        assert "Server error" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_other_http_error(self):
        """Test other HTTP errors (4xx except 404)."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=403,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "403" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_invalid_json(self):
        """Test invalid JSON response."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            body="Invalid JSON content",
            status=200,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "Invalid JSON" in str(exc_info.value)

    def test_fetch_product_timeout(self):
        """Test request timeout."""
        import requests
        product = "python"

        with patch("endoflife_fetcher.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product, timeout=1)

            assert "Network or API error" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_custom_timeout(self):
        """Test custom timeout parameter."""
        product = "python"
        mock_data = {"test": "data"}

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        result = fetch_product(product, timeout=30)
        assert result == mock_data


class TestSaveJson:
    """Tests for the save_json function."""

    def test_save_json_success(self, tmp_path):
        """Test successful JSON file save."""
        test_data = {"cycle": "3.12", "eol": "2028-10-02"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_creates_directory(self, tmp_path):
        """Test that save_json creates parent directories."""
        test_data = {"test": "data"}
        output_file = tmp_path / "subdir" / "nested" / "test.json"

        save_json(test_data, str(output_file))

        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_save_json_formatting(self, tmp_path):
        """Test JSON formatting (indentation, encoding)."""
        test_data = {"name": "Python", "version": "3.12", "special": "café"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check indentation
        assert "  " in content
        # Check UTF-8 encoding (café should be preserved)
        assert "café" in content

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


class TestParseArgs:
    """Tests for the parse_args function."""

    def test_parse_args_product_only(self):
        """Test parsing with only product argument."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.product == "python"
            assert args.output is None
            assert args.timeout == 15.0

    def test_parse_args_with_output(self):
        """Test parsing with output argument."""
        test_args = ["endoflife_fetcher.py", "ubuntu", "-o", "custom.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.product == "ubuntu"
            assert args.output == "custom.json"

    def test_parse_args_with_output_long(self):
        """Test parsing with --output long form."""
        test_args = ["endoflife_fetcher.py", "nodejs", "--output", "node.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.product == "nodejs"
            assert args.output == "node.json"

    def test_parse_args_with_timeout(self):
        """Test parsing with timeout argument."""
        test_args = ["endoflife_fetcher.py", "python", "-t", "30"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.product == "python"
            assert args.timeout == 30.0

    def test_parse_args_with_timeout_long(self):
        """Test parsing with --timeout long form."""
        test_args = ["endoflife_fetcher.py", "python", "--timeout", "45.5"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.timeout == 45.5

    def test_parse_args_all_arguments(self):
        """Test parsing with all arguments."""
        test_args = [
            "endoflife_fetcher.py",
            "python",
            "-o",
            "output.json",
            "-t",
            "20",
        ]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.product == "python"
            assert args.output == "output.json"
            assert args.timeout == 20.0


class TestMain:
    """Integration tests for the main function."""

    @responses.activate
    def test_main_success_with_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with successful execution and default output."""
        product = "python"
        mock_data = [{"cycle": "3.12", "eol": "2028-10-02"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        # Change to tmp directory
        monkeypatch.chdir(tmp_path)

        # Mock command line arguments
        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            main()

        # Check output file was created
        output_file = tmp_path / "Output" / f"{product}-eol.json"
        assert output_file.exists()

        # Check stdout
        captured = capsys.readouterr()
        assert "No output path specified" in captured.out
        assert product in captured.out

    @responses.activate
    def test_main_success_with_custom_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with custom output path."""
        product = "ubuntu"
        output_path = str(tmp_path / "custom.json")
        mock_data = [{"cycle": "22.04", "eol": "2027-04-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        test_args = ["endoflife_fetcher.py", product, "-o", output_path]
        with patch.object(sys, "argv", test_args):
            main()

        # Check output file was created
        assert os.path.exists(output_path)

        # Check stdout
        captured = capsys.readouterr()
        assert "Saved data" in captured.out
        assert product in captured.out

    @responses.activate
    def test_main_product_not_found(self, capsys):
        """Test main function with product not found."""
        product = "invalid-product"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=404,
        )

        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 10
        captured = capsys.readouterr()
        assert "Error" in captured.err
        assert "not found" in captured.err.lower()

    @responses.activate
    def test_main_api_error(self, capsys):
        """Test main function with API error."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=500,
        )

        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 11
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @responses.activate
    def test_main_file_save_error(self, capsys):
        """Test main function with file save error."""
        product = "python"
        mock_data = [{"cycle": "3.12"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        # Mock save_json to raise FileSaveError
        test_args = ["endoflife_fetcher.py", product]

        with patch.object(sys, "argv", test_args):
            with patch("endoflife_fetcher.save_json", side_effect=FileSaveError("Mock error")):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 12
        captured = capsys.readouterr()
        assert "Error" in captured.err

    @responses.activate
    def test_main_with_custom_timeout(self, tmp_path, monkeypatch):
        """Test main function with custom timeout."""
        product = "nodejs"
        mock_data = [{"cycle": "20", "eol": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", product, "-t", "30"]
        with patch.object(sys, "argv", test_args):
            main()

        # Just verify it runs successfully
        output_file = tmp_path / "Output" / f"{product}-eol.json"
        assert output_file.exists()


class TestExceptions:
    """Tests for custom exception classes."""

    def test_eoldapi_error_is_exception(self):
        """Test that EOLDAPIError is an Exception."""
        error = EOLDAPIError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_product_not_found_error_is_eoldapi_error(self):
        """Test that ProductNotFoundError inherits from EOLDAPIError."""
        error = ProductNotFoundError("Product not found")
        assert isinstance(error, EOLDAPIError)
        assert isinstance(error, Exception)

    def test_file_save_error_is_exception(self):
        """Test that FileSaveError is an Exception."""
        error = FileSaveError("Save failed")
        assert isinstance(error, Exception)
        assert str(error) == "Save failed"
