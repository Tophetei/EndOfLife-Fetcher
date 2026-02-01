"""
Tests for the fetch_product function.
"""

from unittest.mock import patch

import pytest
import requests
import responses

from endoflife_fetcher import (
    BASE_URL,
    EOLDAPIError,
    ProductNotFoundError,
    RateLimitError,
    fetch_product,
    fetch_products_list,
)


def make_v1_response(releases):
    """Helper to wrap releases in v1 API response structure."""
    return {"result": {"releases": releases}}


class TestFetchProductSuccess:
    """Tests for successful fetch_product calls."""

    @responses.activate
    def test_fetch_product_success(self):
        """Test successful product fetch returns releases list."""
        product = "python"
        releases = [
            {
                "name": "3.12",
                "releaseDate": "2023-10-02",
                "isEol": False,
                "eolFrom": "2028-10-31",
                "isLts": False,
            }
        ]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
            status=200,
        )

        result = fetch_product(product)
        assert result == releases
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Accept"] == "application/json"

    @responses.activate
    def test_fetch_product_custom_timeout(self):
        """Test custom timeout parameter."""
        product = "python"
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response(releases),
            status=200,
        )

        result = fetch_product(product, timeout=30)
        assert result == releases

    @responses.activate
    def test_fetch_product_empty_releases(self):
        """Test handling of empty releases list."""
        product = "python"

        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json=make_v1_response([]),
            status=200,
        )

        result = fetch_product(product)
        assert result == []

    @responses.activate
    def test_fetch_product_invalid_structure(self):
        """Test handling of unexpected API response structure."""
        product = "python"

        # Missing result.releases structure
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json={"unexpected": "structure"},
            status=200,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product)

        assert "Unexpected API response structure" in str(exc_info.value)


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
        product = "python"

        with patch.object(
            requests.Session, "get", side_effect=requests.exceptions.Timeout("timeout")
        ):
            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product, timeout=1, max_retries=0)

            assert "Network or API error" in str(exc_info.value)

    def test_fetch_product_connection_error(self):
        """Test handling of connection errors."""
        product = "python"

        with patch.object(
            requests.Session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product, max_retries=0)

            assert "Network or API error" in str(exc_info.value)

    def test_fetch_product_ssl_error(self):
        """Test handling of SSL errors."""
        product = "python"

        with patch.object(
            requests.Session,
            "get",
            side_effect=requests.exceptions.SSLError("SSL certificate error"),
        ):
            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_product(product, max_retries=0)

            assert "Network or API error" in str(exc_info.value)


class TestFetchProductRetry:
    """Tests for retry behavior with transient failures."""

    @responses.activate
    def test_retry_succeeds_after_server_error(self):
        """Test that retry recovers from transient 503 error."""
        product = "python"
        releases = [{"name": "3.12", "isEol": False, "eolFrom": "2028-10-31"}]

        # First request fails with 503, second succeeds
        responses.add(responses.GET, f"{BASE_URL}/products/{product}", status=503)
        responses.add(
            responses.GET,
            f"{BASE_URL}/products/{product}",
            json={"result": {"releases": releases}},
            status=200,
        )

        # With retry enabled, should succeed
        result = fetch_product(product, max_retries=3)
        assert len(result) == 1
        assert result[0]["name"] == "3.12"

    @responses.activate
    def test_retry_disabled_fails_immediately(self):
        """Test that max_retries=0 disables retry."""
        product = "python"

        responses.add(responses.GET, f"{BASE_URL}/products/{product}", status=503)

        # With retry disabled, should fail immediately
        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_product(product, max_retries=0)

        assert "Server error 503" in str(exc_info.value)


class TestFetchProductsList:
    """Tests for fetch_products_list function."""

    @responses.activate
    def test_fetch_products_list_success(self):
        """Test successful fetch returns list of product names."""
        api_response = {
            "total": 3,
            "result": [
                {"name": "python", "label": "Python"},
                {"name": "nodejs", "label": "Node.js"},
                {"name": "ubuntu", "label": "Ubuntu"},
            ],
        }

        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            json=api_response,
            status=200,
        )

        result = fetch_products_list()
        assert result == ["python", "nodejs", "ubuntu"]

    @responses.activate
    def test_fetch_products_list_custom_timeout(self):
        """Test fetch_products_list with custom timeout."""
        api_response = {"total": 1, "result": [{"name": "python", "label": "Python"}]}

        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            json=api_response,
            status=200,
        )

        result = fetch_products_list(timeout=30)
        assert result == ["python"]

    @responses.activate
    def test_fetch_products_list_server_error(self):
        """Test handling of server errors."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            status=500,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_products_list()

        assert "Server error" in str(exc_info.value)

    @responses.activate
    def test_fetch_products_list_rate_limit(self):
        """Test handling of rate limit errors."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            status=429,
            headers={"Retry-After": "60"},
        )

        with pytest.raises(RateLimitError):
            fetch_products_list()

    @responses.activate
    def test_fetch_products_list_invalid_structure(self):
        """Test handling of unexpected API response structure."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            json={"unexpected": "structure"},
            status=200,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_products_list()

        assert "Unexpected API response" in str(exc_info.value)

    def test_fetch_products_list_network_error(self):
        """Test handling of network errors (RequestException)."""
        with patch.object(
            requests.Session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with pytest.raises(EOLDAPIError) as exc_info:
                fetch_products_list(max_retries=0)

            assert "Network or API error" in str(exc_info.value)

    @responses.activate
    def test_fetch_products_list_client_error(self):
        """Test handling of HTTP 4xx client errors (non-404, non-429)."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            status=400,
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_products_list()

        assert "HTTP 400 error" in str(exc_info.value)

    @responses.activate
    def test_fetch_products_list_invalid_json(self):
        """Test handling of invalid JSON response (HTML error page)."""
        responses.add(
            responses.GET,
            f"{BASE_URL}/products",
            body="<html><body>Not Found</body></html>",
            status=200,
            content_type="text/html",
        )

        with pytest.raises(EOLDAPIError) as exc_info:
            fetch_products_list()

        assert "Invalid JSON" in str(exc_info.value)
