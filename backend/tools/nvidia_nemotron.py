"""
NVIDIA NIM adapter for FPO agricultural reasoning.

Official chat-completions model IDs (NVIDIA NIM LLM APIs):
  - nvidia/nemotron-3.5-bolt-e4b
    https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-bolt-e4b
    https://build.nvidia.com/nvidia/nemotron-3.5-bolt-e4b
  - nvidia/nemotron-3.5-lightning-30b-a3b
    https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b

This adapter is separate from Code Core / recovery (`code_core.call_nemotron`),
which keeps its existing `nvidia_model` default (z-ai/glm-5.3-flash).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NIM_CHAT_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODELS_URL = "https://integrate.api.nvidia.com/v1/models"

# Verified against NVIDIA NIM reference docs — do not invent aliases.
NEMOTRON_BOLT_E4B = "nvidia/nemotron-3.5-bolt-e4b"
NEMOTRON_LIGHTNING_30B_A3B = "nvidia/nemotron-3.5-lightning-30b-a3b"

FPO_NEMOTRON_MODELS: Dict[str, Dict[str, str]] = {
    NEMOTRON_BOLT_E4B: {
        "label": "Nemotron 3.5 Bolt E4B",
        "docs": "https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-bolt-e4b",
        "role": "fast reasoning / tool-calling",
    },
    NEMOTRON_LIGHTNING_30B_A3B: {
        "label": "Nemotron 3.5 Lightning 30B A3B",
        "docs": "https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b",
        "role": "longer agentic FPO analysis",
    },
}

DEFAULT_FPO_MODEL = NEMOTRON_BOLT_E4B
DEFAULT_TIMEOUT_SECONDS = 120


class NvidiaNemotronError(Exception):
    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


class NvidiaAuthError(NvidiaNemotronError):
    def __init__(self, message: str = "unauthorized"):
        super().__init__(message, status="unauthorized")


class NvidiaUnavailableError(NvidiaNemotronError):
    def __init__(self, message: str = "offline"):
        super().__init__(message, status="offline")


class HttpTransport:
    def request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Tuple[int, Any]:
        req = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
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
            raise NvidiaUnavailableError(f"Cannot reach NVIDIA NIM: {exc}") from exc


@dataclass
class NvidiaFpoConfig:
    api_key: str = ""
    model: str = DEFAULT_FPO_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = 2

    @classmethod
    def from_config_dict(cls, config: Optional[Dict[str, Any]] = None) -> "NvidiaFpoConfig":
        cfg = config or {}
        key = (
            str(cfg.get("nvidia_api_key") or "").strip()
            or str(os.environ.get("NVIDIA_API_KEY") or "").strip()
        )
        model = str(cfg.get("nvidia_fpo_model") or DEFAULT_FPO_MODEL).strip()
        if model not in FPO_NEMOTRON_MODELS:
            model = DEFAULT_FPO_MODEL
        return cls(
            api_key=key,
            model=model,
            timeout_seconds=int(cfg.get("nvidia_fpo_timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
            max_retries=int(cfg.get("nvidia_fpo_max_retries") or 2),
        )


class NvidiaNemotronClient:
    def __init__(
        self,
        config: Optional[NvidiaFpoConfig] = None,
        transport: Optional[HttpTransport] = None,
    ):
        self.config = config or NvidiaFpoConfig()
        self.transport = transport or HttpTransport()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def status(self) -> Dict[str, Any]:
        catalog = [
            {
                "id": mid,
                "label": meta["label"],
                "docs": meta["docs"],
                "role": meta["role"],
            }
            for mid, meta in FPO_NEMOTRON_MODELS.items()
        ]
        base = {
            "provider": "nvidia_nim",
            "name": "NVIDIA NIM Nemotron (FPO)",
            "selected_model": self.config.model,
            "models": catalog,
            "live": False,
        }
        if not self.config.api_key:
            return {
                **base,
                "status": "unconfigured",
                "message": "NVIDIA API key is not configured (FPO adapter). Code Core nvidia_model is unchanged.",
            }
        try:
            code, payload = self.transport.request(
                NIM_MODELS_URL,
                method="GET",
                headers=self._headers(),
                timeout=min(self.config.timeout_seconds, 20),
            )
        except NvidiaNemotronError as exc:
            return {**base, "status": "offline", "message": str(exc)}
        if code in (401, 403):
            return {**base, "status": "unauthorized", "message": "NVIDIA NIM rejected the API key"}
        if code != 200:
            return {**base, "status": "offline", "message": f"NVIDIA NIM models probe HTTP {code}"}
        return {
            **base,
            "status": "online",
            "live": True,
            "message": f"NVIDIA NIM reachable; FPO model {self.config.model}",
            "upstream": payload if isinstance(payload, dict) else {},
        }

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> str:
        if not self.config.api_key:
            raise NvidiaAuthError("NVIDIA API key is not configured")
        model_id = model or self.config.model
        if model_id not in FPO_NEMOTRON_MODELS:
            raise NvidiaNemotronError(f"Unsupported FPO Nemotron model: {model_id}")
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 1024,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        last_err: Optional[Exception] = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                code, data = self.transport.request(
                    NIM_CHAT_URL,
                    method="POST",
                    headers=self._headers(),
                    body=body,
                    timeout=self.config.timeout_seconds,
                )
            except NvidiaNemotronError as exc:
                last_err = exc
                if attempt < attempts:
                    time.sleep(min(2 ** (attempt - 1), 4))
                    continue
                raise
            if code in (401, 403):
                raise NvidiaAuthError("unauthorized")
            if code != 200:
                last_err = NvidiaUnavailableError(f"NVIDIA NIM HTTP {code}")
                if attempt < attempts:
                    time.sleep(min(2 ** (attempt - 1), 4))
                    continue
                raise last_err
            text = _choice_text(data)
            if not text:
                raise NvidiaNemotronError("Empty NVIDIA NIM chat response")
            return text
        raise last_err or NvidiaUnavailableError("NVIDIA NIM request failed")


def _choice_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def get_status(config: Optional[Dict[str, Any]] = None, transport: Optional[HttpTransport] = None) -> Dict[str, Any]:
    return NvidiaNemotronClient(NvidiaFpoConfig.from_config_dict(config), transport=transport).status()


def chat_completion(
    prompt: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    system_prompt: str = "",
    model: Optional[str] = None,
    transport: Optional[HttpTransport] = None,
) -> str:
    return NvidiaNemotronClient(
        NvidiaFpoConfig.from_config_dict(config),
        transport=transport,
    ).chat(prompt, system_prompt=system_prompt, model=model)


def list_fpo_models() -> List[Dict[str, str]]:
    return [
        {"id": mid, **meta}
        for mid, meta in FPO_NEMOTRON_MODELS.items()
    ]
