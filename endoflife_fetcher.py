#!/usr/bin/env python3
"""
Fetch end-of-life data for products from endoflife.date API and save as JSON.
"""

import argparse
import json
import os
import sys

import requests


class EOLDAPIError(Exception):
    """Base exception for endoflife.date API errors."""

    pass


class ProductNotFoundError(EOLDAPIError):
    """Exception raised when a product is not found (HTTP 404)."""

    pass


class FileSaveError(Exception):
    """Exception raised when file saving fails."""

    pass


BASE_URL = "https://endoflife.date/api/v1"


def fetch_product(product, timeout=15):
    """
    Fetch end-of-life data for a specific product.

    Args:
        product: Product slug (e.g., 'python', 'ubuntu', 'nodejs')
        timeout: HTTP request timeout in seconds

    Returns:
        dict: JSON response from the API

    Raises:
        ProductNotFoundError: If the product is not found (404)
        EOLDAPIError: For network errors, server errors, or invalid responses
    """
    url = f"{BASE_URL}/products/{product}"

    try:
        resp = requests.get(
            url, timeout=timeout, headers={"Accept": "application/json"}
        )
    except requests.exceptions.RequestException as e:
        raise EOLDAPIError(f"Network or API error while requesting {url}: {e}") from e

    if resp.status_code == 404:
        raise ProductNotFoundError(
            f"Product '{product}' not found on endoflife.date. "
            f"Check {BASE_URL}/products for valid product names."
        )

    if str(resp.status_code).startswith("5"):
        raise EOLDAPIError(f"Server error {resp.status_code} from endoflife.date.")

    if not resp.ok:
        raise EOLDAPIError(f"HTTP {resp.status_code} error from endoflife.date.")

    try:
        data = resp.json()
    except ValueError as e:
        raise EOLDAPIError(f"Invalid JSON received from API: {e}") from e

    return data


def save_json(data, path):
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


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch end-of-life data for a product from "
            "endoflife.date API and save as JSON."
        )
    )
    parser.add_argument("product", help="Product slug (e.g., python, ubuntu, nodejs)")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path for JSON. If omitted, saves to Output/{product}.json",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: 15)",
    )
    return parser.parse_args()


def main():
    """Main entry point for the script."""
    args = parse_args()
    product = args.product
    output = args.output

    # Fetch product data from API
    try:
        data = fetch_product(product, timeout=args.timeout)
    except ProductNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(10)
    except EOLDAPIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(11)

    # Determine output path (CLI argument or default Output folder)
    if not output:
        output = os.path.join("Output", f"{product}-eol.json")
        print(f"No output path specified, using default: {output}")

    # Save data to file
    try:
        save_json(data, output)
    except FileSaveError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(12)

    print(f"Saved data for '{product}' to: {output}")


if __name__ == "__main__":
    main()
