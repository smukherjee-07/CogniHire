"""AI integration client handling upstream model communication via REST API."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Get API key
AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")

# ✅ Use Gemini 3.8 Flash by default
AI_MODEL = os.getenv("AI_MODEL", "gemini-3.8-flash")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///cognihire.db")


class AIServiceClient:
    def __init__(self, api_key: str | None = AI_API_KEY, model_name: str = AI_MODEL):
        self.api_key = api_key
        self.model_name = model_name

        if not self.api_key:
            raise ValueError(
                "AI_API_KEY is not configured. Set AI_API_KEY or GEMINI_API_KEY in your environment."
            )

        # API URL
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

    def generate(self, prompt: str) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",  # ask for JSON output
            },
        }

        try:
            print(f"Using model: {self.model_name}")  # ✅ debug check

            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=30,
            )

            response.raise_for_status()
            res_json = response.json()

            # Extract text safely
            raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]

            # ✅ Safe JSON parsing (important for Gemini 3)
            try:
                data = json.loads(raw_text.strip())
            except json.JSONDecodeError:
                data = {"raw_response": raw_text}

            return {
                "success": True,
                "error": False,
                "error_message": "",
                "timestamp": timestamp,
                "model_used": self.model_name,
                "data": data,
            }

        except requests.exceptions.RequestException as req_err:
            return {
                "success": False,
                "error": True,
                "error_message": f"Request error: {str(req_err)}",
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