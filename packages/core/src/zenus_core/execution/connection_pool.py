"""
HTTP Connection Pool

Provides a shared urllib3 connection pool for tools that need to make
outbound HTTP/HTTPS requests from Python (as opposed to spawning curl).

Features:
  - Reuses TCP connections across requests (faster, fewer file descriptors)
  - Configurable pool size per host
  - Retry policy with backoff
  - Thread-safe singleton
  - Optional per-request timeouts

Usage::

    pool = get_connection_pool()
    resp = pool.get("https://api.example.com/data")
    print(resp.status, resp.data)

    # POST with JSON body
    resp = pool.post("https://api.example.com/items", json={"name": "x"})
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Optional

import urllib3
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ConnectionPool
# ---------------------------------------------------------------------------

class ConnectionPool:
    """
    Shared urllib3 connection pool manager.

    Wraps :class:`urllib3.PoolManager` and exposes a simple ``request()``
    interface plus convenience helpers ``get()`` and ``post()``.

    Args:
        num_pools:   Number of distinct host pools to maintain.
        maxsize:     Max connections per host.
        timeout:     Default request timeout in seconds.
        retries:     Total retries on transient failures (429, 5xx, connect errors).
    """

    def __init__(
        self,
        num_pools: int = 10,
        maxsize: int = 10,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist={429, 500, 502, 503, 504},
            allowed_methods={"GET", "HEAD", "OPTIONS"},
            raise_on_status=False,
        )
        self._pool = urllib3.PoolManager(
            num_pools=num_pools,
            maxsize=maxsize,
            retries=retry,
        )
        self._default_timeout = urllib3.util.Timeout(connect=timeout, read=timeout)
        logger.debug(
            "ConnectionPool created (num_pools=%d, maxsize=%d, timeout=%.1fs)",
            num_pools, maxsize, timeout,
        )

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        json: Optional[Any] = None,
        timeout: Optional[float] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> urllib3.HTTPResponse:
        """
        Execute an HTTP request.

        Args:
            method:  HTTP verb (GET, POST, PUT, DELETE, …).
            url:     Full URL including scheme.
            headers: Extra request headers.
            body:    Raw bytes body (mutually exclusive with *json*).
            json:    Python object to JSON-encode as the body.
                     Also sets ``Content-Type: application/json``.
            timeout: Per-request timeout in seconds (overrides default).
            fields:  Form fields (for POST with ``application/x-www-form-urlencoded``).

        Returns:
            :class:`urllib3.HTTPResponse` — caller may read ``.data`` or
            iterate ``.read()``.

        Raises:
            urllib3.exceptions.HTTPError: On connection / protocol errors
                (after retries are exhausted).
        """
        h: Dict[str, str] = headers.copy() if headers else {}

        if json is not None:
            body = _json_encode(json)
            h.setdefault("Content-Type", "application/json")

        kw: Dict[str, Any] = {
            "headers": h,
            "timeout": urllib3.util.Timeout(total=timeout) if timeout else self._default_timeout,
            "preload_content": True,
        }
        if body is not None:
            kw["body"] = body
        if fields is not None:
            kw["fields"] = fields

        logger.debug("→ %s %s", method.upper(), url)
        response = self._pool.request(method.upper(), url, **kw)
        logger.debug("← %d %s", response.status, url)
        return response

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> urllib3.HTTPResponse:
        """HTTP GET."""
        return self.request("GET", url, headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        json: Optional[Any] = None,
        fields: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> urllib3.HTTPResponse:
        """HTTP POST."""
        return self.request(
            "POST", url,
            headers=headers, body=body, json=json,
            fields=fields, timeout=timeout,
        )

    def put(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        json: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> urllib3.HTTPResponse:
        """HTTP PUT."""
        return self.request(
            "PUT", url, headers=headers, body=body, json=json, timeout=timeout
        )

    def delete(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> urllib3.HTTPResponse:
        """HTTP DELETE."""
        return self.request("DELETE", url, headers=headers, timeout=timeout)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Close all open connections and clear pools."""
        self._pool.clear()
        logger.debug("ConnectionPool cleared")

    def stats(self) -> Dict[str, Any]:
        """Return pool statistics (number of active connections per host).

        urllib3's internal pool container does not support thread-safe
        iteration, so this method captures a best-effort snapshot.  If
        iteration is unavailable an empty dict is returned rather than
        raising.
        """
        result: Dict[str, Any] = {}
        try:
            for key, pool in self._pool.pools.items():
                result[str(key)] = {
                    "num_connections": pool.num_connections,
                    "num_requests": pool.num_requests,
                }
        except (NotImplementedError, AttributeError):
            pass
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_encode(obj: Any) -> bytes:
    return _json_module.dumps(obj, ensure_ascii=False).encode("utf-8")


import json as _json_module  # noqa: E402  (placed after function to keep top tidy)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ConnectionPool:
    """Return the global :class:`ConnectionPool` (created on first call)."""
    global _default_pool
    with _pool_lock:
        if _default_pool is None:
            _default_pool = ConnectionPool()
    return _default_pool
