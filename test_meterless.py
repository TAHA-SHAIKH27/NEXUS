"""Mocked unit tests for the Meterless Runtime provider. No live Nightshift calls."""

import json

import pytest

from backend.tools.meterless import (
    DEFAULT_BASE_URL,
    MeterlessAuthError,
    MeterlessClient,
    MeterlessConfig,
    MeterlessUnavailableError,
    auto_detect,
    chat_completion,
    normalize_base_url,
)


class FakeTransport:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def request(self, url, method="GET", headers=None, body=None, timeout=180):
        self.calls.append({"url": url, "method": method, "headers": headers or {}, "body": body, "timeout": timeout})
        return self.handler(url, method, headers or {}, body)


def test_normalize_avoids_v1_v1():
    assert normalize_base_url("http://127.0.0.1:8088/v1") == "http://127.0.0.1:8088/v1"
    assert normalize_base_url("127.0.0.1:8088") == "http://127.0.0.1:8088/v1"
    assert normalize_base_url("http://127.0.0.1:8088/v1/chat/completions") == "http://127.0.0.1:8088/v1"
    assert normalize_base_url("http://127.0.0.1:8088/v1/models") == "http://127.0.0.1:8088/v1"
    assert normalize_base_url("http://127.0.0.1:8088/healthz") == "http://127.0.0.1:8088/v1"
    assert normalize_base_url("") == DEFAULT_BASE_URL


def test_placeholder_token_rejected():
    cfg = MeterlessConfig.from_config_dict({"meterless_runtime_token": "rt-local"})
    ok, err = cfg.token_status()
    assert not ok
    assert "rt-local" in err
    client = MeterlessClient(cfg, transport=FakeTransport(lambda *a: (200, {})))
    snap = client.status()
    assert snap["status"] == "unauthorized"
    assert snap["live"] is False


def test_missing_token_unauthorized():
    snap = MeterlessClient(MeterlessConfig(token=""), transport=FakeTransport(lambda *a: (200, {}))).status()
    assert snap["status"] == "unauthorized"
    assert snap["live"] is False


def test_models_401_is_unauthorized_not_offline():
    def handler(url, method, headers, body):
        return 401, {"error": "bad token"}

    client = MeterlessClient(MeterlessConfig(token="real-token"), transport=FakeTransport(handler))
    snap = client.status()
    assert snap["status"] == "unauthorized"
    assert snap["live"] is False


def test_models_200_without_meterless_ids_is_offline():
    def handler(url, method, headers, body):
        return 200, {"data": [{"id": "gpt-4o"}]}

    client = MeterlessClient(MeterlessConfig(token="real-token"), transport=FakeTransport(handler))
    snap = client.status()
    assert snap["status"] == "offline"
    assert snap["live"] is False


def test_models_200_with_meterless_ids_is_online():
    def handler(url, method, headers, body):
        return 200, {"data": [{"id": "meterless/auto"}, {"id": "meterless/deep"}]}

    client = MeterlessClient(MeterlessConfig(token="real-token"), transport=FakeTransport(handler))
    snap = client.status()
    assert snap["status"] == "online"
    assert snap["live"] is True
    assert "meterless/auto" in snap["models"]


def test_connection_error_is_offline():
    class Boom(FakeTransport):
        def request(self, *args, **kwargs):
            raise MeterlessUnavailableError("Cannot reach Meterless runtime: timed out")

    snap = MeterlessClient(MeterlessConfig(token="real-token"), transport=Boom(lambda *a: (0, {}))).status()
    assert snap["status"] == "offline"
    assert snap["live"] is False


def test_chat_sends_required_headers_and_returns_string():
    def handler(url, method, headers, body):
        assert method == "POST"
        assert headers["Authorization"] == "Bearer abc"
        assert headers["meterless-app"] == "nexus"
        assert headers["meterless-scope"] == "user"
        payload = json.loads(body.decode("utf-8"))
        assert payload["model"] == "meterless/deep"
        assert payload["messages"][-1]["content"] == "hello"
        return 200, {"choices": [{"message": {"content": "world"}}]}

    text = chat_completion(
        "hello",
        {"meterless_runtime_token": "abc"},
        transport=FakeTransport(handler),
    )
    assert text == "world"
    assert isinstance(text, str)


def test_chat_unauthorized():
    def handler(url, method, headers, body):
        return 403, {"error": "nope"}

    with pytest.raises(MeterlessAuthError):
        MeterlessClient(MeterlessConfig(token="bad"), transport=FakeTransport(handler)).chat("hello")


def test_auto_detect_first_unauthorized_hit():
    def handler(url, method, headers, body):
        if ":8088" in url:
            return 401, {}
        return 0, {}

    found = auto_detect("tok", transport=FakeTransport(handler))
    assert found == "http://127.0.0.1:8088/v1"


@pytest.mark.live_meterless
def test_live_meterless_opt_in():
    """Run later with RUN_LIVE_METERLESS_TESTS=1 and a real Nightshift token."""
    import os
    if os.environ.get("RUN_LIVE_METERLESS_TESTS") != "1":
        pytest.skip("Live Meterless tests are opt-in")
    from backend.tools.meterless import get_status
    snap = get_status()
    assert snap["status"] in ("online", "unauthorized", "offline")
