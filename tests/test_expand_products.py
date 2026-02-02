"""Tests for the expand_products function."""

import pytest

from endoflife_fetcher import expand_products


class TestExpandProductsSimple:
    """Tests for simple group expansion."""

    def test_no_groups_passthrough(self):
        """Test products without @ pass through unchanged."""
        products = ["python", "nodejs"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs"]
        assert unknown == []

    def test_simple_group_expansion(self):
        """Test @group expands to its members."""
        products = ["@backend"]
        groups = {"backend": ["python", "nodejs", "postgresql"]}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs", "postgresql"]
        assert unknown == []

    def test_mixed_groups_and_products(self):
        """Test mixing @groups and individual products."""
        products = ["@backend", "ubuntu"]
        groups = {"backend": ["python", "nodejs"]}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs", "ubuntu"]
        assert unknown == []


class TestExpandProductsDeduplication:
    """Tests for deduplication behavior."""

    def test_duplicate_product_deduplicated(self):
        """Test same product in group and CLI is deduplicated."""
        products = ["@backend", "python"]
        groups = {"backend": ["python", "nodejs"]}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs"]
        assert expanded.count("python") == 1

    def test_overlapping_groups_deduplicated(self):
        """Test products appearing in multiple groups are deduplicated."""
        products = ["@backend", "@frontend"]
        groups = {
            "backend": ["python", "nodejs"],
            "frontend": ["nodejs", "react"],  # nodejs in both
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs", "react"]
        assert expanded.count("nodejs") == 1

    def test_preserves_first_occurrence_order(self):
        """Test deduplication preserves order of first occurrence."""
        products = ["@group1", "@group2"]
        groups = {
            "group1": ["c", "a", "b"],
            "group2": ["b", "d", "a"],  # b and a already seen
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["c", "a", "b", "d"]


class TestExpandProductsNested:
    """Tests for nested group expansion."""

    def test_nested_groups(self):
        """Test groups can reference other groups."""
        products = ["@all"]
        groups = {
            "backend": ["python", "nodejs"],
            "frontend": ["react", "vue"],
            "all": ["@backend", "@frontend"],
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs", "react", "vue"]

    def test_deeply_nested_groups(self):
        """Test multiple levels of nesting."""
        products = ["@everything"]
        groups = {
            "lang": ["python"],
            "db": ["postgresql"],
            "backend": ["@lang", "@db"],
            "everything": ["@backend", "ubuntu"],
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "postgresql", "ubuntu"]

    def test_nested_with_mixed_content(self):
        """Test nested group with both products and group refs."""
        products = ["@mixed"]
        groups = {
            "tools": ["docker", "kubernetes"],
            "mixed": ["python", "@tools", "nodejs"],
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "docker", "kubernetes", "nodejs"]


class TestExpandProductsCircular:
    """Tests for circular reference detection."""

    def test_direct_circular_reference(self):
        """Test direct circular reference (A -> A) is detected."""
        products = ["@a"]
        groups = {"a": ["@a"]}

        with pytest.raises(ValueError) as exc_info:
            expand_products(products, groups)

        assert "Circular group reference detected" in str(exc_info.value)
        assert "a -> a" in str(exc_info.value)

    def test_indirect_circular_reference(self):
        """Test indirect circular reference (A -> B -> A) is detected."""
        products = ["@a"]
        groups = {
            "a": ["@b"],
            "b": ["@a"],
        }

        with pytest.raises(ValueError) as exc_info:
            expand_products(products, groups)

        assert "Circular group reference detected" in str(exc_info.value)
        assert "a -> b -> a" in str(exc_info.value)

    def test_longer_circular_chain(self):
        """Test longer circular chain is detected."""
        products = ["@a"]
        groups = {
            "a": ["@b"],
            "b": ["@c"],
            "c": ["@a"],
        }

        with pytest.raises(ValueError) as exc_info:
            expand_products(products, groups)

        assert "Circular group reference detected" in str(exc_info.value)
        assert "a -> b -> c -> a" in str(exc_info.value)


class TestExpandProductsUnknown:
    """Tests for unknown group handling."""

    def test_unknown_group_reported(self):
        """Test unknown group is reported in unknown list."""
        products = ["@unknown"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == ["unknown"]

    def test_multiple_unknown_groups(self):
        """Test multiple unknown groups are all reported."""
        products = ["@foo", "@bar", "@baz"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == ["foo", "bar", "baz"]

    def test_unknown_with_valid_products(self):
        """Test unknown groups with valid products."""
        products = ["@unknown", "python"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python"]
        assert unknown == ["unknown"]

    def test_unknown_with_valid_groups(self):
        """Test unknown groups mixed with valid groups."""
        products = ["@backend", "@unknown"]
        groups = {"backend": ["python", "nodejs"]}

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python", "nodejs"]
        assert unknown == ["unknown"]

    def test_unknown_in_nested_group(self):
        """Test unknown group referenced inside another group."""
        products = ["@all"]
        groups = {
            "all": ["@backend", "@unknown"],
            "backend": ["python"],
        }

        expanded, unknown = expand_products(products, groups)

        assert expanded == ["python"]
        assert unknown == ["unknown"]

    def test_unknown_not_duplicated(self):
        """Test same unknown group referenced twice is reported once."""
        products = ["@unknown", "@unknown"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert unknown == ["unknown"]
        assert unknown.count("unknown") == 1


class TestExpandProductsEdgeCases:
    """Tests for edge cases."""

    def test_empty_products(self):
        """Test empty products list."""
        products = []
        groups = {"backend": ["python"]}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == []

    def test_empty_groups(self):
        """Test empty groups dict with @ reference."""
        products = ["@backend"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == ["backend"]

    def test_empty_group_definition(self):
        """Test group defined as empty list."""
        products = ["@empty"]
        groups = {"empty": []}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == []

    def test_at_in_product_name(self):
        """Test product name that looks like group but isn't defined."""
        products = ["@notagroup"]
        groups = {}

        expanded, unknown = expand_products(products, groups)

        assert expanded == []
        assert unknown == ["notagroup"]
