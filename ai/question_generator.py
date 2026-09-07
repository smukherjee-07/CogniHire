"""Utilities for generating interview questions from the AI backend."""

from __future__ import annotations

from typing import Any

from ai.api import AIServiceClient
from ai.prompts import build_question_generation_prompt


class QuestionGenerator:
    """Wrap the AI API to generate interview-ready questions."""

    def __init__(self, client: AIServiceClient | None = None):
        self.client = client or AIServiceClient()

    def generate_questions(
        self,
        job_role: str,
        experience_level: str = "mid",
        focus_areas: list[str] | None = None,
        interview_type: str = "technical",
        count: int = 5,
    ) -> list[str]:
        """Generate a list of job-specific interview questions."""
        prompt = build_question_generation_prompt(
            job_role=job_role,
            experience_level=experience_level,
            focus_areas=focus_areas,
            interview_type=interview_type,
            count=count,
        )

        response = self.client.generate(prompt)
        payload = response.get("data") if isinstance(response, dict) else None

        if isinstance(payload, dict):
            questions = payload.get("questions") or payload.get("items") or []
            if isinstance(questions, list):
                return [str(item).strip() for item in questions if str(item).strip()]

        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]

        raise ValueError("AI response did not contain a valid question list.")

    def generate_question_bank(
        self,
        job_role: str,
        experience_level: str = "mid",
        focus_areas: list[str] | None = None,
        interview_type: str = "technical",
        count: int = 5,
    ) -> list[str]:
        """Alias for generate_questions."""
        return self.generate_questions(
            job_role=job_role,
            experience_level=experience_level,
            focus_areas=focus_areas,
            interview_type=interview_type,
            count=count,
        )


__all__ = ["QuestionGenerator"]
