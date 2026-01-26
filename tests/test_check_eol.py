"""
Tests for the check_eol_status function.

Uses v1 API field names:
- "name" for cycle/version name
- "isEol" (bool) for EOL status
- "eolFrom" (date string) for EOL date
"""

from datetime import datetime, timedelta

from endoflife_fetcher import check_eol_status


class TestCheckEolBasic:
    """Basic tests for check_eol_status function."""

    def test_empty_results(self):
        """Test with empty results dict."""
        result = check_eol_status({})
        assert result == []

    def test_no_eol_products(self):
        """Test when no products are past EOL."""
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        results = {"python": [{"name": "3.12", "isEol": False, "eolFrom": future_date}]}
        result = check_eol_status(results)
        assert result == []

    def test_is_eol_false_no_date(self):
        """Test when isEol is False and no eolFrom date."""
        results = {"python": [{"name": "3.12", "isEol": False}]}
        result = check_eol_status(results)
        assert result == []

    def test_missing_eol_fields(self):
        """Test when both isEol and eolFrom are missing."""
        results = {"python": [{"name": "3.12"}]}
        result = check_eol_status(results)
        assert result == []


class TestCheckEolPastEol:
    """Tests for products that are past EOL."""

    def test_is_eol_true_with_date(self):
        """Test when isEol is True with an eolFrom date."""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        results = {"python": [{"name": "2.7", "isEol": True, "eolFrom": past_date}]}
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["product"] == "python"
        assert result[0]["cycle"] == "2.7"
        assert result[0]["days_until"] == -30

    def test_is_eol_true_no_date(self):
        """Test when isEol is True but no eolFrom date."""
        results = {"python": [{"name": "2.7", "isEol": True}]}
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["product"] == "python"
        assert result[0]["cycle"] == "2.7"
        assert result[0]["days_until"] is None
        assert "already EOL" in result[0]["eol"]

    def test_eol_date_in_past(self):
        """Test when EOL date is in the past and isEol is True."""
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        results = {"python": [{"name": "3.8", "isEol": True, "eolFrom": past_date}]}
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["product"] == "python"
        assert result[0]["cycle"] == "3.8"
        assert result[0]["days_until"] == -30

    def test_eol_date_today(self):
        """Test when EOL date is today."""
        today = datetime.now().strftime("%Y-%m-%d")
        results = {"python": [{"name": "3.9", "isEol": True, "eolFrom": today}]}
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["days_until"] == 0


class TestCheckEolWarnDays:
    """Tests for --warn-days threshold functionality."""

    def test_within_warn_days_threshold(self):
        """Test product within warn-days threshold (not yet EOL)."""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        results = {"nodejs": [{"name": "18", "isEol": False, "eolFrom": future_date}]}
        # With 60 day threshold, 30 days out should be caught
        result = check_eol_status(results, warn_days=60)
        assert len(result) == 1
        assert result[0]["product"] == "nodejs"
        assert result[0]["days_until"] == 30

    def test_outside_warn_days_threshold(self):
        """Test product outside warn-days threshold."""
        future_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        results = {"nodejs": [{"name": "20", "isEol": False, "eolFrom": future_date}]}
        # With 30 day threshold, 90 days out should not be caught
        result = check_eol_status(results, warn_days=30)
        assert result == []

    def test_exactly_at_threshold(self):
        """Test product exactly at warn-days threshold."""
        future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        results = {
            "ubuntu": [{"name": "22.04", "isEol": False, "eolFrom": future_date}]
        }
        # Exactly 30 days out with 30 day threshold should be caught
        result = check_eol_status(results, warn_days=30)
        assert len(result) == 1


class TestCheckEolMultipleProducts:
    """Tests for multiple products and releases."""

    def test_multiple_products_mixed(self):
        """Test with multiple products, some EOL some not."""
        past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
        results = {
            "python": [
                {"name": "2.7", "isEol": True, "eolFrom": past_date},
                {"name": "3.12", "isEol": False, "eolFrom": future_date},
            ],
            "nodejs": [
                {"name": "16", "isEol": True, "eolFrom": past_date},
                {"name": "20", "isEol": False, "eolFrom": future_date},
            ],
        }
        result = check_eol_status(results)
        assert len(result) == 2
        products = [r["product"] for r in result]
        assert "python" in products
        assert "nodejs" in products

    def test_multiple_releases_same_product(self):
        """Test multiple EOL releases from same product."""
        past_date1 = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        past_date2 = (datetime.now() - timedelta(days=50)).strftime("%Y-%m-%d")
        results = {
            "python": [
                {"name": "3.7", "isEol": True, "eolFrom": past_date1},
                {"name": "3.8", "isEol": True, "eolFrom": past_date2},
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
        """Test with invalid date format in eolFrom (should be skipped)."""
        results = {
            "python": [{"name": "3.12", "isEol": False, "eolFrom": "not-a-date"}]
        }
        result = check_eol_status(results)
        assert result == []

    def test_invalid_date_format_is_eol_true(self):
        """Test with invalid date format when isEol is True."""
        results = {"python": [{"name": "2.7", "isEol": True, "eolFrom": "not-a-date"}]}
        result = check_eol_status(results)
        # Should still be caught as EOL, just without a specific date
        assert len(result) == 1
        assert result[0]["days_until"] is None
        assert "already EOL" in result[0]["eol"]

    def test_missing_name_field(self):
        """Test with missing name field uses 'unknown'."""
        past_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        results = {"python": [{"isEol": True, "eolFrom": past_date}]}
        result = check_eol_status(results)
        assert len(result) == 1
        assert result[0]["cycle"] == "unknown"

    def test_non_list_releases(self):
        """Test with non-list releases value (defensive check)."""
        results = {
            "python": "not a list"  # type: ignore[dict-item]  # intentionally wrong type
        }
        result = check_eol_status(results)
        assert result == []

    def test_non_dict_release(self):
        """Test with non-dict release entry (defensive check)."""
        results = {
            "python": [
                "not a dict",  # type: ignore[list-item]  # intentionally wrong type
                {"name": "3.12", "isEol": False},
            ]
        }
        result = check_eol_status(results)
        assert result == []

    def test_unexpected_eol_from_type(self):
        """Test with unexpected eolFrom type (e.g., integer) - should be skipped."""
        past_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        results = {
            "python": [
                {"name": "3.12", "isEol": False, "eolFrom": 25012026},  # Invalid
                {"name": "3.8", "isEol": True, "eolFrom": past_date},  # Valid
            ]
        }
        result = check_eol_status(results)
        # Only the valid one should be caught
        assert len(result) == 1
        assert result[0]["cycle"] == "3.8"
