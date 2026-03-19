"""
Tests for ConnectionPool.

All HTTP calls are intercepted with unittest.mock — no real network traffic.
Covers:
- ConnectionPool construction
- request() with all HTTP verbs
- JSON body serialisation and Content-Type header
- Custom timeout propagation
- Convenience helpers (get, post, put, delete)
- clear() and stats()
- Module-level singleton
"""

import json as _json
import pytest
from unittest.mock import MagicMock, patch, call

import urllib3

from zenus_core.execution.connection_pool import (
    ConnectionPool,
    _json_encode,
    get_connection_pool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(**kwargs) -> ConnectionPool:
    """Build a ConnectionPool with a mocked PoolManager."""
    with patch("zenus_core.execution.connection_pool.urllib3.PoolManager"):
        pool = ConnectionPool(**kwargs)
    pool._pool = MagicMock()
    return pool


def _fake_response(status: int = 200, data: bytes = b"ok") -> MagicMock:
    resp = MagicMock(spec=urllib3.HTTPResponse)
    resp.status = status
    resp.data = data
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConnectionPoolConstruction:
    def test_creates_pool_manager(self):
        with patch("zenus_core.execution.connection_pool.urllib3.PoolManager") as mock_pm:
            ConnectionPool(num_pools=5, maxsize=8, timeout=10.0)
        mock_pm.assert_called_once()

    def test_default_timeout_set(self):
        pool = _make_pool(timeout=15.0)
        assert pool._default_timeout.connect_timeout == 15.0
        assert pool._default_timeout.read_timeout == 15.0

    def test_attributes(self):
        pool = _make_pool(num_pools=3, maxsize=4, timeout=5.0, retries=2)
        assert pool._default_timeout is not None


# ---------------------------------------------------------------------------
# request() — basic
# ---------------------------------------------------------------------------

class TestConnectionPoolRequest:
    def test_get_request(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        resp = pool.request("GET", "http://example.com/")
        pool._pool.request.assert_called_once()
        args, kwargs = pool._pool.request.call_args
        assert args[0] == "GET"
        assert args[1] == "http://example.com/"

    def test_returns_response(self):
        pool = _make_pool()
        fake = _fake_response(status=201, data=b"created")
        pool._pool.request.return_value = fake
        resp = pool.request("POST", "http://example.com/items")
        assert resp.status == 201

    def test_method_uppercased(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("post", "http://example.com/")
        args, _ = pool._pool.request.call_args
        assert args[0] == "POST"

    def test_headers_passed(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("GET", "http://x.com/", headers={"Authorization": "Bearer tok"})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer tok"

    def test_body_passed(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("POST", "http://x.com/", body=b"raw body")
        _, kwargs = pool._pool.request.call_args
        assert kwargs["body"] == b"raw body"

    def test_fields_passed(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("POST", "http://x.com/", fields={"key": "val"})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["fields"] == {"key": "val"}


# ---------------------------------------------------------------------------
# request() — JSON serialisation
# ---------------------------------------------------------------------------

class TestConnectionPoolJSON:
    def test_json_encoded_to_body(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("POST", "http://x.com/", json={"name": "zenus"})
        _, kwargs = pool._pool.request.call_args
        body = kwargs["body"]
        assert _json.loads(body) == {"name": "zenus"}

    def test_content_type_set_for_json(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("POST", "http://x.com/", json={"a": 1})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["headers"]["Content-Type"] == "application/json"

    def test_content_type_not_overridden_if_already_set(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request(
            "POST", "http://x.com/", json={"a": 1},
            headers={"Content-Type": "text/plain"},
        )
        _, kwargs = pool._pool.request.call_args
        # setdefault: caller's header wins
        assert kwargs["headers"]["Content-Type"] == "text/plain"

    def test_json_list(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("POST", "http://x.com/", json=[1, 2, 3])
        _, kwargs = pool._pool.request.call_args
        assert _json.loads(kwargs["body"]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# request() — timeout
# ---------------------------------------------------------------------------

class TestConnectionPoolTimeout:
    def test_custom_timeout_used(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.request("GET", "http://x.com/", timeout=5.0)
        _, kwargs = pool._pool.request.call_args
        # Custom timeout is passed as Timeout object
        assert kwargs["timeout"].total == 5.0

    def test_default_timeout_used_when_none(self):
        pool = _make_pool(timeout=30.0)
        pool._pool.request.return_value = _fake_response()
        pool.request("GET", "http://x.com/")
        _, kwargs = pool._pool.request.call_args
        assert kwargs["timeout"] is pool._default_timeout


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

class TestConvenienceHelpers:
    def test_get_calls_request_with_get(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.get("http://x.com/")
        args, _ = pool._pool.request.call_args
        assert args[0] == "GET"

    def test_get_passes_headers(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.get("http://x.com/", headers={"X-Token": "abc"})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["headers"]["X-Token"] == "abc"

    def test_post_calls_request_with_post(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.post("http://x.com/")
        args, _ = pool._pool.request.call_args
        assert args[0] == "POST"

    def test_post_passes_json(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.post("http://x.com/", json={"key": "val"})
        _, kwargs = pool._pool.request.call_args
        assert _json.loads(kwargs["body"]) == {"key": "val"}

    def test_post_passes_fields(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.post("http://x.com/", fields={"f": "v"})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["fields"] == {"f": "v"}

    def test_put_calls_request_with_put(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.put("http://x.com/resource")
        args, _ = pool._pool.request.call_args
        assert args[0] == "PUT"

    def test_put_passes_json(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.put("http://x.com/resource", json={"updated": True})
        _, kwargs = pool._pool.request.call_args
        assert _json.loads(kwargs["body"]) == {"updated": True}

    def test_delete_calls_request_with_delete(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.delete("http://x.com/resource")
        args, _ = pool._pool.request.call_args
        assert args[0] == "DELETE"

    def test_delete_passes_headers(self):
        pool = _make_pool()
        pool._pool.request.return_value = _fake_response()
        pool.delete("http://x.com/resource", headers={"X-Key": "val"})
        _, kwargs = pool._pool.request.call_args
        assert kwargs["headers"]["X-Key"] == "val"


# ---------------------------------------------------------------------------
# clear() and stats()
# ---------------------------------------------------------------------------

class TestConnectionPoolManagement:
    def test_clear_calls_pool_clear(self):
        pool = _make_pool()
        pool.clear()
        pool._pool.clear.assert_called_once()

    def test_stats_returns_dict(self):
        pool = _make_pool()
        pool._pool.pools.items.return_value = []
        result = pool.stats()
        assert isinstance(result, dict)

    def test_stats_includes_pool_info(self):
        pool = _make_pool()
        mock_inner = MagicMock()
        mock_inner.num_connections = 3
        mock_inner.num_requests = 10
        pool._pool.pools.items.return_value = [("host:443", mock_inner)]
        result = pool.stats()
        assert "host:443" in result
        assert result["host:443"]["num_connections"] == 3
        assert result["host:443"]["num_requests"] == 10


# ---------------------------------------------------------------------------
# _json_encode helper
# ---------------------------------------------------------------------------

class TestJsonEncode:
    def test_encodes_dict(self):
        data = _json_encode({"key": "value"})
        assert _json.loads(data) == {"key": "value"}

    def test_returns_bytes(self):
        assert isinstance(_json_encode({}), bytes)

    def test_encodes_unicode(self):
        data = _json_encode({"emoji": "🚀"})
        parsed = _json.loads(data)
        assert parsed["emoji"] == "🚀"

    def test_encodes_list(self):
        data = _json_encode([1, "two", 3.0])
        assert _json.loads(data) == [1, "two", 3.0]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestGetConnectionPool:
    def test_returns_connection_pool_instance(self):
        pool = get_connection_pool()
        assert isinstance(pool, ConnectionPool)

    def test_singleton_same_instance(self):
        p1 = get_connection_pool()
        p2 = get_connection_pool()
        assert p1 is p2

    def test_singleton_is_functional(self):
        pool = get_connection_pool()
        # Smoke-test: the pool has a PoolManager (not None)
        assert pool._pool is not None
