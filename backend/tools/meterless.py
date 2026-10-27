"""
Meterless Runtime (Nightshift hotspot) OpenAI-compatible provider.

Contract: Meterless Runtime 0.90.0
https://github.com/Meterless/Meterless/blob/main/docs/agent-ready/add-meterless-provider.md

This module never claims a live connection. Status is derived from HTTP
responses (or from an injected transport in tests). Placeholder token
`rt-local` is rejected.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.tools.result_schema import ToolResult

PROVIDER_ID = "meterless"
PROVIDER_NAME = "Meterless Runtime"
DEFAULT_BASE_URL = "http://127.0.0.1:8088/v1"
APP_ID = "nexus"
PLACEHOLDER_TOKEN = "rt-local"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MODEL = "meterless/auto"
DETECT_PORTS = (8088, 8090, 8787, 11434)
DETECT_HOSTS = ("127.0.0.1", "localhost", "[::1]")

# Routing modes (not model file names). Unknown meterless/* ids are kept.
KNOWN_ROUTING_MODES = {
    "meterless/auto",
    "meterless/fast",
    "meterless/deep",
    "meterless/cheap",
    "meterless/local",
    "meterless/fusion",
    "meterless/text",
    "meterless/vision",
    "meterless/image",
    "meterless/video",
}


class MeterlessError(Exception):
    """Base Meterless provider error."""

    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


class MeterlessAuthError(MeterlessError):
    def __init__(self, message: str = "unauthorized"):
        super().__init__(message, status="unauthorized")


class MeterlessUnavailableError(MeterlessError):
    def __init__(self, message: str = "offline"):
        super().__init__(message, status="offline")


def normalize_base_url(raw: str) -> str:
    """Normalize pasted URLs to `<host>/v1` without producing `/v1/v1`."""
    value = (raw or "").strip()
    if not value:
        return DEFAULT_BASE_URL
    if "://" not in value:
        value = "http://" + value
    value = value.rstrip("/")
    for suffix in ("/v1/chat/completions", "/v1/models", "/healthz"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    value = value.rstrip("/")
    if value.endswith("/v1"):
        return value
    return value + "/v1"


def origin_from_v1(base_v1: str) -> str:
    base = (base_v1 or DEFAULT_BASE_URL).rstrip("/")
    if base.endswith("/v1"):
        return base[:-3].rstrip("/") or "http://127.0.0.1:8088"
    return base


HttpResponse = Tuple[int, Any]


class HttpTransport:
    """urllib transport; tests inject a fake with the same `.request` signature."""

    def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> HttpResponse:
        req = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8") if resp.length != 0 else ""
                payload: Any = None
                if raw:
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = raw
                return int(getattr(resp, "status", 200) or 200), payload
        except HTTPError as exc:
            detail = exc.read(800).decode("utf-8", errors="replace") if exc.fp else ""
            parsed: Any = detail
            try:
                parsed = json.loads(detail) if detail else {"error": exc.reason}
            except json.JSONDecodeError:
                parsed = {"error": detail or str(exc.reason)}
            return int(exc.code), parsed
        except (URLError, TimeoutError, OSError) as exc:
            raise MeterlessUnavailableError(f"Cannot reach Meterless runtime: {exc}") from exc


@dataclass
class MeterlessConfig:
    base_url: str = DEFAULT_BASE_URL
    token: str = ""
    app_id: str = APP_ID
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    default_model: str = DEFAULT_MODEL
    max_retries: int = 0

    @classmethod
    def from_config_dict(cls, config: Optional[Dict[str, Any]] = None) -> "MeterlessConfig":
        cfg = config or {}
        token = (
            str(cfg.get("meterless_runtime_token") or "").strip()
            or str(os.environ.get("METERLESS_RUNTIME_TOKEN") or "").strip()
        )
        raw_url = (
            str(cfg.get("meterless_base_url") or "").strip()
            or str(os.environ.get("METERLESS_BASE_URL") or "").strip()
            or DEFAULT_BASE_URL
        )
        timeout = int(cfg.get("meterless_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
        return cls(
            base_url=normalize_base_url(raw_url),
            token=token,
            app_id=str(cfg.get("meterless_app_id") or APP_ID).strip().lower() or APP_ID,
            timeout_seconds=max(5, timeout),
            default_model=str(cfg.get("meterless_model") or DEFAULT_MODEL),
            max_retries=int(cfg.get("meterless_max_retries") or 2),
        )

    def token_status(self) -> Tuple[bool, str]:
        if not self.token:
            return False, "Meterless runtime token is not configured"
        if self.token == PLACEHOLDER_TOKEN:
            return False, "Placeholder token rt-local is rejected; paste the token from the Nightshift state directory (proxy-token)"
        if self.token == "********" or self.token == "••••••••":
            return False, "Masked placeholder token detected; the real token was overwritten. Re-enter the Nightshift proxy-token in Settings."
        return True, ""


def _headers(cfg: MeterlessConfig, *, chat: bool = False) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "meterless-app": cfg.app_id,
        "Authorization": f"Bearer {cfg.token}",
    }
    if chat:
        headers["meterless-scope"] = "user"
    return headers


class MeterlessClient:
    def __init__(
        self,
        config: Optional[MeterlessConfig] = None,
        transport: Optional[HttpTransport] = None,
    ):
        self.config = config or MeterlessConfig()
        self.transport = transport or HttpTransport()

    def _call(
        self,
        path: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        *,
        chat: bool = False,
    ) -> HttpResponse:
        ok, err = self.config.token_status()
        if not ok:
            raise MeterlessAuthError(err)
        url = f"{self.config.base_url.rstrip('/')}{path}"
        if path == "/healthz":
            url = f"{origin_from_v1(self.config.base_url)}/healthz"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        last_exc: Optional[Exception] = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                return self.transport.request(
                    url,
                    method=method,
                    headers=_headers(self.config, chat=chat),
                    body=body,
                    timeout=self.config.timeout_seconds,
                )
            except MeterlessUnavailableError as exc:
                last_exc = exc
                if attempt < attempts:
                    time.sleep(min(2 ** (attempt - 1), 4))
                    continue
                raise
        raise last_exc or MeterlessUnavailableError("Meterless request failed")

    def healthz(self) -> bool:
        """Process-up probe only. Does not decide provider status."""
        try:
            code, _ = self._call("/healthz")
            return 200 <= code < 300
        except MeterlessError:
            return False

    def list_models(self) -> Dict[str, Any]:
        code, payload = self._call("/models")
        if code in (401, 403):
            raise MeterlessAuthError("unauthorized")
        if code != 200 or not isinstance(payload, dict):
            raise MeterlessUnavailableError("offline")
        ids = _extract_model_ids(payload)
        meterless_ids = [i for i in ids if i.startswith("meterless/")]
        if not meterless_ids:
            raise MeterlessUnavailableError("offline")
        return {"status": "online", "models": ids, "raw": payload}

    def status(self) -> Dict[str, Any]:
        """
        GET /v1/models decides:
          401/403 -> unauthorized
          200 with meterless ids -> online
          anything else -> offline
        """
        ok, err = self.config.token_status()
        if not ok:
            return {
                "provider": PROVIDER_ID,
                "name": PROVIDER_NAME,
                "status": "unauthorized",
                "message": err,
                "base_url": self.config.base_url,
                "live": False,
                "models": [],
            }
        try:
            listed = self.list_models()
            return {
                "provider": PROVIDER_ID,
                "name": PROVIDER_NAME,
                "status": "online",
                "message": "Meterless runtime responded with routing modes",
                "base_url": self.config.base_url,
                "live": True,
                "models": listed["models"],
            }
        except MeterlessAuthError as exc:
            return {
                "provider": PROVIDER_ID,
                "name": PROVIDER_NAME,
                "status": "unauthorized",
                "message": str(exc),
                "base_url": self.config.base_url,
                "live": False,
                "models": [],
            }
        except MeterlessError as exc:
            return {
                "provider": PROVIDER_ID,
                "name": PROVIDER_NAME,
                "status": "offline",
                "message": str(exc),
                "base_url": self.config.base_url,
                "live": False,
                "models": [],
            }

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> str:
        if not isinstance(prompt, str):
            raise MeterlessError("Plain text requests must stay a string")
        model_id = model or self.config.default_model or DEFAULT_MODEL
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.2,
        }
        code, body = self._call("/chat/completions", method="POST", payload=payload, chat=True)
        if code in (401, 403):
            raise MeterlessAuthError("unauthorized")
        if code != 200:
            raise MeterlessUnavailableError(f"offline (HTTP {code})")
        text = _message_text(body)
        if not text:
            raise MeterlessError("Empty Meterless chat response")
        return text


def _extract_model_ids(payload: Dict[str, Any]) -> List[str]:
    data = payload.get("data")
    ids: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
            elif isinstance(item, str):
                ids.append(item)
    return ids


def _message_text(body: Any) -> str:
    if not isinstance(body, dict):
        return str(body or "")
    choices = body.get("choices") or []
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    parts.append(str(part["text"]))
            return "".join(parts).strip()
    return str(body.get("text") or "").strip()


def auto_detect(
    token: str,
    transport: Optional[HttpTransport] = None,
    app_id: str = APP_ID,
) -> Optional[str]:
    """Try common Nightshift ports; save the first online or unauthorized hit."""
    probe = transport or HttpTransport()
    for host in DETECT_HOSTS:
        for port in DETECT_PORTS:
            url = f"http://{host}:{port}/v1"
            cfg = MeterlessConfig(base_url=url, token=token or "probe-token", app_id=app_id, timeout_seconds=3, max_retries=1)
            client = MeterlessClient(cfg, transport=probe)
            try:
                snap = client.status()
            except MeterlessError:
                continue
            if snap["status"] in ("online", "unauthorized"):
                return url
    return None


def get_status(config: Optional[Dict[str, Any]] = None, transport: Optional[HttpTransport] = None) -> Dict[str, Any]:
    client = MeterlessClient(MeterlessConfig.from_config_dict(config), transport=transport)
    return client.status()


def chat_completion(
    prompt: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    system_prompt: str = "",
    model: Optional[str] = None,
    transport: Optional[HttpTransport] = None,
) -> str:
    client = MeterlessClient(MeterlessConfig.from_config_dict(config), transport=transport)
    return client.chat(prompt, system_prompt=system_prompt, model=model)


def as_tool_result(status: Dict[str, Any]) -> ToolResult:
    if status.get("status") == "online":
        return ToolResult.success("meterless_status", status.get("message") or "online", data=status)
    return ToolResult.error("meterless_status", status.get("message") or "offline", error=status.get("status"))
