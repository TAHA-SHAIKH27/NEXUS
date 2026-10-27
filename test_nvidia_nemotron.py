"""Mocked tests for the FPO NVIDIA Nemotron adapter. Does not call NIM."""

import json

import pytest

from backend.tools.nvidia_nemotron import (
    DEFAULT_FPO_MODEL,
    FPO_NEMOTRON_MODELS,
    NEMOTRON_BOLT_E4B,
    NEMOTRON_LIGHTNING_30B_A3B,
    NvidiaAuthError,
    NvidiaFpoConfig,
    NvidiaNemotronClient,
    NvidiaUnavailableError,
    chat_completion,
    list_fpo_models,
)


class FakeTransport:
    def __init__(self, handler):
        self.handler = handler

    def request(self, url, method="GET", headers=None, body=None, timeout=120):
        return self.handler(url, method, headers or {}, body)


def test_official_model_ids():
    assert NEMOTRON_BOLT_E4B == "nvidia/nemotron-3.5-bolt-e4b"
    assert NEMOTRON_LIGHTNING_30B_A3B == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert set(FPO_NEMOTRON_MODELS) == {NEMOTRON_BOLT_E4B, NEMOTRON_LIGHTNING_30B_A3B}
    ids = {m["id"] for m in list_fpo_models()}
    assert ids == set(FPO_NEMOTRON_MODELS)


def test_unknown_model_falls_back_to_bolt():
    cfg = NvidiaFpoConfig.from_config_dict({
        "nvidia_api_key": "k",
        "nvidia_fpo_model": "totally-invented/model",
    })
    assert cfg.model == DEFAULT_FPO_MODEL


def test_code_core_nvidia_model_is_not_used():
    cfg = NvidiaFpoConfig.from_config_dict({
        "nvidia_api_key": "k",
        "nvidia_model": "z-ai/glm-5.3-flash",
        "nvidia_fpo_model": NEMOTRON_LIGHTNING_30B_A3B,
    })
    assert cfg.model == NEMOTRON_LIGHTNING_30B_A3B


def test_missing_key_unconfigured():
    snap = NvidiaNemotronClient(NvidiaFpoConfig(api_key=""), transport=FakeTransport(lambda *a: (200, {}))).status()
    assert snap["status"] == "unconfigured"
    assert snap["live"] is False


def test_models_probe_401():
    def handler(url, method, headers, body):
        return 401, {"error": "no"}

    snap = NvidiaNemotronClient(NvidiaFpoConfig(api_key="bad"), transport=FakeTransport(handler)).status()
    assert snap["status"] == "unauthorized"
    assert snap["live"] is False


def test_models_probe_offline():
    class Boom:
        def request(self, *args, **kwargs):
            raise NvidiaUnavailableError("timeout")

    snap = NvidiaNemotronClient(NvidiaFpoConfig(api_key="k"), transport=Boom()).status()
    assert snap["status"] == "offline"


def test_chat_mocked_success():
    def handler(url, method, headers, body):
        assert "integrate.api.nvidia.com" in url
        payload = json.loads(body.decode("utf-8"))
        assert payload["model"] == NEMOTRON_BOLT_E4B
        return 200, {"choices": [{"message": {"content": "Explain only."}}]}

    text = chat_completion(
        "hello",
        {"nvidia_api_key": "k"},
        transport=FakeTransport(handler),
    )
    assert text == "Explain only."


def test_chat_unauthorized():
    def handler(url, method, headers, body):
        return 401, {}

    with pytest.raises(NvidiaAuthError):
        NvidiaNemotronClient(NvidiaFpoConfig(api_key="bad"), transport=FakeTransport(handler)).chat("x")


@pytest.mark.live_nvidia
def test_live_nvidia_opt_in():
    import os
    if os.environ.get("RUN_LIVE_NVIDIA_TESTS") != "1":
        pytest.skip("Live NVIDIA tests are opt-in")
    from backend.tools.nvidia_nemotron import get_status
    snap = get_status()
    assert snap["status"] in ("online", "unauthorized", "offline", "unconfigured")
