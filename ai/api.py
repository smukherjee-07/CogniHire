"""AI integration client handling upstream model communication via REST API."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# gemini-1.5-flash (the old default) has been shut down by Google; override with AI_MODEL in .env.
DEFAULT_MODEL = "gemini-3.8-flash"
_RETRY_STATUS = {429, 500, 502, 503, 504}
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _env_number(name: str, default: float, cast=float):
    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class AIServiceClient:
    """Thin wrapper around the Gemini ``generateContent`` REST endpoint (JSON-only replies)."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        # Resolved at construction time (not import time) so .env / test overrides are honoured.
        self.api_key = api_key or os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name or os.getenv("AI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout if timeout is not None else _env_number("AI_TIMEOUT_SECONDS", 30.0)
        self.max_retries = (
            max_retries if max_retries is not None else _env_number("AI_MAX_RETRIES", 2, int)
        )
        if not self.api_key:
            raise ValueError(
                "AI_API_KEY is not configured. Set AI_API_KEY or GEMINI_API_KEY in your environment."
            )
        # The key travels in a header, never in the URL, so it cannot leak into logs or error text.
        self.url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent"
        )

    def generate(self, prompt: str) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7,
            },
        }

        try:
            response = self._post(headers, payload)
            if response.status_code >= 400:
                raise RuntimeError(self._describe_http_error(response))
            data = self._extract_json(response.json())
            return {
                "success": True,
                "error": False,
                "error_message": "",
                "timestamp": timestamp,
                "model_used": self.model_name,
                "data": data,
            }
        except requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "error": True,
                "error_message": f"Request error: {exc}",
                "timestamp": timestamp,
                "data": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": True,
                "error_message": str(exc),
                "timestamp": timestamp,
                "data": None,
            }

    def _post(self, headers: dict, payload: dict) -> requests.Response:
        """POST with a small retry loop for rate limits, 5xx errors and dropped connections."""
        attempt = 0
        while True:
            try:
                response = requests.post(self.url, headers=headers, json=payload, timeout=self.timeout)
            except requests.ConnectionError:
                if attempt >= self.max_retries:
                    raise
            else:
                if response.status_code not in _RETRY_STATUS or attempt >= self.max_retries:
                    return response
            attempt += 1
            time.sleep(min(2 ** (attempt - 1), 4))

    @staticmethod
    def _describe_http_error(response: requests.Response) -> str:
        try:
            message = response.json()["error"]["message"]
        except Exception:
            message = (response.text or "").strip()[:200]
        return f"HTTP {response.status_code}: {message or 'request failed'}"

    @staticmethod
    def _extract_json(body: dict[str, Any]) -> Any:
        candidates = body.get("candidates") or []
        if not candidates:
            reason = (body.get("promptFeedback") or {}).get("blockReason", "no candidates returned")
            raise ValueError(f"Model returned no answer ({reason})")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        # Skip "thought" parts that reasoning models may emit before the real answer.
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        cleaned = _CODE_FENCE.sub("", text.strip())
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Surface what the model actually sent instead of masking it as a fake "success".
            raise ValueError(f"Model reply was not valid JSON: {text[:200]!r}") from exc
