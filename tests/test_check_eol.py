"""
Tests for the check_eol_status function.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from endoflife_fetcher import check_eol_status


class TestCheckEolBasic:
    """Basic tests for check_eol_status function."""

    def test_empty_results(self):
        """Test with empty results dict."""
        result = check_eol_status({})
        assert result == []

    def test_no_eol_products(self):
        """Test when no products are past EOL."""
        # EOL date far in the future
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        results = {
            "python": [{"cycle": "3.12", "eol": future_date}]
        }
        result = check_eol_status(results)
        assert result == []

    def test_eol_boolean_false(self):
        """Test when eol is False (no EOL date set)."""
        results = {
            "python": [{"cycle": "3.12", "eol": False}]
        }
        result = check_eol_status(results)
        assert result == []

    def test_eol_none(self):
        """Test when eol is None."""
        results = {
            "python": [{"cycle": "3.12", "eol": None}]
        }
        result = check_eol_status(results)
        assert result == []


class TestCheckEolPastEol:
    """Tests for products that are past EOL."""

    def test_eol_boolean_true(self):
        """Test when eol is True (already EOL, no specific date)."""
        results = {
            "python": [{"cycle": "2.7", "eol": True}]
        }
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["product"] == "python"
        assert result[0]["cycle"] == "2.7"
        assert result[0]["days_until"] is None

    def test_eol_date_in_past(self):
        """Test when EOL date is in the past."""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        results = {
            "python": [{"cycle": "3.8", "eol": past_date}]
        }
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["product"] == "python"
        assert result[0]["cycle"] == "3.8"
        assert result[0]["days_until"] == -30

    def test_eol_date_today(self):
        """Test when EOL date is today."""
        today = datetime.now().strftime("%Y-%m-%d")
        results = {
            "python": [{"cycle": "3.9", "eol": today}]
        }
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["days_until"] == 0


class TestCheckEolWarnDays:
    """Tests for --warn-days threshold functionality."""

    def test_within_warn_days_threshold(self):
        """Test product within warn-days threshold."""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        results = {
            "nodejs": [{"cycle": "18", "eol": future_date}]
        }
        # With 60 day threshold, 30 days out should be caught
        result = check_eol_status(results, warn_days=60)
        assert len(result) == 1
        assert result[0]["product"] == "nodejs"
        assert result[0]["days_until"] == 30

    def test_outside_warn_days_threshold(self):
        """Test product outside warn-days threshold."""
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        results = {
            "nodejs": [{"cycle": "20", "eol": future_date}]
        }
        # With 30 day threshold, 90 days out should not be caught
        result = check_eol_status(results, warn_days=30)
        assert result == []

    def test_exactly_at_threshold(self):
        """Test product exactly at warn-days threshold."""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        results = {
            "ubuntu": [{"cycle": "22.04", "eol": future_date}]
        }
        # Exactly 30 days out with 30 day threshold should be caught
        result = check_eol_status(results, warn_days=30)
        assert len(result) == 1


class TestCheckEolMultipleProducts:
    """Tests for multiple products and cycles."""

    def test_multiple_products_mixed(self):
        """Test with multiple products, some EOL some not."""
        past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        results = {
            "python": [
                {"cycle": "2.7", "eol": True},
                {"cycle": "3.12", "eol": future_date},
            ],
            "nodejs": [
                {"cycle": "16", "eol": past_date},
                {"cycle": "20", "eol": future_date},
            ],
        }
        result = check_eol_status(results)
        assert len(result) == 2
        products = [r["product"] for r in result]
        assert "python" in products
        assert "nodejs" in products

    def test_multiple_cycles_same_product(self):
        """Test multiple EOL cycles from same product."""
        past_date1 = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        past_date2 = (datetime.now() - timedelta(days=50)).strftime("%Y-%m-%d")
        results = {
            "python": [
                {"cycle": "3.7", "eol": past_date1},
                {"cycle": "3.8", "eol": past_date2},
            ],
        }
        result = check_eol_status(results)
        assert len(result) == 2
        cycles = [r["cycle"] for r in result]
        assert "3.7" in cycles
        assert "3.8" in cycles


class TestCheckEolEdgeCases:
    """Edge case tests for check_eol_status."""

    def test_invalid_date_format(self):
        """Test with invalid date format (should be skipped)."""
        results = {
            "python": [{"cycle": "3.12", "eol": "not-a-date"}]
        }
        result = check_eol_status(results)
        assert result == []

    def test_missing_cycle_field(self):
        """Test with missing cycle field."""
        past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        results = {
            "python": [{"eol": past_date}]
        }
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["cycle"] == "unknown"

    def test_non_list_cycles(self):
        """Test with non-list cycles value (defensive check)."""
        results = {
            "python": "not a list"
        }
        result = check_eol_status(results)
        assert result == []

    def test_non_dict_cycle(self):
        """Test with non-dict cycle entry (defensive check)."""
        results = {
            "python": ["not a dict", {"cycle": "3.12", "eol": False}]
        }
        result = check_eol_status(results)
        assert result == []
    
    def test_invalid_eol_date_type(self):
        """Test with invalid eol date type (e.g., integer)."""
        valid_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        results = {
            "python": [{"cycle": "3.12", "eol": 25012026},
                       {"cycle": "3.13", "eol": valid_date},
            ]
        }
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["cycle"] == "3.13"
