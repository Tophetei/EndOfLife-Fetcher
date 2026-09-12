"""API client for endoflife.date."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import BASE_URL, MAX_RESPONSE_BYTES
from .exceptions import (
    EOLDAPIError,
    ProductNotFoundError,
    RateLimitError,
    ResponseTooLargeError,
)


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


def _read_capped(resp: requests.Response, url: str, max_bytes: int) -> bytes:
    """
    Read a streamed response body, refusing anything past max_bytes.

    Args:
        resp: Streamed response to read from
        url: Requested URL, for error messages
        max_bytes: Maximum number of body bytes to accept

    Returns:
        Raw response body

    Raises:
        ResponseTooLargeError: If the body exceeds max_bytes
        EOLDAPIError: For network errors while reading the body
    """
    # Trust Content-Length only to fail early; it is absent on chunked responses
    declared = resp.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise ResponseTooLargeError(
            f"Response from {url} declares {declared} bytes, over the "
            f"{max_bytes} byte limit."
        )

    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLargeError(
                    f"Response from {url} exceeds the {max_bytes} byte limit."
                )
            chunks.append(chunk)
    except requests.exceptions.RequestException as e:
        raise EOLDAPIError(f"Network or API error while reading {url}: {e}") from e

    return b"".join(chunks)


def _api_get(
    endpoint: str,
    timeout: float = 15,
    max_retries: int = 3,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """
    Make a GET request to the endoflife.date API.

    Handles common error cases: network errors, rate limits, server errors,
    oversized bodies, and JSON parsing.

    Args:
        endpoint: API endpoint (e.g., '/products' or '/products/python')
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)
        max_bytes: Maximum response body size to accept, in bytes

    Returns:
        Parsed JSON response as dict

    Raises:
        RateLimitError: If rate limit is exceeded (HTTP 429)
        ResponseTooLargeError: If the response body exceeds max_bytes
        EOLDAPIError: For network errors, server errors, or invalid responses

    Note:
        Does NOT handle 404 - callers should check for that if needed.
    """
    url = f"{BASE_URL}{endpoint}"
    session = create_retry_session(max_retries=max_retries)

    try:
        resp = session.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json"},
            stream=True,
        )
    except requests.exceptions.RequestException as e:
        raise EOLDAPIError(f"Network or API error while requesting {url}: {e}") from e

    # Streaming leaves the body unread, so every path below must close the
    # response rather than rely on it being consumed.
    with resp:
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    retry_seconds = int(retry_after)
                    raise RateLimitError(
                        f"Rate limit exceeded. Please retry after "
                        f"{retry_seconds} seconds.",
                        retry_after=retry_seconds,
                    )
                except ValueError:
                    # Retry-After might be an HTTP date instead of seconds
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

        body = _read_capped(resp, url, max_bytes)

    try:
        return cast(dict[str, Any], json.loads(body))
    except ValueError as e:
        raise EOLDAPIError(f"Invalid JSON received from API: {e}") from e


def fetch_product(
    product: str,
    timeout: float = 15,
    max_retries: int = 3,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> list[dict[str, Any]]:
    """
    Fetch end-of-life data for a specific product.

    Args:
        product: Product slug (e.g., 'python', 'ubuntu', 'nodejs')
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)
        max_bytes: Maximum response body size to accept, in bytes

    Returns:
        List of release dicts from the API

    Raises:
        ProductNotFoundError: If the product is not found (404)
        ResponseTooLargeError: If the response body exceeds max_bytes
        EOLDAPIError: For network errors, server errors, or invalid responses
    """
    # requests resolves dot segments, so an unescaped '../categories' would
    # silently retarget another endpoint on the same host
    data = _api_get(
        f"/products/{quote(product, safe='')}",
        timeout=timeout,
        max_retries=max_retries,
        max_bytes=max_bytes,
    )

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
        return cast(list[dict[str, Any]], data["result"]["releases"])
    except (KeyError, TypeError) as e:
        raise EOLDAPIError(
            f"Unexpected API response structure for '{product}': {e}"
        ) from e


def fetch_products_list(
    timeout: float = 15,
    max_retries: int = 3,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> list[str]:
    """
    Fetch list of all available product names from the API.

    Args:
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts for transient failures (0 to disable)
        max_bytes: Maximum response body size to accept, in bytes

    Returns:
        List of product slugs (e.g., ['python', 'nodejs', 'ubuntu', ...])

    Raises:
        ResponseTooLargeError: If the response body exceeds max_bytes
        EOLDAPIError: For network errors, server errors, or invalid responses
    """
    data = _api_get(
        "/products", timeout=timeout, max_retries=max_retries, max_bytes=max_bytes
    )

    # Handle unexpected error responses
    if data.get("_ok") is False:
        raise EOLDAPIError(
            f"HTTP {data.get('_status_code')} error from endoflife.date."
        )

    try:
        return [product["name"] for product in data["result"]]
    except (KeyError, TypeError) as e:
        raise EOLDAPIError(f"Unexpected API response structure: {e}") from e
