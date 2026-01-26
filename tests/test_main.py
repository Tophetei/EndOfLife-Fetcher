"""
Integration tests for the main function.

Uses v1 API response structure.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest
import responses

from endoflife_fetcher import BASE_URL, FileSaveError, main


def make_v1_response(releases):
    """Helper to wrap releases in v1 API response structure."""
    return {"result": {"releases": releases}}


class TestMainSingleProduct:
    """Tests for main() with single product."""

    @responses.activate
    def test_default_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with single product and default output."""
        product = "python"
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
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
        releases = [{"name": "22.04", "isEol": False, "eolFrom": "2027-04-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
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
        releases = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
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
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
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
            assert json.load(f) == releases_python
        with open(nodejs_file) as f:
            assert json.load(f) == releases_nodejs

        captured = capsys.readouterr()
        assert "Saved data for 2 products" in captured.out

    @responses.activate
    def test_output_warning_without_one_file(self, tmp_path, capsys, monkeypatch):
        """Test warning when using -o with multiple products without --one-file."""
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
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
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
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
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]
        releases_ubuntu = [{"name": "22.04", "isEol": False, "eolFrom": "2027-04-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/ubuntu",
            json=make_v1_response(releases_ubuntu),
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
            assert data["python"] == releases_python
            assert data["nodejs"] == releases_nodejs
            assert data["ubuntu"] == releases_ubuntu

        captured = capsys.readouterr()
        assert "Saved data for 3 product(s)" in captured.out

    @responses.activate
    def test_one_file_custom_output(self, tmp_path, capsys, monkeypatch):
        """Test main function with --one-file and custom output path."""
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]
        custom_output = str(tmp_path / "my-products.json")

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
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
            assert data["python"] == releases_python
            assert data["nodejs"] == releases_nodejs

    @responses.activate
    def test_single_product_one_file(self, tmp_path, capsys, monkeypatch):
        """Test single product with --one-file flag produces dict output."""
        product = "python"
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
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
            assert data["python"] == releases


class TestMainPartialSuccess:
    """Tests for partial success scenarios (some products fail)."""

    @responses.activate
    def test_partial_success_per_file(self, tmp_path, capsys, monkeypatch):
        """Test main function with some products failing (per-file mode)."""
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(responses.GET, f"{BASE_URL}/products/invalid", status=404)
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

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
        releases_python = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
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
            json=make_v1_response(releases_nodejs),
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
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
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
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response([{"name": "20", "isEol": False, "eolFrom": "2026-04-30"}]),
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


class TestMainCheckMode:
    """Tests for --check mode (EOL checking)."""

    @responses.activate
    def test_check_no_eol_exits_0(self, tmp_path, monkeypatch):
        """Test --check exits 0 when no products are EOL."""
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2099-01-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "--check"]
        with patch.object(sys, "argv", test_args):
            # Should not raise SystemExit
            main()

    @responses.activate
    def test_check_eol_exits_1(self, tmp_path, capsys, monkeypatch):
        """Test --check exits 1 when products are past EOL."""
        releases = [{"name": "2.7", "isEol": True, "eolFrom": "2020-01-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "--check"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "EOL Check Failed" in captured.err
        assert "python" in captured.err
        assert "2.7" in captured.err

    @responses.activate
    def test_check_eol_is_eol_true(self, tmp_path, capsys, monkeypatch):
        """Test --check detects isEol: true."""
        releases = [{"name": "2.7", "isEol": True, "eolFrom": "2020-01-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "--check"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "EOL" in captured.err

    @responses.activate
    def test_check_eol_no_date(self, tmp_path, capsys, monkeypatch):
        """Test --check shows 'already EOL' when isEol is True but no eolFrom date."""
        # isEol: True without eolFrom results in days_until: None
        releases = [{"name": "2.7", "isEol": True}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "--check"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "already EOL" in captured.err
        assert "python 2.7" in captured.err

    @responses.activate
    def test_check_with_warn_days(self, tmp_path, capsys, monkeypatch):
        """Test --check with --warn-days threshold."""
        from datetime import datetime, timedelta

        # EOL date 30 days from now
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        releases = [{"name": "18", "isEol": False, "eolFrom": future_date}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        # With 60 day threshold, should catch it
        test_args = ["endoflife_fetcher.py", "nodejs", "--check", "--warn-days", "60"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "EOL in 30 days" in captured.err

    @responses.activate
    def test_check_eol_today(self, tmp_path, capsys, monkeypatch):
        """Test --check shows 'EOL today' when EOL date is today."""
        from datetime import datetime

        # EOL date is today
        today = datetime.now().strftime("%Y-%m-%d")
        releases = [{"name": "16", "isEol": True, "eolFrom": today}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "nodejs", "--check"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "EOL today" in captured.err

    @responses.activate
    def test_check_warn_days_not_triggered(self, tmp_path, monkeypatch):
        """Test --check with --warn-days when product is outside threshold."""
        from datetime import datetime, timedelta

        # EOL date 90 days from now
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        releases = [{"name": "20", "isEol": False, "eolFrom": future_date}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        # With 30 day threshold, should NOT catch it
        test_args = ["endoflife_fetcher.py", "nodejs", "--check", "--warn-days", "30"]
        with patch.object(sys, "argv", test_args):
            # Should not raise SystemExit
            main()

    @responses.activate
    def test_check_multiple_products_mixed(self, tmp_path, capsys, monkeypatch):
        """Test --check with multiple products, some EOL some not."""
        releases_python = [
            {"name": "2.7", "isEol": True, "eolFrom": "2020-01-01"},  # EOL
            {"name": "3.12", "isEol": False, "eolFrom": "2099-01-01"},  # Not EOL
        ]
        releases_nodejs = [{"name": "20", "isEol": False, "eolFrom": "2099-01-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases_python),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/nodejs",
            json=make_v1_response(releases_nodejs),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        test_args = ["endoflife_fetcher.py", "python", "nodejs", "--check"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "python 2.7" in captured.err
        # nodejs 20 should NOT be in the error output
        assert "nodejs 20" not in captured.err

    @responses.activate
    def test_check_without_flag_ignores_eol(self, tmp_path, monkeypatch):
        """Test that EOL products don't cause exit 1 without --check flag."""
        releases = [{"name": "2.7", "isEol": True, "eolFrom": "2020-01-01"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/python",
            json=make_v1_response(releases),
            status=200,
        )

        monkeypatch.chdir(tmp_path)

        # Without --check, should succeed even with EOL product
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            main()  # Should not raise
