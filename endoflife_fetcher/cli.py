"""Command-line interface for endoflife-fetcher."""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .api import EOLDAPIError, fetch_product, fetch_products_list
from .config import Config, load_config
from .exceptions import FileSaveError, ProductNotFoundError, RateLimitError
from .filters import expand_products, filter_releases
from .output import check_eol_status, save_json


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
