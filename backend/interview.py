"""Application service for creating and completing interview sessions."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from ai.api import AIServiceClient
from ai.evaluator import AnswerEvaluator
from ai.presence import PresenceEvaluator
from ai.question_generator import QuestionGenerator
from backend.question_bank import pick_questions
from database.database import Database

logger = logging.getLogger(__name__)

# Last resort, only used if the question_bank table is empty.
FALLBACK_QUESTIONS = (
    "What interests you most about working as a {role}?",
    "Describe a challenging problem you solved and how you approached it.",
    "How do you check the quality of your work before delivering it?",
    "Tell me about a time you received difficult feedback and acted on it.",
    "What would you focus on during your first 30 days as a {role}?",
)

_RESULT_LOCKS: dict[str, threading.Lock] = {}
_RESULT_LOCKS_GUARD = threading.Lock()


def _result_lock(session_id: str) -> threading.Lock:
    with _RESULT_LOCKS_GUARD:
        return _RESULT_LOCKS.setdefault(session_id, threading.Lock())


def ai_configured() -> bool:
    return bool(os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY"))


class InterviewService:
    """Coordinates persistence, optional AI, and deterministic local behavior."""

    def __init__(self, database: Database):
        self.database = database
        self._question_generator: QuestionGenerator | None = None
        self._evaluator: AnswerEvaluator | None = None
        self._presence_evaluator: PresenceEvaluator | None = None

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
        if not self.database.get_user(user_id):
            raise ValueError("Unknown user_id")

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
        skipped: bool = False,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        question = self.database.get_question(session_id, question_id)
        if not question:
            raise ValueError("Question does not belong to this interview session")
        if session["status"] != "in_progress":
            raise ValueError("Interview session is already completed")
        if answer_mode not in {"text", "audio", "video", "audio_video"}:
            raise ValueError("Unsupported answer mode")
        # skipped=True (the web client's "nothing was captured for this question" signal) is the
        # one case where an empty answer with no media is allowed through instead of rejected.
        if not skipped and not answer_text.strip() and not (audio_file_path or video_file_path):
            raise ValueError("Answer text or media is required")
        # Idempotent: the web client re-sends the last answer when it ends the interview.
        return self.database.save_response(
            interview_id=session_id,
            question_id=question_id,
            answer_text=answer_text.strip(),
            answer_mode=answer_mode,
            audio_file_path=audio_file_path,
            video_file_path=video_file_path,
        )

    def results(self, session_id: str) -> dict[str, Any]:
        with _result_lock(session_id):
            return self._load_results(session_id)

    def _load_results(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        self.database.ensure_empty_responses(session_id)
        pending = [r for r in self.database.list_responses(session_id) if r["evaluation_id"] is None]
        for response, evaluation in zip(pending, self._evaluate_many(pending, session)):
            self.database.save_evaluation(response["id"], **evaluation)
        if session["status"] == "in_progress":
            self.database.complete_interview(session_id)
        result = self.database.get_results(session_id)
        for response in result["responses"]:
            if response["evaluation_source"] == "ai_unavailable":
                response["feedback"] = self._evaluation_failure_message(
                    ValueError(response["feedback"] or "")
                )
                if (response["answer_text"] or "").strip():
                    response["recommendation"] = (
                        "Compare your response with the reference answer above; "
                        "AI-generated improvement feedback is unavailable."
                    )
            if not response["ideal_answer"]:
                response["ideal_answer"] = self._fallback_ideal_answer(response["question_text"])
        scores = [response["score"] for response in result["responses"] if response["score"] is not None]
        result["score"] = round(sum(scores) / len(scores), 2) if scores else 0
        return result

    def evaluate_presence(self, session_id: str, image_mime_type: str, image_data: str) -> dict[str, str]:
        session = self._require_session(session_id)
        if not ai_configured():
            raise RuntimeError("Gemini is not configured; attire could not be assessed.")
        if self._presence_evaluator is None:
            self._presence_evaluator = PresenceEvaluator()
        try:
            return self._presence_evaluator.evaluate_attire(
                image_mime_type=image_mime_type,
                image_data=image_data,
                job_role=session["job_role"],
            )
        except (ValueError, KeyError, TypeError) as exc:
            logger.exception("AI attire evaluation failed")
            raise RuntimeError(f"AI attire evaluation failed: {exc}") from exc

    def _build_questions(
        self,
        job_role: str,
        interview_type: str,
        experience_level: str,
        question_count: int,
        focus_areas: list[str] | None,
    ) -> tuple[list[str], str]:
        """AI first; then the 750-question bank; then a tiny built-in list."""
        if ai_configured():
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
                logger.warning("AI returned %d of %d questions; using the question bank", len(questions), question_count)
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("AI question generation failed (%s); using the question bank", exc)

        questions = pick_questions(self.database, job_role, interview_type, question_count)
        if len(questions) >= question_count:
            return questions, "bank"

        for template in FALLBACK_QUESTIONS:
            question = template.format(role=job_role)
            if len(questions) < question_count and question not in questions:
                questions.append(question)
        while len(questions) < question_count:
            questions.append(
                f"Describe a project or decision that demonstrates your readiness for {job_role}."
            )
        return questions, "local"

    def _evaluate_many(self, responses: list[dict[str, Any]], session: dict[str, Any]) -> list[dict[str, Any]]:
        """Evaluate in question order to keep Gemini request volume controlled."""
        return [self._evaluate(response, session) for response in responses]

    def _get_evaluator(self) -> AnswerEvaluator:
        if self._evaluator is None:
            self._evaluator = AnswerEvaluator(client=AIServiceClient(max_retries=0))
        return self._evaluator

    def _evaluate(self, response: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        if not response["answer_text"].strip():
            ideal_answer = ""
            source = "skipped"
            if ai_configured():
                try:
                    ideal_answer = self._get_evaluator().generate_ideal_answer(
                        question=response["question_text"],
                        job_role=session["job_role"],
                        experience_level=session["experience_level"],
                    )
                    source = "ai"
                except Exception as exc:
                    logger.exception("AI evaluation failed for skipped answer")
                    return {
                        "score": 0.0,
                        "strengths": [],
                        "weaknesses": ["No answer was provided for this question."],
                        "feedback": self._evaluation_failure_message(exc),
                        "recommendation": "Detailed evaluation is unavailable for this unanswered question.",
                        "ideal_answer": self._fallback_ideal_answer(response["question_text"]),
                        "raw": {"source": "ai_unavailable"},
                    }
            return {
                "score": 0.0,
                "strengths": [],
                "weaknesses": ["No answer was provided for this question."],
                "feedback": "This question was skipped.",
                "recommendation": "Answer every question to get a complete evaluation.",
                "ideal_answer": ideal_answer,
                "raw": {"source": source, "ideal_answer": ideal_answer},
            }

        if ai_configured():
            try:
                evaluation = self._get_evaluator().evaluate_answer(
                    question=response["question_text"],
                    candidate_answer=response["answer_text"],
                    job_role=session["job_role"],
                    experience_level=session["experience_level"],
                )
                return self._normalise_evaluation(evaluation, response["question_text"])
            except Exception as exc:
                logger.exception("AI evaluation failed")
                return {
                    **self._local_evaluation(response["answer_text"], response["question_text"]),
                    "feedback": self._evaluation_failure_message(exc),
                    "recommendation": "Compare your response with the reference answer above; AI-generated improvement feedback is unavailable.",
                    "raw": {"source": "ai_unavailable"},
                }

        return self._local_evaluation(response["answer_text"], response["question_text"])

    @staticmethod
    def _fallback_ideal_answer(question_text: str) -> str:
        question = question_text.casefold()
        if "refactor" in question and "rewrite" in question:
            reference = (
                "I would refactor when the system is still understandable and the problem is localized, "
                "because that lets me improve it incrementally while preserving working behavior. I would "
                "consider a rewrite when the architecture consistently blocks important requirements and "
                "incremental changes are no longer practical. Before choosing, I would compare delivery "
                "cost, risk, maintainability, and business needs, then validate the decision with tests and "
                "a staged rollout."
            )
        elif any(phrase in question for phrase in ("tell me about a time", "describe a time", "give an example")):
            reference = (
                "Use a truthful STAR example: describe the Situation and your Task, explain the specific "
                "Actions you took and why, then share the Result and what you learned. Replace each part "
                "with details from your own experience."
            )
        elif any(word in question for word in ("decide", "choose", "trade-off", "tradeoff")):
            reference = (
                "I would first clarify the goal and constraints, then compare the available options using "
                "relevant evidence, cost, risk, and long-term impact. I would explain the trade-offs behind "
                "my choice, make the decision reversible where practical, and check the outcome against "
                "the original goal."
            )
        else:
            reference = (
                "Start with a direct answer to the question. Explain the key idea or steps and why they fit, "
                "mention important constraints or trade-offs, and support the answer with a relevant example "
                "or evidence. Keep personal details truthful and specific to your experience."
            )
        return f"Offline reference (not AI-generated): {reference}"

    @staticmethod
    def _evaluation_failure_message(error: Exception) -> str:
        detail = str(error).casefold()
        if "quota" in detail or "resource_exhausted" in detail or "429" in detail:
            return "Gemini's request quota is currently exhausted. Detailed AI evaluation is unavailable; the reference answer is still shown."
        return "Gemini evaluation is unavailable right now. The reference answer is still shown."

    @classmethod
    def _local_evaluation(cls, answer_text: str, question_text: str = "") -> dict[str, Any]:
        answer_length = len(answer_text.strip())
        score = min(10.0, max(2.0, round(2 + answer_length / 80, 2)))
        return {
            "score": score,
            "strengths": [],
            "weaknesses": [],
            "feedback": "",
            "recommendation": "",
            "ideal_answer": cls._fallback_ideal_answer(question_text) if question_text else "",
            "raw": {"source": "local"},
        }

    @classmethod
    def _normalise_evaluation(cls, evaluation: dict[str, Any], question_text: str = "") -> dict[str, Any]:
        ideal_answer = str(evaluation.get("ideal_answer") or "")
        return {
            "score": min(10.0, max(0.0, float(evaluation.get("score", 0)))),
            "strengths": evaluation.get("strengths") or [],
            "weaknesses": evaluation.get("weaknesses") or [],
            "feedback": str(evaluation.get("feedback") or ""),
            "recommendation": str(evaluation.get("recommendation") or ""),
            "ideal_answer": ideal_answer or (cls._fallback_ideal_answer(question_text) if question_text else ""),
            "raw": {"source": "ai", **evaluation},
        }

    def _require_session(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_interview(session_id)
        if not session:
            raise ValueError("Interview session not found")
        return session


__all__ = ["InterviewService", "ai_configured"]
