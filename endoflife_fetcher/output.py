"""Output and file handling functions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from .exceptions import FileSaveError


def save_json(data: Any, path: str) -> None:
    """
    Save data as JSON to the specified file path.

    Creates parent directories if they don't exist.

    Args:
        data: Data to serialize as JSON
        path: File path to save to

    Raises:
        FileSaveError: If file writing fails
    """
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise FileSaveError(f"Failed to write file '{path}': {e}") from e


def check_eol_status(
    results: dict[str, list[dict[str, Any]]], warn_days: int = 0
) -> list[dict[str, Any]]:
    """
    Check which products have releases that are EOL or within the warning threshold.

    Args:
        results: Dict of {product: [releases]} from the v1 API
        warn_days: Number of days threshold for warning (0 = only already EOL)

    Returns:
        List of dicts with EOL information:
        [{"product": str, "cycle": str, "eol": str, "days_until": int or None}]
    """
    eol_products = []
    today = datetime.now().date()
    threshold_date = today + timedelta(days=warn_days)

    for product, releases in results.items():
        if not isinstance(releases, list):
            continue

        for release in releases:
            if not isinstance(release, dict):
                continue

            cycle_name = release.get("name", "unknown")
            is_eol = release.get("isEol", False)
            eol_from = release.get("eolFrom")

            # Try to parse the EOL date
            eol_date = None
            days_until = None
            if eol_from:
                try:
                    eol_date = datetime.strptime(eol_from, "%Y-%m-%d").date()
                    days_until = (eol_date - today).days
                except (ValueError, TypeError):
                    pass

            # Determine if this release should be reported
            should_report = False
            eol_str = eol_from

            if is_eol:
                should_report = True
                if not eol_date:
                    eol_str = "true (already EOL)"
                    days_until = None
            elif eol_date and eol_date <= threshold_date:
                should_report = True

            if should_report:
                eol_products.append(
                    {
                        "product": product,
                        "cycle": cycle_name,
                        "eol": eol_str,
                        "days_until": days_until,
                    }
                )

    return eol_products
