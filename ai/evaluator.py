"""Evaluation utilities for scoring interview answers using the AI backend."""

from __future__ import annotations

from typing import Any

from ai.api import AIServiceClient
from ai.prompts import build_answer_evaluation_prompt, build_ideal_answer_prompt


class AnswerEvaluator:
    """Scores a candidate answer against a role-specific rubric."""

    def __init__(self, client: AIServiceClient | None = None):
        self.client = client or AIServiceClient()

    def evaluate_answer(
        self,
        question: str,
        candidate_answer: str,
        job_role: str,
        experience_level: str = "mid",
        skills: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a structured evaluation payload for a candidate response."""
        prompt = build_answer_evaluation_prompt(
            question=question,
            candidate_answer=candidate_answer,
            job_role=job_role,
            experience_level=experience_level,
            skills=skills,
        )

        response = self.client.generate(prompt)
        payload = response.get("data") if isinstance(response, dict) else None

        if isinstance(payload, dict):
            return {
                "score": payload.get("score", 0),
                "strengths": payload.get("strengths", []),
                "weaknesses": payload.get("weaknesses", []),
                "feedback": payload.get("feedback", ""),
                "recommendation": payload.get("recommendation", ""),
                "ideal_answer": payload.get("ideal_answer") or payload.get("suggested_answer", ""),
            }

        detail = response.get("error_message") if isinstance(response, dict) else ""
        raise ValueError(detail or "AI response did not contain a valid evaluation payload.")

    def generate_ideal_answer(
        self,
        question: str,
        job_role: str,
        experience_level: str = "mid",
    ) -> str:
        """Generate an ideal answer without relying on a candidate response."""
        response = self.client.generate(
            build_ideal_answer_prompt(question, job_role, experience_level)
        )
        payload = response.get("data") if isinstance(response, dict) else None
        if isinstance(payload, dict) and isinstance(payload.get("ideal_answer"), str):
            answer = payload["ideal_answer"].strip()
            if answer:
                return answer
        detail = response.get("error_message") if isinstance(response, dict) else ""
        raise ValueError(detail or "AI response did not contain a valid ideal answer.")


__all__ = ["AnswerEvaluator"]
