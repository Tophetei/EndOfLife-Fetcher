"""Constants for endoflife-fetcher."""

# API Configuration
BASE_URL = "https://endoflife.date/api/v1"

# Exit codes
EXIT_SUCCESS = 0
EXIT_EOL_CHECK_FAILED = 1  # --check found EOL/expiring products
EXIT_PARTIAL_SUCCESS = 5  # Some products succeeded, some failed
EXIT_NOT_FOUND = 10  # Product not found (HTTP 404)
EXIT_API_ERROR = 11  # Network or API error
EXIT_FILE_ERROR = 12  # File writing error
EXIT_RATE_LIMIT = 13  # Rate limit exceeded (HTTP 429)
