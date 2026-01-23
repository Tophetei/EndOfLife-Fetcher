"""
Tests for custom exception classes.
"""

from endoflife_fetcher import (
    EOLDAPIError,
    FileSaveError,
    ProductNotFoundError,
    RateLimitError,
)


class TestEOLDAPIError:
    """Tests for the base EOLDAPIError exception."""

    def test_is_exception(self):
        """Test that EOLDAPIError is an Exception."""
        error = EOLDAPIError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"


class TestProductNotFoundError:
    """Tests for ProductNotFoundError exception."""

    def test_is_eoldapi_error(self):
        """Test that ProductNotFoundError inherits from EOLDAPIError."""
        error = ProductNotFoundError("Product not found")
        assert isinstance(error, EOLDAPIError)
        assert isinstance(error, Exception)

    def test_message(self):
        """Test exception message."""
        error = ProductNotFoundError("Product 'foo' not found")
        assert "foo" in str(error)


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_is_eoldapi_error(self):
        """Test that RateLimitError inherits from EOLDAPIError."""
        error = RateLimitError("Rate limit exceeded")
        assert isinstance(error, EOLDAPIError)
        assert isinstance(error, Exception)

    def test_retry_after_none_by_default(self):
        """Test that retry_after is None when not provided."""
        error = RateLimitError("Rate limit exceeded")
        assert error.retry_after is None

    def test_retry_after_with_seconds(self):
        """Test that RateLimitError stores retry_after as integer."""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        assert error.retry_after == 60
        assert "Rate limit exceeded" in str(error)

    def test_retry_after_with_http_date(self):
        """Test that RateLimitError stores retry_after as string (HTTP date)."""
        http_date = "Wed, 21 Oct 2025 07:28:00 GMT"
        error = RateLimitError("Rate limit exceeded", retry_after=http_date)
        assert error.retry_after == http_date


class TestFileSaveError:
    """Tests for FileSaveError exception."""

    def test_is_exception(self):
        """Test that FileSaveError is an Exception."""
        error = FileSaveError("Save failed")
        assert isinstance(error, Exception)
        assert str(error) == "Save failed"

    def test_not_eoldapi_error(self):
        """Test that FileSaveError is NOT an EOLDAPIError (different hierarchy)."""
        error = FileSaveError("Save failed")
        assert not isinstance(error, EOLDAPIError)
