#!/usr/bin/env python3
"""
Fetch end-of-life data for products from endoflife.date API and save as JSON.
"""

from __future__ import annotations

__version__ = "1.0.0"

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pragma: no cover


class EOLDAPIError(Exception):
    """Base exception for endoflife.date API errors."""

    pass


class ProductNotFoundError(EOLDAPIError):
    """Exception raised when a product is not found (HTTP 404)."""

    pass


class RateLimitError(EOLDAPIError):
    """Exception raised when rate limit is exceeded (HTTP 429)."""

    def __init__(self, message: str, retry_after: int | str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class FileSaveError(Exception):
    """Exception raised when file saving fails."""

    pass


BASE_URL = "https://endoflife.date/api/v1"


@dataclass
class Config:
    """Configuration container with defaults."""

    timeout: float = 15.0
    max_retries: int = 3
    warn_days: int = 0
    quiet: bool = False
    one_file: bool = False
    lts: bool = False
    active: bool = False
    output_dir: str = "Output"
    combined_filename: str = "all-products-eol.json"
    products: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)


def find_config_files() -> list[Path]:
    """
    Find config files in priority order (lowest to highest).

    Returns:
        List of existing config file paths:
        - ~/.config/endoflife-fetcher/config.toml (user config)
        - ./endoflife-fetcher.toml (local config)
    """
    config_files = []

    # 1. User config (XDG standard)
    user_config = Path.home() / ".config" / "endoflife-fetcher" / "config.toml"
    if user_config.exists():
        config_files.append(user_config)

    # 2. Local config
    local_config = Path("endoflife-fetcher.toml")
    if local_config.exists():
        config_files.append(local_config)

    return config_files


def load_config(config_path: Path | str | None = None) -> Config:
    """
    Load and merge configuration from files.

    Args:
        config_path: Explicit config file path (if provided, only this file is loaded)

    Priority (lowest to highest):
    1. Built-in defaults
    2. User config (~/.config/endoflife-fetcher/config.toml)
    3. Local config (./endoflife-fetcher.toml)
    4. Explicit --config path (replaces auto-discovery)

    Returns:
        Config object with merged settings

    Raises:
        FileNotFoundError: If explicit config_path doesn't exist
    """
    config = Config()  # Start with defaults

    # Determine which files to load
    if config_path is not None:
        # Explicit path: only load this file, error if not found
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        config_files = [path]
    else:
        # Auto-discovery
        config_files = find_config_files()

    # Mapping of config keys to their type converters
    field_types: dict[str, type] = {
        "timeout": float,
        "max_retries": int,
        "warn_days": int,
        "quiet": bool,
        "one_file": bool,
        "lts": bool,
        "active": bool,
        "output_dir": str,
        "combined_filename": str,
    }

    for file_path in config_files:
        try:
            with open(file_path, "rb") as f:
                file_config = tomllib.load(f)

            # Apply typed fields
            for key, converter in field_types.items():
                if key in file_config:
                    setattr(config, key, converter(file_config[key]))

            # Handle special cases
            if "products" in file_config:
                config.products = list(file_config["products"])
            if "groups" in file_config:
                config.groups.update(file_config["groups"])

        except tomllib.TOMLDecodeError as e:
            # Warn but don't fail - config errors shouldn't break the tool
            print(f"Warning: Invalid TOML in {file_path}: {e}", file=sys.stderr)
        except OSError as e:
            # File exists but can't be read - warn
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return config


def create_retry_session(
    max_retries: int = 3, backoff_factor: float = 1
) -> requests.Session:
    """
    Create a requests session with retry strategy for transient failures.

    Args:
        max_retries: Maximum number of retry attempts (0 to disable)
        backoff_factor: Multiplier for exponential backoff delay

    Returns:
        Configured requests.Session with retry adapter mounted
    """
    session = requests.Session()

    if max_retries > 0:
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,  # Let us handle status codes manually
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    return session


def _api_get(
    endpoint: str, timeout: float = 15, max_retries: int = 3
) -> dict[str, Any]:
    """
    Make a GET request to the endoflife.date API.

    Handles common error cases: network errors, rate limits, server errors,
    and JSON parsing.

    Args:
        endpoint: API endpoint (e.g., '/products' or '/products/python')
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)

    Returns:
        Parsed JSON response as dict

    Raises:
        RateLimitError: If rate limit is exceeded (HTTP 429)
        EOLDAPIError: For network errors, server errors, or invalid responses

    Note:
        Does NOT handle 404 - callers should check for that if needed.
    """
    url = f"{BASE_URL}{endpoint}"
    session = create_retry_session(max_retries=max_retries)

    try:
        resp = session.get(url, timeout=timeout, headers={"Accept": "application/json"})
    except requests.exceptions.RequestException as e:
        raise EOLDAPIError(f"Network or API error while requesting {url}: {e}") from e

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
        # Return response for caller to handle specific status codes (e.g., 404)
        return {"_status_code": resp.status_code, "_ok": False}

    try:
        return resp.json()
    except ValueError as e:
        raise EOLDAPIError(f"Invalid JSON received from API: {e}") from e


def fetch_product(
    product: str, timeout: float = 15, max_retries: int = 3
) -> list[dict[str, Any]]:
    """
    Fetch end-of-life data for a specific product.

    Args:
        product: Product slug (e.g., 'python', 'ubuntu', 'nodejs')
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)

    Returns:
        List of release dicts from the API

    Raises:
        ProductNotFoundError: If the product is not found (404)
        EOLDAPIError: For network errors, server errors, or invalid responses
    """
    data = _api_get(f"/products/{product}", timeout=timeout, max_retries=max_retries)

    # Handle 404 specifically for products
    if data.get("_ok") is False:
        if data.get("_status_code") == 404:
            raise ProductNotFoundError(
                f"Product '{product}' not found on endoflife.date."
            )
        raise EOLDAPIError(
            f"HTTP {data.get('_status_code')} error from endoflife.date."
        )

    # Extract releases from v1 API response structure
    try:
        return data["result"]["releases"]
    except (KeyError, TypeError) as e:
        raise EOLDAPIError(
            f"Unexpected API response structure for '{product}': {e}"
        ) from e


def fetch_products_list(timeout: float = 15, max_retries: int = 3) -> list[str]:
    """
    Fetch list of all available product names from the API.

    Args:
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)

    Returns:
        List of product slugs (e.g., ['python', 'nodejs', 'ubuntu', ...])

    Raises:
        EOLDAPIError: For network errors, server errors, or invalid responses
    """
    data = _api_get("/products", timeout=timeout, max_retries=max_retries)

    # Handle unexpected error responses
    if data.get("_ok") is False:
        raise EOLDAPIError(
            f"HTTP {data.get('_status_code')} error from endoflife.date."
        )

    try:
        return [product["name"] for product in data["result"]]
    except (KeyError, TypeError) as e:
        raise EOLDAPIError(f"Unexpected API response structure: {e}") from e


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


def parse_args(config: Config | None = None) -> argparse.Namespace:
    """
    Parse command line arguments.

    Args:
        config: Optional Config object to use for default values.
                If None, built-in defaults are used.
    """
    if config is None:
        config = Config()

    parser = argparse.ArgumentParser(
        description=(
            "Fetch end-of-life data for one or more products from "
            "endoflife.date API and save as JSON."
        )
    )

    # Positional arguments
    parser.add_argument(
        "products",
        nargs="*",
        metavar="product",
        help="Product slug(s) (e.g., python, ubuntu, nodejs)",
    )

    # Output options
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
        default=config.timeout,
        help=f"HTTP timeout in seconds (default: {config.timeout})",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=config.max_retries,
        metavar="N",
        help=(
            "Max retry attempts for transient failures "
            f"(default: {config.max_retries}). Set to 0 to disable."
        ),
    )
    parser.add_argument(
        "--one-file",
        action="store_true",
        default=config.one_file,
        help=(
            "Save all products data in a single JSON file "
            "(default: one file per product)"
        ),
    )

    # Filtering options
    parser.add_argument(
        "--lts",
        action="store_true",
        default=config.lts,
        help="Only include LTS (Long Term Support) releases",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        default=config.active,
        help="Only include active releases (exclude already EOL)",
    )

    # Check mode options
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Check if any product cycle is past EOL or within --warn-days threshold. "
            "Exits with code 1 if EOL products are found."
        ),
    )
    parser.add_argument(
        "--warn-days",
        type=int,
        default=config.warn_days,
        metavar="DAYS",
        help=(
            "Days threshold for EOL warning with --check. "
            f"0 means only already-EOL products (default: {config.warn_days})"
        ),
    )

    # Scripting options
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=config.quiet,
        help="Suppress progress output (errors still shown)",
    )
    parser.add_argument(
        "--list-products",
        action="store_true",
        help="List all available products from endoflife.date and exit",
    )

    # Utility options
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to TOML configuration file",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the script."""
    # First, check for --config argument to load config before full parsing
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv):
            config_path = sys.argv[i + 1]
            break
        elif arg.startswith("--config="):
            config_path = arg.split("=", 1)[1]
            break

    # Load configuration
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Parse arguments with config-based defaults
    args = parse_args(config)
    products = args.products or config.products
    output = args.output
    one_file = args.one_file

    def info(msg: str) -> None:
        """Print message unless quiet mode is enabled."""
        if not args.quiet:
            print(msg)

    # Handle --list-products
    if args.list_products:
        try:
            info("Fetching products list...")
            products_list = fetch_products_list(
                timeout=args.timeout, max_retries=args.max_retries
            )
            for product in products_list:
                print(product)
        except EOLDAPIError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(11)
        return

    # Validate that products were specified
    if not products:
        print(
            "[ERROR] No products specified. "
            "Use --list-products to see available products.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Expand product groups (@group syntax)
    try:
        products, unknown_groups = expand_products(products, config.groups)
    except ValueError as e:
        # Circular reference detected
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Handle unknown groups
    if unknown_groups:
        if not products:
            # All arguments were unknown groups - fatal error
            groups_str = ", ".join(f"@{g}" for g in unknown_groups)
            print(f"[ERROR] Unknown group(s): {groups_str}", file=sys.stderr)
            sys.exit(1)
        else:
            # Some groups unknown but we have products - warn and continue
            for group in unknown_groups:
                print(f"Warning: Unknown group '@{group}', skipping", file=sys.stderr)

    # Storage for results
    results = {}
    errors = {}
    filtered_empty = []  # Products fetched OK but filtered to empty

    # Fetch data for each product
    for product in products:
        try:
            info(f"Fetching data for '{product}'...")
            data = fetch_product(
                product, timeout=args.timeout, max_retries=args.max_retries
            )

            # Apply filters if requested
            data = filter_releases(data, lts=args.lts, active=args.active)

            if not data:
                info(f"  [OK] No releases match filters for '{product}'")
                filtered_empty.append(product)
            else:
                results[product] = data
                info(f"  [OK] Successfully fetched data for '{product}'")
        except ProductNotFoundError as e:
            error_msg = str(e)
            errors[product] = {"type": "not_found", "message": error_msg}
            print(f"  [ERROR] {error_msg}", file=sys.stderr)
        except RateLimitError as e:
            error_msg = str(e)
            errors[product] = {
                "type": "rate_limit",
                "message": error_msg,
                "retry_after": e.retry_after,
            }
            print(f"  [ERROR] {error_msg}", file=sys.stderr)
            if e.retry_after:
                print(
                    f"    Hint: Wait {e.retry_after} seconds before retrying",
                    file=sys.stderr,
                )
        except EOLDAPIError as e:
            error_msg = str(e)
            errors[product] = {"type": "api_error", "message": error_msg}
            print(f"  [ERROR] {error_msg}", file=sys.stderr)

    # Check if we got any successful results
    if not results:
        # If all products were filtered to empty (no errors), that's OK - not an error
        if filtered_empty and not errors:
            info("\nAll products fetched successfully but no releases matched filters.")
            return

        has_not_found = any(e["type"] == "not_found" for e in errors.values())
        if has_not_found:
            print(
                "\nCheck available products at https://endoflife.date/ "
                "or run: endoflife-fetcher --list-products",
                file=sys.stderr,
            )
        if has_not_found:
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
                output = os.path.join(config.output_dir, config.combined_filename)
                info(f"\nNo output path specified, using default: {output}")

            save_json(results, output)
            info(f"\nSaved data for {len(results)} product(s) to: {output}")
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
                    file_path = os.path.join(config.output_dir, f"{product}-eol.json")

                save_json(data, file_path)
                saved_files.append((product, file_path))

            if len(saved_files) == 1:
                info(f"\nSaved data for '{saved_files[0][0]}' to: {saved_files[0][1]}")
            else:
                info(f"\nSaved data for {len(saved_files)} products:")
                for product, file_path in saved_files:
                    info(f"  - {product}: {file_path}")

    except FileSaveError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(12)

    # Report on any errors
    if errors:
        failed_names = ", ".join(errors.keys())
        print(f"\n{len(errors)} product(s) failed: {failed_names}", file=sys.stderr)
        if any(e["type"] == "not_found" for e in errors.values()):
            print(
                "Check available products at https://endoflife.date/ "
                "or run: endoflife-fetcher --list-products",
                file=sys.stderr,
            )
        # Exit with partial success code (we got some data but not all)
        sys.exit(5)

    # Check EOL status if --check is enabled
    if args.check:
        eol_found = check_eol_status(results, args.warn_days)
        if eol_found:
            print("\n[WARNING] EOL Check Failed:", file=sys.stderr)
            for item in eol_found:
                if item["days_until"] is None:
                    status = "already EOL"
                elif item["days_until"] < 0:
                    status = f"EOL {-item['days_until']} days ago"
                elif item["days_until"] == 0:
                    status = "EOL today"
                else:
                    status = f"EOL in {item['days_until']} days"
                print(
                    f"  - {item['product']} {item['cycle']}: {status} ({item['eol']})",
                    file=sys.stderr,
                )
            sys.exit(1)


if __name__ == "__main__":
    main()
