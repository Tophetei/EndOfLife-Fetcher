"""
Tests for the parse_args function.
"""

import sys
from unittest.mock import patch

from endoflife_fetcher import parse_args


class TestParseArgsProducts:
    """Tests for product argument parsing."""

    def test_single_product(self):
        """Test parsing with only one product argument."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python"]
            assert args.output is None
            assert args.timeout == 15.0
            assert args.one_file is False

    def test_multiple_products(self):
        """Test parsing with multiple products."""
        test_args = ["endoflife_fetcher.py", "python", "nodejs", "ubuntu"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs", "ubuntu"]
            assert args.output is None
            assert args.one_file is False


class TestParseArgsOutput:
    """Tests for output argument parsing."""

    def test_output_short_form(self):
        """Test parsing with -o argument."""
        test_args = ["endoflife_fetcher.py", "ubuntu", "-o", "custom.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["ubuntu"]
            assert args.output == "custom.json"

    def test_output_long_form(self):
        """Test parsing with --output argument."""
        test_args = ["endoflife_fetcher.py", "nodejs", "--output", "node.json"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["nodejs"]
            assert args.output == "node.json"


class TestParseArgsTimeout:
    """Tests for timeout argument parsing."""

    def test_timeout_short_form(self):
        """Test parsing with -t argument."""
        test_args = ["endoflife_fetcher.py", "python", "-t", "30"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python"]
            assert args.timeout == 30.0

    def test_timeout_long_form(self):
        """Test parsing with --timeout argument."""
        test_args = ["endoflife_fetcher.py", "python", "--timeout", "45.5"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.timeout == 45.5


class TestParseArgsOneFile:
    """Tests for --one-file flag parsing."""

    def test_one_file_flag(self):
        """Test parsing with --one-file flag."""
        test_args = ["endoflife_fetcher.py", "python", "nodejs", "--one-file"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs"]
            assert args.one_file is True


class TestParseArgsCombined:
    """Tests for combined argument parsing."""

    def test_all_arguments(self):
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


class TestParseArgsListProducts:
    """Tests for --list-products argument parsing."""

    def test_list_products_flag(self):
        """Test parsing with --list-products flag."""
        test_args = ["endoflife_fetcher.py", "--list-products"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.list_products is True
            assert args.products == []

    def test_list_products_default_false(self):
        """Test that --list-products defaults to False."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.list_products is False

    def test_no_args_parses_ok(self):
        """Test that no arguments still parses (validation is in main)."""
        test_args = ["endoflife_fetcher.py"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == []
            assert args.list_products is False


class TestParseArgsQuiet:
    """Tests for --quiet / -q argument parsing."""

    def test_quiet_short_flag(self):
        """Test parsing with -q flag."""
        test_args = ["endoflife_fetcher.py", "python", "-q"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.quiet is True

    def test_quiet_long_flag(self):
        """Test parsing with --quiet flag."""
        test_args = ["endoflife_fetcher.py", "python", "--quiet"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.quiet is True

    def test_quiet_default_false(self):
        """Test that --quiet defaults to False."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.quiet is False


class TestParseArgsCheck:
    """Tests for --check and --warn-days argument parsing."""

    def test_check_flag(self):
        """Test parsing with --check flag."""
        test_args = ["endoflife_fetcher.py", "python", "--check"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.check is True
            assert args.warn_days == 0  # Default

    def test_check_flag_default_false(self):
        """Test that --check defaults to False."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.check is False

    def test_warn_days(self):
        """Test parsing with --warn-days argument."""
        test_args = ["endoflife_fetcher.py", "python", "--check", "--warn-days", "90"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.check is True
            assert args.warn_days == 90

    def test_warn_days_default(self):
        """Test that --warn-days defaults to 0."""
        test_args = ["endoflife_fetcher.py", "python"]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.warn_days == 0

    def test_all_arguments_with_check(self):
        """Test parsing with all arguments including --check."""
        test_args = [
            "endoflife_fetcher.py",
            "python",
            "nodejs",
            "-o",
            "output.json",
            "--one-file",
            "--check",
            "--warn-days",
            "30",
        ]
        with patch.object(sys, "argv", test_args):
            args = parse_args()
            assert args.products == ["python", "nodejs"]
            assert args.output == "output.json"
            assert args.one_file is True
            assert args.check is True
            assert args.warn_days == 30
