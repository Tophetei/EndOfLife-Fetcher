"""
Unit tests for endoflife_fetcher module.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import responses

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from endoflife_fetcher import (
    BASE_URL,
    EOLDAPIError,
    FileSaveError,
    ProductNotFoundError,
    RateLimitError,
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
    def test_fetch_product_rate_limit_with_retry_after(self):
        """Test rate limit error (429) with Retry-After header."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            headers={"Retry-After": "60"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after == 60

    @responses.activate
    def test_fetch_product_rate_limit_without_retry_after(self):
        """Test rate limit error (429) without Retry-After header."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after is None

    @responses.activate
    def test_fetch_product_rate_limit_with_http_date(self):
        """Test rate limit error (429) with HTTP date in Retry-After."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            headers={"Retry-After": "Wed, 21 Oct 2025 07:28:00 GMT"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after == "Wed, 21 Oct 2025 07:28:00 GMT"

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

    def test_save_json_formatting(self, tmp_path):
        """Test JSON formatting (indentation, encoding)."""
        test_data = {"name": "Python", "version": "3.12", "special": "café"}
        output_file = tmp_path / "test.json"

        save_json(test_data, str(output_file))

        with open(output_file, encoding="utf-8") as f:
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

    def test_parse_args_single_product_only(self):
        """Test parsing with only one product argument."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python"]
            assert args.output is None
            assert args.timeout == 15.0
            assert args.one_file is False

    def test_parse_args_multiple_products(self):
        """Test parsing with multiple products."""
        test_args = ["endoflife_fetcher.py", "python", "nodejs", "ubuntu"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs", "ubuntu"]
            assert args.output is None
            assert args.one_file is False

    def test_parse_args_with_output(self):
        """Test parsing with output argument."""
        test_args = ["endoflife_fetcher.py", "ubuntu", "-o", "custom.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["ubuntu"]
            assert args.output == "custom.json"

    def test_parse_args_with_output_long(self):
        """Test parsing with --output long form."""
        test_args = ["endoflife_fetcher.py", "nodejs", "--output", "node.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["nodejs"]
            assert args.output == "node.json"

    def test_parse_args_with_timeout(self):
        """Test parsing with timeout argument."""
        test_args = ["endoflife_fetcher.py", "python", "-t", "30"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python"]
            assert args.timeout == 30.0

    def test_parse_args_with_timeout_long(self):
        """Test parsing with --timeout long form."""
        test_args = ["endoflife_fetcher.py", "python", "--timeout", "45.5"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.timeout == 45.5

    def test_parse_args_with_one_file(self):
        """Test parsing with --one-file flag."""
        test_args = ["endoflife_fetcher.py", "python", "nodejs", "--one-file"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs"]
            assert args.one_file is True

    def test_parse_args_all_arguments(self):
        """Test parsing with all arguments."""
        test_args = [
            "endoflife_fetcher.py",
            "python",
            "nodejs",
            "-o",
            "output.json",
            "-t",
            "20",
            "--one-file",
        ]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs"]
            assert args.output == "output.json"
            assert args.timeout == 20.0
            assert args.one_file is True


class TestMain:
    """Integration tests for the main function."""

    @responses.activate
    def test_main_single_product_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with single product and default output."""
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
        assert "Fetching data" in captured.out
        assert product in captured.out

    @responses.activate
    def test_main_multiple_products_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with multiple products and default output."""
        products = ["python", "nodejs"]
        mock_data_python = [{"cycle": "3.12", "eol": "2028-10-02"}]
        mock_data_nodejs = [{"cycle": "20", "eol": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data_python,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=mock_data_nodejs,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "nodejs"]
        with patch.object(sys, "argv", test_args):
            main()

        # Check both output files were created
        python_file = tmp_path / "Output" / "python-eol.json"
        nodejs_file = tmp_path / "Output" / "nodejs-eol.json"

        assert python_file.exists()
        assert nodejs_file.exists()

        # Check content
        with open(python_file) as f:
            assert json.load(f) == mock_data_python
        with open(nodejs_file) as f:
            assert json.load(f) == mock_data_nodejs

        # Check stdout
        captured = capsys.readouterr()
        assert "Saved data for 2 products" in captured.out
        assert "python" in captured.out
        assert "nodejs" in captured.out

    @responses.activate
    def test_main_multiple_products_one_file(self, tmp_path, capsys, monkeypatch):
        """Test main function with --one-file option."""
        products = ["python", "nodejs", "ubuntu"]
        mock_data_python = [{"cycle": "3.12"}]
        mock_data_nodejs = [{"cycle": "20"}]
        mock_data_ubuntu = [{"cycle": "22.04"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data_python,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=mock_data_nodejs,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/ubuntu",
            json=mock_data_ubuntu,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "nodejs", "ubuntu", "--one-file"]
        with patch.object(sys, "argv", test_args):
            main()

        # Check one combined file was created
        output_file = tmp_path / "Output" / "all-products-eol.json"
        assert output_file.exists()

        # Check content structure
        with open(output_file) as f:
            data = json.load(f)
            assert "python" in data
            assert "nodejs" in data
            assert "ubuntu" in data
            assert data["python"] == mock_data_python
            assert data["nodejs"] == mock_data_nodejs
            assert data["ubuntu"] == mock_data_ubuntu

        # Check stdout
        captured = capsys.readouterr()
        assert "Saved data for 3 product(s)" in captured.out

    @responses.activate
    def test_main_one_file_custom_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with --one-file and custom output path."""
        products = ["python", "nodejs"]
        mock_data_python = [{"cycle": "3.12"}]
        mock_data_nodejs = [{"cycle": "20"}]
        custom_output = str(tmp_path / "my-products.json")

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data_python,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=mock_data_nodejs,
            status=200,
        )

        test_args = [
            "endoflife_fetcher.py",
            "python",
            "nodejs",
            "--one-file",
            "-o",
            custom_output,
        ]
        with patch.object(sys, "argv", test_args):
            main()

        # Check custom output file was created
        assert os.path.exists(custom_output)

        # Check content
        with open(custom_output) as f:
            data = json.load(f)
            assert data["python"] == mock_data_python
            assert data["nodejs"] == mock_data_nodejs

    @responses.activate
    def test_main_single_product_custom_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with single product and custom output path."""
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
    def test_main_partial_success(self, capsys):
        """Test main function with some products failing."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=[{"cycle": "3.12"}],
            status=200,
        )
        responses.add(responses.GET, f"{BASE_URL}/products/invalid", status=404)
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=[{"cycle": "20"}],
            status=200,
        )

        test_args = ["endoflife_fetcher.py", "python", "invalid", "nodejs"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        # Should exit with 5 (partial success)
        assert exc_info.value.code == 5

        captured = capsys.readouterr()
        assert "Successfully fetched data for 'python'" in captured.out
        assert "Successfully fetched data for 'nodejs'" in captured.out
        assert "1 product(s) failed" in captured.err
        assert "invalid" in captured.err

    @responses.activate
    def test_main_all_products_fail(self, capsys):
        """Test main function when all products fail."""
        responses.add(responses.GET, f"{BASE_URL}/products/invalid1", status=404)
        responses.add(responses.GET, f"{BASE_URL}/products/invalid2", status=404)

        test_args = ["endoflife_fetcher.py", "invalid1", "invalid2"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 10
        captured = capsys.readouterr()
        assert "Failed to fetch data for all products" in captured.err

    @responses.activate
    def test_main_product_not_found(self, capsys):
        """Test main function with single product not found."""
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
        assert "Error" in captured.err or "not found" in captured.err.lower()

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
        assert "Error" in captured.err or "error" in captured.err.lower()

    @responses.activate
    def test_main_rate_limit_error(self, capsys):
        """Test main function with rate limit error."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            headers={"Retry-After": "120"},
        )

        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 13
        captured = capsys.readouterr()
        assert "Rate limit" in captured.err
        assert "120" in captured.err

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
            with patch(
                "endoflife_fetcher.save_json", side_effect=FileSaveError("Mock error")
            ):
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

    @responses.activate
    def test_main_multiple_products_with_output_warning(
        self, tmp_path, capsys, monkeypatch
    ):
        """Test that a warning is shown when using -o with multiple products without --one-file."""
        products = ["python", "nodejs"]
        mock_data_python = [{"cycle": "3.12"}]
        mock_data_nodejs = [{"cycle": "20"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data_python,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=mock_data_nodejs,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "nodejs", "-o", "ignored.json"]
        with patch.object(sys, "argv", test_args):
            main()

        # Check that warning was displayed
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "--one-file not used" in captured.err

        # Check that default naming was used
        assert (tmp_path / "Output" / "python-eol.json").exists()
        assert (tmp_path / "Output" / "nodejs-eol.json").exists()


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

    def test_rate_limit_error_is_eoldapi_error(self):
        """Test that RateLimitError inherits from EOLDAPIError."""
        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, EOLDAPIError)
        assert isinstance(error, Exception)
        assert error.retry_after is None

    def test_rate_limit_error_with_retry_after(self):
        """Test that RateLimitError stores retry_after value."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        assert isinstance(error, EOLDAPIError)
        assert error.retry_after == 60
        assert "Rate limit exceeded" in str(error)

    def test_file_save_error_is_exception(self):
        """Test that FileSaveError is an Exception."""
        error = FileSaveError("Save failed")
        assert isinstance(error, Exception)
        assert str(error) == "Save failed"
