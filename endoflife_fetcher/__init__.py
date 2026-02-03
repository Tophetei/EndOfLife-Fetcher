"""
EndOfLife-Fetcher: Fetch end-of-life data from endoflife.date API.

This package provides a CLI tool and library for fetching EOL data.
"""

__version__ = "1.0.0"

from .api import fetch_product, fetch_products_list
from .cli import main, parse_args
from .config import Config, find_config_files, load_config
from .constants import BASE_URL
from .exceptions import (
    EOLDAPIError,
    FileSaveError,
    ProductNotFoundError,
    RateLimitError,
)
from .filters import expand_products, filter_releases
from .output import check_eol_status, save_json

__all__ = [
    "__version__",
    "BASE_URL",
    # Exceptions
    "EOLDAPIError",
    "ProductNotFoundError",
    "RateLimitError",
    "FileSaveError",
    # Config
    "Config",
    "find_config_files",
    "load_config",
    # API
    "fetch_product",
    "fetch_products_list",
    # Filters
    "filter_releases",
    "expand_products",
    # Output
    "save_json",
    "check_eol_status",
    # CLI
    "parse_args",
    "main",
]
