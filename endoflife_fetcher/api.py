"""API client for endoflife.date."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import BASE_URL, EOLDAPIError, ProductNotFoundError, RateLimitError


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
