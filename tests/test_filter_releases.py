"""Tests for the filter_releases function."""

from endoflife_fetcher import filter_releases


class TestFilterReleasesLts:
    """Tests for --lts filtering."""

    def test_lts_filters_non_lts(self):
        """Test that --lts filters out non-LTS releases."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            {"name": "23", "isLts": False, "isEol": False},
            {"name": "22", "isLts": True, "isEol": False},
        ]

        result = filter_releases(releases, lts=True)

        assert len(result) == 2
        assert result[0]["name"] == "24"
        assert result[1]["name"] == "22"

    def test_lts_empty_when_no_lts(self):
        """Test that --lts returns empty list when no LTS releases."""
        releases = [
            {"name": "3.12", "isLts": False, "isEol": False},
            {"name": "3.11", "isLts": False, "isEol": False},
        ]

        result = filter_releases(releases, lts=True)

        assert result == []

    def test_lts_missing_field_treated_as_false(self):
        """Test that missing isLts field is treated as False."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            {"name": "23", "isEol": False},  # No isLts field
        ]

        result = filter_releases(releases, lts=True)

        assert len(result) == 1
        assert result[0]["name"] == "24"


class TestFilterReleasesActive:
    """Tests for --active filtering."""

    def test_active_filters_eol(self):
        """Test that --active filters out EOL releases."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            {"name": "23", "isLts": False, "isEol": True},
            {"name": "22", "isLts": True, "isEol": False},
        ]

        result = filter_releases(releases, active=True)

        assert len(result) == 2
        assert result[0]["name"] == "24"
        assert result[1]["name"] == "22"

    def test_active_missing_field_treated_as_false(self):
        """Test that missing isEol field is treated as False (active)."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            {"name": "23"},  # No isEol field - should be included
        ]

        result = filter_releases(releases, active=True)

        assert len(result) == 2


class TestFilterReleasesCombined:
    """Tests for combined --lts and --active filtering."""

    def test_lts_and_active_combined(self):
        """Test that --lts --active filters correctly."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},  # LTS, active ✓
            {"name": "23", "isLts": False, "isEol": True},  # Not LTS, EOL
            {"name": "22", "isLts": True, "isEol": False},  # LTS, active ✓
            {"name": "20", "isLts": True, "isEol": True},  # LTS, but EOL
            {"name": "18", "isLts": True, "isEol": False},  # LTS, active ✓
        ]

        result = filter_releases(releases, lts=True, active=True)

        assert len(result) == 3
        names = [r["name"] for r in result]
        assert names == ["24", "22", "18"]


class TestFilterReleasesNoFilter:
    """Tests for no filtering."""

    def test_no_filter_returns_all(self):
        """Test that no filters returns all releases."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            {"name": "23", "isLts": False, "isEol": True},
        ]

        result = filter_releases(releases, lts=False, active=False)

        assert result == releases

    def test_empty_releases(self):
        """Test that empty list returns empty list."""
        result = filter_releases([], lts=True, active=True)

        assert result == []

    def test_non_dict_items_skipped(self):
        """Test that non-dict items are skipped during filtering."""
        releases = [
            {"name": "24", "isLts": True, "isEol": False},
            "invalid",
            None,
            {"name": "22", "isLts": True, "isEol": False},
        ]

        result = filter_releases(releases, lts=True)

        assert len(result) == 2
