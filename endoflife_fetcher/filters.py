"""Filtering functions for releases and product groups."""

from __future__ import annotations

from typing import Any


def filter_releases(
    releases: list[dict[str, Any]], lts: bool = False, active: bool = False
) -> list[dict[str, Any]]:
    """
    Filter releases based on LTS and active status.

    Args:
        releases: List of release dicts from the API
        lts: If True, only include LTS releases
        active: If True, exclude releases that are already EOL

    Returns:
        Filtered list of releases
    """
    if not lts and not active:
        return releases

    filtered = []
    for release in releases:
        if not isinstance(release, dict):
            continue

        # Filter by LTS if requested
        if lts and not release.get("isLts", False):
            continue

        # Filter by active (not EOL) if requested
        if active and release.get("isEol", False):
            continue

        filtered.append(release)

    return filtered


def expand_products(
    products: list[str], groups: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    """
    Expand product groups (@group syntax) into individual products.

    Supports:
    - Simple groups: @backend -> ["python", "nodejs"]
    - Nested groups: @all -> ["@backend", "@frontend"] -> all products
    - Mixed input: ["@backend", "python"] -> expanded + deduplicated
    - Circular reference detection

    Args:
        products: List of products and/or group references (@name)
        groups: Dict mapping group names to product lists

    Returns:
        Tuple of (expanded_products, unknown_groups)
        - expanded_products: Deduplicated list preserving order
        - unknown_groups: List of group names that weren't found
    """
    expanded: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()

    def resolve(item: str, chain: list[str]) -> None:
        """Recursively resolve a product or group reference."""
        if item.startswith("@"):
            group_name = item[1:]

            # Check for circular reference
            if group_name in chain:
                cycle = " -> ".join(chain + [group_name])
                raise ValueError(f"Circular group reference detected: {cycle}")

            if group_name not in groups:
                if group_name not in unknown:
                    unknown.append(group_name)
                return

            # Recursively expand group members
            for member in groups[group_name]:
                resolve(member, chain + [group_name])
        else:
            # Regular product - add if not already seen
            if item not in seen:
                seen.add(item)
                expanded.append(item)

    for product in products:
        resolve(product, [])

    return expanded, unknown
