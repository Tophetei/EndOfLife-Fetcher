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


class RateLimitError(EOLDAPIError):
    """Exception raised when rate limit is exceeded (HTTP 429)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


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

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                retry_seconds = int(retry_after)
                raise RateLimitError(
                    f"Rate limit exceeded. Please retry after {retry_seconds} seconds.",
                    retry_after=retry_seconds,
                )
            except ValueError:
                # Retry-After might be a HTTP date instead of seconds
                raise RateLimitError(
                    f"Rate limit exceeded. Retry-After: {retry_after}",
                    retry_after=retry_after,
                ) from None
        else:
            raise RateLimitError(
                "Rate limit exceeded. Please wait before making more requests."
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
            "Fetch end-of-life data for one or more products from "
            "endoflife.date API and save as JSON."
        )
    )
    parser.add_argument(
        "products",
        nargs="+",
        metavar="product",
        help="Product slug(s) (e.g., python, ubuntu, nodejs)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output file path for JSON. If omitted, saves to Output/{product}-eol.json "
            "for each product, or Output/all-products-eol.json with --one-file"
        ),
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--one-file",
        action="store_true",
        help=(
            "Save all products data in a single JSON file "
            "(default: one file per product)"
        ),
    )
    return parser.parse_args()


def main():
    """Main entry point for the script."""
    args = parse_args()
    products = args.products
    output = args.output
    one_file = args.one_file

    # Storage for results
    results = {}
    errors = {}

    # Fetch data for each product
    for product in products:
        try:
            print(f"Fetching data for '{product}'...")
            data = fetch_product(product, timeout=args.timeout)
            results[product] = data
            print(f"  ✓ Successfully fetched data for '{product}'")
        except ProductNotFoundError as e:
            error_msg = str(e)
            errors[product] = {"type": "not_found", "message": error_msg}
            print(f"  ✗ Error: {error_msg}", file=sys.stderr)
        except RateLimitError as e:
            error_msg = str(e)
            errors[product] = {
                "type": "rate_limit",
                "message": error_msg,
                "retry_after": e.retry_after,
            }
            print(f"  ✗ Error: {error_msg}", file=sys.stderr)
            if e.retry_after:
                print(
                    f"    Hint: Wait {e.retry_after} seconds before retrying",
                    file=sys.stderr,
                )
        except EOLDAPIError as e:
            error_msg = str(e)
            errors[product] = {"type": "api_error", "message": error_msg}
            print(f"  ✗ Error: {error_msg}", file=sys.stderr)

    # Check if we got any successful results
    if not results:
        print("\nError: Failed to fetch data for all products.", file=sys.stderr)
        # Determine appropriate exit code based on errors
        if any(e["type"] == "not_found" for e in errors.values()):
            sys.exit(10)
        elif any(e["type"] == "rate_limit" for e in errors.values()):
            sys.exit(13)
        else:
            sys.exit(11)

    # Save the results
    try:
        if one_file:
            # Save all products in one file
            if not output:
                output = os.path.join("Output", "all-products-eol.json")
                print(f"\nNo output path specified, using default: {output}")

            save_json(results, output)
            print(f"\nSaved data for {len(results)} product(s) to: {output}")
        else:
            # Save each product in its own file
            if output and len(products) > 1:
                print(
                    "\nWarning: --output specified with multiple products "
                    "but --one-file not used. "
                    "Using default naming pattern.",
                    file=sys.stderr,
                )
                output = None

            saved_files = []
            for product, data in results.items():
                if output and len(products) == 1:
                    # Use specified output path for single product
                    file_path = output
                else:
                    # Use default naming pattern
                    file_path = os.path.join("Output", f"{product}-eol.json")

                save_json(data, file_path)
                saved_files.append((product, file_path))

            if len(saved_files) == 1:
                print(f"\nSaved data for '{saved_files[0][0]}' to: {saved_files[0][1]}")
            else:
                print(f"\nSaved data for {len(saved_files)} products:")
                for product, file_path in saved_files:
                    print(f"  - {product}: {file_path}")

    except FileSaveError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(12)

    # Report on any errors
    if errors:
        print(f"\n{len(errors)} product(s) failed:", file=sys.stderr)
        for product, error in errors.items():
            print(f"  - {product}: {error['message']}", file=sys.stderr)
        # Exit with partial success code (we got some data but not all)
        sys.exit(5)


if __name__ == "__main__":
    main()
