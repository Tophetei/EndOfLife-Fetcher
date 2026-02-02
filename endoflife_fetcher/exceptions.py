"""Custom exceptions for endoflife-fetcher."""

from __future__ import annotations


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
