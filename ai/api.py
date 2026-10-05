"""AI integration client handling upstream model communication via Gemini SDK."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# gemini-1.5-flash (the old default) has been shut down by Google; override with AI_MODEL in .env.
DEFAULT_MODEL = "gemini-3.8-flash"
_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _env_number(name: str, default: float, cast=float):
    try:
        return cast(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class AIServiceClient:
    """Thin wrapper around Google GenAI (JSON-only replies)."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        # Resolved at construction time (not import time) so .env / test overrides are honoured.
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY")
        self.model_name = model_name or os.getenv("AI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout if timeout is not None else _env_number("AI_TIMEOUT_SECONDS", 30.0)
        self.max_retries = (
            max_retries if max_retries is not None else _env_number("AI_MAX_RETRIES", 2, int)
        )
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in your environment."
            )
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=int(self.timeout * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=self.max_retries + 1,
                    http_status_codes=[408, 500, 502, 503, 504],
                ),
            ),
        )

    def generate(self, prompt: str, image: tuple[str, str] | None = None) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        parts = [types.Part(text=prompt)]
        if image:
            mime_type, image_data = image
            parts.append(types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type))

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=types.Content(role="user", parts=parts),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            data = self._extract_json(response.text or "")
            return {
                "success": True,
                "error": False,
                "error_message": "",
                "timestamp": timestamp,
                "model_used": self.model_name,
                "data": data,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": True,
                "error_message": str(exc),
                "timestamp": timestamp,
                "data": None,
            }

    @staticmethod
    def _extract_json(text: str) -> Any:
        cleaned = _CODE_FENCE.sub("", text.strip())
        if not cleaned:
            raise ValueError("Model returned no answer")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Surface what the model actually sent instead of masking it as a fake "success".
            raise ValueError(f"Model reply was not valid JSON: {text[:200]!r}") from exc
