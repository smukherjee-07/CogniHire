"""AI integration client handling upstream model communication via REST API."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "gemini-1.5-flash")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///cognihire.db")


class AIServiceClient:
    def __init__(self, api_key: str | None = AI_API_KEY, model_name: str = AI_MODEL):
        self.api_key = api_key
        self.model_name = model_name
        if not self.api_key:
            raise ValueError(
                "AI_API_KEY is not configured. Set AI_API_KEY or GEMINI_API_KEY in your environment."
            )
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

    def generate(self, prompt: str) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.7,
            },
        }

        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            res_json = response.json()
            raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(raw_text.strip())

            return {
                "success": True,
                "error": False,
                "error_message": "",
                "timestamp": timestamp,
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
