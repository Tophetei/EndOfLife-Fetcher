"""
Tests for the fetch_product function.
"""

from unittest.mock import patch

import pytest
import responses

from endoflife_fetcher import (
    BASE_URL,
    EOLDAPIError,
    ProductNotFoundError,
    RateLimitError,
    fetch_product,
)


class TestFetchProductSuccess:
    """Tests for successful fetch_product calls."""

    @responses.activate
    def test_fetch_product_success(self):
        """Test successful product fetch."""
        product = "python"
        mock_data = [
            {
                "cycle": "3.12",
                "releaseDate": "2023-10-02",
                "eol": "2028-10-02",
                "latest": "3.12.0",
                "lts": False,
            }
        ]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        result = fetch_product(product)
        assert result == mock_data
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Accept"] == "application/json"

    @responses.activate
    def test_fetch_product_custom_timeout(self):
        """Test custom timeout parameter."""
        product = "python"
        mock_data = {"test": "data"}

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=mock_data,
            status=200,
        )

        result = fetch_product(product, timeout=30)
        assert result == mock_data

    @responses.activate
    def test_fetch_product_empty_json_response(self):
        """Test handling of empty but valid JSON responses."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=[],
            status=200,
        )

        result = fetch_product(product)
        assert result == []


class TestFetchProductHTTPErrors:
    """Tests for HTTP error responses."""

    @responses.activate
    def test_fetch_product_not_found(self):
        """Test product not found (404 error)."""
        product = "invalid-product"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=404,
        )

        with pytest.raises(ProductNotFoundError) as exc_info:
            fetch_product(product)

        assert "invalid-product" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    @responses.activate
    def test_fetch_product_server_error_500(self):
        """Test server error (500 status code)."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=500,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "500" in str(exc_info.value)
        assert "Server error" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_server_error_other_5xx(self):
        """Test handling of various 5xx status codes (502, 503, 504)."""
        product = "python"

        for status_code in [502, 503, 504]:
            responses.reset()
            responses.add(
                responses.GET,
                f"{BASE_URL}/products/{product}",
                status=status_code,
            )

            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product)

            assert str(status_code) in str(exc_info.value)
            assert "Server error" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_other_http_error(self):
        """Test other HTTP errors (4xx except 404 and 429)."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=403,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "403" in str(exc_info.value)

    @responses.activate
    def test_fetch_product_invalid_json(self):
        """Test invalid JSON response."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            body="Invalid JSON content",
            status=200,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "Invalid JSON" in str(exc_info.value)


class TestFetchProductRateLimit:
    """Tests for rate limit (429) responses."""

    @responses.activate
    def test_rate_limit_with_retry_after_seconds(self):
        """Test rate limit error (429) with Retry-After header in seconds."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            headers={"Retry-After": "60"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after == 60

    @responses.activate
    def test_rate_limit_without_retry_after(self):
        """Test rate limit error (429) without Retry-After header."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after is None

    @responses.activate
    def test_rate_limit_with_http_date(self):
        """Test rate limit error (429) with HTTP date in Retry-After."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            status=429,
            headers={"Retry-After": "Wed, 21 Oct 2025 07:28:00 GMT"},
        )

        with pytest.raises(RateLimitError) as exc_info:
            fetch_product(product)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.retry_after == "Wed, 21 Oct 2025 07:28:00 GMT"


class TestFetchProductNetworkErrors:
    """Tests for network-level errors."""

    def test_fetch_product_timeout(self):
        """Test request timeout."""
        import requests

        product = "python"

        with patch("endoflife_fetcher.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product, timeout=1)

            assert "Network or API error" in str(exc_info.value)

    def test_fetch_product_connection_error(self):
        """Test handling of connection errors."""
        import requests

        product = "python"

        with patch("endoflife_fetcher.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )

            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product)

            assert "Network or API error" in str(exc_info.value)

    def test_fetch_product_ssl_error(self):
        """Test handling of SSL errors."""
        import requests

        product = "python"

        with patch("endoflife_fetcher.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.SSLError("SSL certificate error")

            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product)

            assert "Network or API error" in str(exc_info.value)
