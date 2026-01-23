"""
Integration tests for the main function.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest
import responses

from endoflife_fetcher import BASE_URL, FileSaveError, main


class TestMainSingleProduct:
    """Tests for main() with single product."""

    @responses.activate
    def test_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with single product and default output."""
        product = "python"
        mock_data = [{"cycle": "3.12", "eol": "2028-10-02"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            main()

        output_file = tmp_path / "Output" / f"{product}-eol.json"
        assert output_file.exists()

        captured = capsys.readouterr()
        assert "Fetching data" in captured.out
        assert product in captured.out

    @responses.activate
    def test_custom_output(self, tmp_path, capsys, monkeypatch):
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

        assert os.path.exists(output_path)

        captured = capsys.readouterr()
        assert "Saved data" in captured.out
        assert product in captured.out

    @responses.activate
    def test_with_custom_timeout(self, tmp_path, monkeypatch):
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

        output_file = tmp_path / "Output" / f"{product}-eol.json"
        assert output_file.exists()


class TestMainMultipleProducts:
    """Tests for main() with multiple products."""

    @responses.activate
    def test_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with multiple products and default output."""
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

        python_file = tmp_path / "Output" / "python-eol.json"
        nodejs_file = tmp_path / "Output" / "nodejs-eol.json"

        assert python_file.exists()
        assert nodejs_file.exists()

        with open(python_file) as f:
            assert json.load(f) == mock_data_python
        with open(nodejs_file) as f:
            assert json.load(f) == mock_data_nodejs

        captured = capsys.readouterr()
        assert "Saved data for 2 products" in captured.out

    @responses.activate
    def test_output_warning_without_one_file(self, tmp_path, capsys, monkeypatch):
        """Test warning when using -o with multiple products without --one-file."""
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

        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "--one-file not used" in captured.err

        # Default naming should be used
        assert (tmp_path / "Output" / "python-eol.json").exists()
        assert (tmp_path / "Output" / "nodejs-eol.json").exists()

    @responses.activate
    def test_duplicate_products(self, tmp_path, capsys, monkeypatch):
        """Test behavior when the same product is specified multiple times."""
        mock_data = [{"cycle": "3.12", "eol": "2028-10-02"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "python"]
        with patch.object(sys, "argv", test_args):
            main()

        # Should have made 2 API calls
        assert len(responses.calls) == 2

        # But only one file saved (dict key collision)
        output_file = tmp_path / "Output" / "python-eol.json"
        assert output_file.exists()

        captured = capsys.readouterr()
        assert "Saved data for 'python'" in captured.out


class TestMainOneFileMode:
    """Tests for main() with --one-file flag."""

    @responses.activate
    def test_multiple_products_one_file(self, tmp_path, capsys, monkeypatch):
        """Test main function with --one-file option."""
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

        output_file = tmp_path / "Output" / "all-products-eol.json"
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)
            assert "python" in data
            assert "nodejs" in data
            assert "ubuntu" in data
            assert data["python"] == mock_data_python
            assert data["nodejs"] == mock_data_nodejs
            assert data["ubuntu"] == mock_data_ubuntu

        captured = capsys.readouterr()
        assert "Saved data for 3 product(s)" in captured.out

    @responses.activate
    def test_one_file_custom_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with --one-file and custom output path."""
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

        assert os.path.exists(custom_output)

        with open(custom_output) as f:
            data = json.load(f)
            assert data["python"] == mock_data_python
            assert data["nodejs"] == mock_data_nodejs

    @responses.activate
    def test_single_product_one_file(self, tmp_path, capsys, monkeypatch):
        """Test single product with --one-file flag produces dict output."""
        product = "python"
        mock_data = [{"cycle": "3.12", "eol": "2028-10-02"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", product, "--one-file"]
        with patch.object(sys, "argv", test_args):
            main()

        output_file = tmp_path / "Output" / "all-products-eol.json"
        assert output_file.exists()

        # Verify structure is {"python": [...]} not just [...]
        with open(output_file) as f:
            data = json.load(f)
            assert isinstance(data, dict)
            assert "python" in data
            assert data["python"] == mock_data


class TestMainPartialSuccess:
    """Tests for partial success scenarios (some products fail)."""

    @responses.activate
    def test_partial_success_per_file(self, capsys):
        """Test main function with some products failing (per-file mode)."""
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

        assert exc_info.value.code == 5

        captured = capsys.readouterr()
        assert "Successfully fetched data for 'python'" in captured.out
        assert "Successfully fetched data for 'nodejs'" in captured.out
        assert "1 product(s) failed" in captured.err
        assert "invalid" in captured.err

    @responses.activate
    def test_partial_success_one_file(self, tmp_path, capsys, monkeypatch):
        """Test partial success with --one-file mode."""
        mock_data_python = [{"cycle": "3.12"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data_python,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/invalid",
            status=404,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=[{"cycle": "20"}],
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "invalid", "nodejs", "--one-file"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 5

        # Check combined file contains only successful products
        output_file = tmp_path / "Output" / "all-products-eol.json"
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)
            assert "python" in data
            assert "nodejs" in data
            assert "invalid" not in data

        captured = capsys.readouterr()
        assert "1 product(s) failed" in captured.err


class TestMainAllProductsFail:
    """Tests for scenarios where all products fail."""

    @responses.activate
    def test_all_fail_not_found(self, capsys):
        """Test exit code 10 when all products return 404."""
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
    def test_all_fail_rate_limit(self, capsys):
        """Test exit code 13 when all products fail with rate limit errors."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            status=429,
            headers={"Retry-After": "60"},
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            status=429,
            headers={"Retry-After": "60"},
        )

        test_args = ["endoflife_fetcher.py", "python", "nodejs"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 13
        captured = capsys.readouterr()
        assert "Failed to fetch data for all products" in captured.err

    @responses.activate
    def test_all_fail_api_error(self, capsys):
        """Test exit code 11 when all products fail with API errors."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            status=500,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            status=503,
        )

        test_args = ["endoflife_fetcher.py", "python", "nodejs"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 11
        captured = capsys.readouterr()
        assert "Failed to fetch data for all products" in captured.err

    @responses.activate
    def test_all_fail_mixed_errors_priority(self, capsys):
        """Test exit code priority: not_found (10) > rate_limit (13) > api_error (11)."""
        # One 404, one 429 - should exit with 10 (not_found has priority)
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/invalid",
            status=404,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            status=429,
        )

        test_args = ["endoflife_fetcher.py", "invalid", "python"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 10


class TestMainSingleProductErrors:
    """Tests for single product error scenarios."""

    @responses.activate
    def test_product_not_found(self, capsys):
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
    def test_api_error(self, capsys):
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
    def test_rate_limit_with_retry_hint(self, capsys):
        """Test main function with rate limit error showing retry hint."""
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
        assert "Hint:" in captured.err

    @responses.activate
    def test_rate_limit_without_retry_hint(self, capsys):
        """Test that no hint is shown when rate limit has no Retry-After."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            # No Retry-After header
        )

        test_args = ["endoflife_fetcher.py", product]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 13
        captured = capsys.readouterr()
        assert "Rate limit exceeded" in captured.err
        # The "Hint: Wait X seconds" message should NOT appear
        assert "Hint:" not in captured.err


class TestMainFileSaveErrors:
    """Tests for file save error scenarios."""

    @responses.activate
    def test_file_save_error_per_file(self, capsys):
        """Test main function with file save error in per-file mode."""
        product = "python"
        mock_data = [{"cycle": "3.12"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

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
    def test_file_save_error_one_file_mode(self, capsys):
        """Test file save error specifically in --one-file mode."""
        mock_data = [{"cycle": "3.12"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=mock_data,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=[{"cycle": "20"}],
            status=200,
        )

        test_args = ["endoflife_fetcher.py", "python", "nodejs", "--one-file"]

        with patch.object(sys, "argv", test_args):
            with patch(
                "endoflife_fetcher.save_json",
                side_effect=FileSaveError("Disk full"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 12
        captured = capsys.readouterr()
        assert "Disk full" in captured.err
