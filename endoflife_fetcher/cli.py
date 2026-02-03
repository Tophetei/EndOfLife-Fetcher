"""Command-line interface for endoflife-fetcher."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from . import __version__
from .api import EOLDAPIError, fetch_product, fetch_products_list
from .config import Config, load_config
from .constants import (
    EXIT_API_ERROR,
    EXIT_EOL_CHECK_FAILED,
    EXIT_FILE_ERROR,
    EXIT_NOT_FOUND,
    EXIT_PARTIAL_SUCCESS,
    EXIT_RATE_LIMIT,
)
from .exceptions import FileSaveError, ProductNotFoundError, RateLimitError
from .filters import expand_products, filter_releases
from .output import check_eol_status, save_json


def _info(msg: str, quiet: bool) -> None:
    """Print message unless quiet mode is enabled."""
    if not quiet:
        print(msg)


def _extract_config_path() -> str | None:
    """Extract --config path from argv before full parsing."""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv):
            return sys.argv[i + 1]
        elif arg.startswith("--config="):
            return arg.split("=", 1)[1]
    return None


def _handle_list_products(args: argparse.Namespace) -> None:
    """Handle --list-products flag."""
    _info("Fetching products list...", args.quiet)
    try:
        products_list = fetch_products_list(
            timeout=args.timeout, max_retries=args.max_retries
        )
        for product in products_list:
            print(product)
    except EOLDAPIError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(EXIT_API_ERROR)


def _expand_and_validate_products(
    products: list[str], groups: dict[str, list[str]]
) -> list[str]:
    """Expand product groups and validate."""
    if not products:
        print(
            "[ERROR] No products specified. "
            "Use --list-products to see available products.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        expanded, unknown_groups = expand_products(products, groups)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    if unknown_groups:
        if not expanded:
            groups_str = ", ".join(f"@{g}" for g in unknown_groups)
            print(f"[ERROR] Unknown group(s): {groups_str}", file=sys.stderr)
            sys.exit(1)
        else:
            for group in unknown_groups:
                print(f"Warning: Unknown group '@{group}', skipping", file=sys.stderr)

    return expanded


def _fetch_all_products(
    products: list[str], args: argparse.Namespace
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """
    Fetch data for all products.

    Returns:
        Tuple of (results, errors, filtered_empty)
    """
    results: dict[str, Any] = {}
    errors: dict[str, Any] = {}
    filtered_empty: list[str] = []

    for product in products:
        try:
            _info(f"Fetching data for '{product}'...", args.quiet)
            data = fetch_product(
                product, timeout=args.timeout, max_retries=args.max_retries
            )

            data = filter_releases(data, lts=args.lts, active=args.active)

            if not data:
                _info(f"  [OK] No releases match filters for '{product}'", args.quiet)
                filtered_empty.append(product)
            else:
                results[product] = data
                _info(f"  [OK] Successfully fetched data for '{product}'", args.quiet)

        except ProductNotFoundError as e:
            errors[product] = {"type": "not_found", "message": str(e)}
            print(f"  [ERROR] {e}", file=sys.stderr)

        except RateLimitError as e:
            errors[product] = {
                "type": "rate_limit",
                "message": str(e),
                "retry_after": e.retry_after,
            }
            print(f"  [ERROR] {e}", file=sys.stderr)
            if e.retry_after:
                print(
                    f"    Hint: Wait {e.retry_after} seconds before retrying",
                    file=sys.stderr,
                )

        except EOLDAPIError as e:
            errors[product] = {"type": "api_error", "message": str(e)}
            print(f"  [ERROR] {e}", file=sys.stderr)

    return results, errors, filtered_empty


def _handle_no_results(
    errors: dict[str, Any], filtered_empty: list[str], quiet: bool
) -> None:
    """Handle case when no results were fetched. Exits the program."""
    if filtered_empty and not errors:
        _info(
            "\nAll products fetched successfully but no releases matched filters.",
            quiet,
        )
        return

    has_not_found = any(e["type"] == "not_found" for e in errors.values())
    if has_not_found:
        print(
            "\nCheck available products at https://endoflife.date/ "
            "or run: endoflife-fetcher --list-products",
            file=sys.stderr,
        )

    if has_not_found:
        sys.exit(EXIT_NOT_FOUND)
    elif any(e["type"] == "rate_limit" for e in errors.values()):
        sys.exit(EXIT_RATE_LIMIT)
    else:
        sys.exit(EXIT_API_ERROR)


def _save_results(
    results: dict[str, Any],
    products: list[str],
    output: str | None,
    one_file: bool,
    config: Config,
    quiet: bool,
) -> None:
    """Save results to JSON file(s)."""
    try:
        if one_file:
            if not output:
                output = os.path.join(config.output_dir, config.combined_filename)
                _info(f"\nNo output path specified, using default: {output}", quiet)

            save_json(results, output)
            _info(f"\nSaved data for {len(results)} product(s) to: {output}", quiet)
        else:
            if output and len(products) > 1:
                print(
                    "\nWarning: --output specified with multiple products "
                    "but --one-file not used. Using default naming pattern.",
                    file=sys.stderr,
                )
                output = None

            saved_files = []
            for product, data in results.items():
                if output and len(products) == 1:
                    file_path = output
                else:
                    file_path = os.path.join(config.output_dir, f"{product}-eol.json")

                save_json(data, file_path)
                saved_files.append((product, file_path))

            if len(saved_files) == 1:
                _info(
                    f"\nSaved data for '{saved_files[0][0]}' to: {saved_files[0][1]}",
                    quiet,
                )
            else:
                _info(f"\nSaved data for {len(saved_files)} products:", quiet)
                for product, file_path in saved_files:
                    _info(f"  - {product}: {file_path}", quiet)

    except FileSaveError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(EXIT_FILE_ERROR)


def _report_partial_errors(errors: dict[str, Any]) -> None:
    """Report errors when some products failed but others succeeded."""
    failed_names = ", ".join(errors.keys())
    print(f"\n{len(errors)} product(s) failed: {failed_names}", file=sys.stderr)

    if any(e["type"] == "not_found" for e in errors.values()):
        print(
            "Check available products at https://endoflife.date/ "
            "or run: endoflife-fetcher --list-products",
            file=sys.stderr,
        )

    sys.exit(EXIT_PARTIAL_SUCCESS)


def _handle_check_mode(results: dict[str, Any], warn_days: int) -> None:
    """Handle --check mode. Exits with code 1 if EOL products found."""
    eol_found = check_eol_status(results, warn_days)

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
        sys.exit(EXIT_EOL_CHECK_FAILED)


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
    # Load configuration
    config_path = _extract_config_path()
    try:
        config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    args = parse_args(config)

    # Handle --list-products
    if args.list_products:
        _handle_list_products(args)
        return

    # Expand and validate products
    products = _expand_and_validate_products(
        args.products or config.products, config.groups
    )

    # Fetch all products
    results, errors, filtered_empty = _fetch_all_products(products, args)

    # Handle no results
    if not results:
        _handle_no_results(errors, filtered_empty, args.quiet)
        return

    # Save results
    _save_results(results, products, args.output, args.one_file, config, args.quiet)

    # Report partial errors
    if errors:
        _report_partial_errors(errors)

    # Check EOL status if requested
    if args.check:
        _handle_check_mode(results, args.warn_days)
