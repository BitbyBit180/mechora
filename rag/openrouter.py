"""Minimal OpenRouter HTTP client shared by embeddings and generation."""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterError(RuntimeError):
    """A controlled OpenRouter request failure."""


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
        timeout: float | None = None,
        opener: Callable[..., Any] | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = (base_url or os.getenv("OPENROUTER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.http_referer = http_referer or os.getenv("OPENROUTER_HTTP_REFERER")
        self.app_title = app_title or os.getenv("OPENROUTER_APP_TITLE", "Manufacturing Manual Assistant")
        self.timeout = timeout or float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "60"))
        self.opener = opener or urlopen

    def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured.")
        request = Request(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                **({"HTTP-Referer": self.http_referer} if self.http_referer else {}),
                **({"X-Title": self.app_title} if self.app_title else {}),
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                raise OpenRouterError(
                    "OpenRouter rejected the API key (401). Create a new key at "
                    "https://openrouter.ai/keys and replace OPENROUTER_API_KEY in .env."
                ) from exc
            raise OpenRouterError(f"OpenRouter HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise OpenRouterError(f"OpenRouter connection failed: {exc.reason}") from exc
        except OSError as exc:
            raise OpenRouterError(f"OpenRouter connection failed: {exc}") from exc

        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise OpenRouterError("OpenRouter returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise OpenRouterError("OpenRouter returned an invalid response object.")
        if result.get("error"):
            raise OpenRouterError(f"OpenRouter error: {result['error']}")
        return result
