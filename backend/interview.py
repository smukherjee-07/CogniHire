"""Application service for creating and completing interview sessions."""

from __future__ import annotations

import os
from typing import Any

from ai.evaluator import AnswerEvaluator
from ai.question_generator import QuestionGenerator
from database.database import Database


FALLBACK_QUESTIONS = (
    "What interests you most about working in this role?",
    "Describe a challenging problem you solved and how you approached it.",
    "How do you check the quality of your work before delivering it?",
    "Tell me about a time you received difficult feedback and acted on it.",
    "What would you focus on during your first 30 days in this role?",
)


class InterviewService:
    """Coordinates persistence, optional AI, and deterministic local behavior."""

    def __init__(self, database: Database):
        self.database = database
        self._question_generator: QuestionGenerator | None = None
        self._evaluator: AnswerEvaluator | None = None

    def start(
        self,
        user_id: str,
        job_role: str,
        interview_type: str = "technical",
        question_count: int = 5,
        experience_level: str = "mid",
        focus_areas: list[str] | None = None,
    ) -> dict[str, Any]:
        job_role = job_role.strip()
        interview_type = interview_type.strip() or "technical"
        experience_level = experience_level.strip() or "mid"
        if not job_role:
            raise ValueError("Job role is required")
        if not 1 <= question_count <= 20:
            raise ValueError("Question count must be between 1 and 20")

        interview = self.database.create_interview(
            user_id=user_id,
            job_role=job_role,
            interview_type=interview_type,
            question_count=question_count,
            experience_level=experience_level,
        )
        questions, source = self._build_questions(
            job_role, interview_type, experience_level, question_count, focus_areas
        )
        stored_questions = self.database.add_questions(interview["id"], questions, source=source)
        return {"session_id": interview["id"], "interview": interview, "questions": stored_questions}

    def next_question(self, session_id: str) -> dict[str, Any] | None:
        self._require_session(session_id)
        return self.database.next_question(session_id)

    def submit_response(
        self,
        session_id: str,
        question_id: str,
        answer_text: str = "",
        answer_mode: str = "text",
        audio_file_path: str | None = None,
        video_file_path: str | None = None,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        question = self.database.get_question(session_id, question_id)
        if not question:
            raise ValueError("Question does not belong to this interview session")
        if session["status"] != "in_progress":
            raise ValueError("Interview session is already completed")
        if answer_mode not in {"text", "audio", "video", "audio_video"}:
            raise ValueError("Unsupported answer mode")
        if not answer_text.strip() and not (audio_file_path or video_file_path):
            raise ValueError("Answer text or media is required")
        return self.database.save_response(
            interview_id=session_id,
            question_id=question_id,
            answer_text=answer_text.strip(),
            answer_mode=answer_mode,
            audio_file_path=audio_file_path,
            video_file_path=video_file_path,
        )

    def results(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        responses = self.database.list_responses(session_id)
        for response in responses:
            if response["evaluation_id"] is None:
                evaluation = self._evaluate(response, session)
                self.database.save_evaluation(response["id"], **evaluation)

        result = self.database.get_results(session_id)
        if session["status"] == "in_progress":
            self.database.complete_interview(session_id)
            result = self.database.get_results(session_id)
        return result

    def _build_questions(
        self,
        job_role: str,
        interview_type: str,
        experience_level: str,
        question_count: int,
        focus_areas: list[str] | None,
    ) -> tuple[list[str], str]:
        if os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY"):
            try:
                if self._question_generator is None:
                    self._question_generator = QuestionGenerator()
                questions = self._question_generator.generate_questions(
                    job_role=job_role,
                    experience_level=experience_level,
                    focus_areas=focus_areas,
                    interview_type=interview_type,
                    count=question_count,
                )
                if len(questions) >= question_count:
                    return questions[:question_count], "ai"
            except (ValueError, KeyError, TypeError):
                pass

        questions = [
            f"{question} for a {job_role} candidate."
            if "role" in question.lower()
            else question
            for question in FALLBACK_QUESTIONS
        ]
        while len(questions) < question_count:
            questions.append(
                f"Describe a project or decision that demonstrates your readiness for {job_role}."
            )
        return questions[:question_count], "local"

    def _evaluate(self, response: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        if response["answer_text"].strip() and (os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")):
            try:
                if self._evaluator is None:
                    self._evaluator = AnswerEvaluator()
                evaluation = self._evaluator.evaluate_answer(
                    question=response["question_text"],
                    candidate_answer=response["answer_text"],
                    job_role=session["job_role"],
                    experience_level=session["experience_level"],
                )
                return self._normalise_evaluation(evaluation)
            except (ValueError, KeyError, TypeError):
                pass

        answer_length = len(response["answer_text"].strip())
        score = min(10.0, max(2.0, round(2 + answer_length / 80, 2)))
        return {
            "score": score,
            "strengths": ["Response was captured successfully."],
            "weaknesses": ["Add more specific examples and measurable outcomes."],
            "feedback": "Use a clear situation, action, and result structure in your answer.",
            "recommendation": "Expand the answer with one concrete example.",
            "raw": {"source": "local"},
        }

    @staticmethod
    def _normalise_evaluation(evaluation: dict[str, Any]) -> dict[str, Any]:
        return {
            "score": min(10.0, max(0.0, float(evaluation.get("score", 0)))),
            "strengths": evaluation.get("strengths") or [],
            "weaknesses": evaluation.get("weaknesses") or [],
            "feedback": str(evaluation.get("feedback") or ""),
            "recommendation": str(evaluation.get("recommendation") or ""),
            "raw": evaluation,
        }

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_interview(session_id)
        if not session:
            raise ValueError("Interview session not found")
        return session


__all__ = ["InterviewService"]
