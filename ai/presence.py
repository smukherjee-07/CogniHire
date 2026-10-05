"""Image-grounded professional attire feedback using the configured AI client."""

from __future__ import annotations

from typing import Any

from ai.api import AIServiceClient
from ai.prompts import build_attire_evaluation_prompt


class PresenceEvaluator:
    """Assesses visible interview attire without inferring personal traits."""

    def __init__(self, client: AIServiceClient | None = None):
        self.client = client or AIServiceClient()

    def evaluate_attire(self, image_mime_type: str, image_data: str, job_role: str) -> dict[str, Any]:
        response = self.client.generate(
            build_attire_evaluation_prompt(job_role),
            image=(image_mime_type, image_data),
        )
        payload = response.get("data") if isinstance(response, dict) else None
        if isinstance(payload, dict) and isinstance(payload.get("feedback"), str):
            return {"feedback": payload["feedback"].strip()}
        detail = response.get("error_message") if isinstance(response, dict) else ""
        raise ValueError(detail or "AI response did not contain valid attire feedback.")


__all__ = ["PresenceEvaluator"]