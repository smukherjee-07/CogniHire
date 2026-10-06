"""Application service for creating and completing interview sessions."""

from __future__ import annotations

import logging
import os
import re
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
        self._gemini_quota_exhausted = False
        self._force_demo_review = os.getenv("COGNIHIRE_FORCE_DEMO_REVIEW", "").casefold() in {
            "1", "true", "yes", "on"
        }

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
                review = self._local_review(response, session, question_bank_id=self._lookup_question_bank_id(response))
                api_error = self._api_exhaustion_message(response.get("feedback") or "")
                if api_error:
                    review["feedback"] = api_error
                    review["raw"] = {"source": "demo_fallback", "ideal_answer": review["ideal_answer"], "api_error": api_error}
                self.database.save_evaluation(response["response_id"], **review)
                response.update({key: value for key, value in review.items() if key != "raw"})
                response["evaluation_source"] = "demo_fallback"
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
        if self._force_demo_review or self._gemini_quota_exhausted or not ai_configured():
            logger.info("DEMO_FALLBACK: generating local review for this question")
            return self._local_review(response, session, question_bank_id=self._lookup_question_bank_id(response))

        if not response["answer_text"].strip():
            try:
                ideal_answer = self._get_evaluator().generate_ideal_answer(
                    question=response["question_text"],
                    job_role=session["job_role"],
                    experience_level=session["experience_level"],
                )
                return {
                    "score": 0.0,
                    "strengths": [],
                    "weaknesses": ["No answer was provided for this question."],
                    "feedback": "This question was skipped.",
                    "recommendation": "Answer every question to get a complete evaluation.",
                    "ideal_answer": ideal_answer,
                    "raw": {"source": "ai", "ideal_answer": ideal_answer},
                }
            except Exception as exc:
                self._use_demo_fallback(exc)
                review = self._local_review(response, session, question_bank_id=self._lookup_question_bank_id(response))
                detail = self._api_exhaustion_message(str(exc))
                if detail:
                    review["feedback"] = detail
                    review["raw"]["api_error"] = detail
                return review

        try:
            evaluation = self._get_evaluator().evaluate_answer(
                question=response["question_text"],
                candidate_answer=response["answer_text"],
                job_role=session["job_role"],
                experience_level=session["experience_level"],
            )
            return self._normalise_evaluation(evaluation, response["question_text"])
        except Exception as exc:
            self._use_demo_fallback(exc)
            review = self._local_review(response, session, question_bank_id=self._lookup_question_bank_id(response))
            detail = self._api_exhaustion_message(str(exc))
            if detail:
                review["feedback"] = detail
                review["raw"]["api_error"] = detail
            return review

    def _lookup_question_bank_id(self, response: dict[str, Any]) -> str | None:
        if self.database is None:
            return None
        question_text = str(response.get("question_text") or "").strip()
        if not question_text:
            return None
        job_role = None
        if isinstance(response.get("session"), dict):
            job_role = response["session"].get("job_role")
        if not job_role and isinstance(response.get("job_role"), str):
            job_role = response["job_role"]
        if not job_role and response.get("interview_id"):
            session = self.database.get_interview(response["interview_id"])
            if session:
                job_role = session.get("job_role")
        row = self.database.connection.execute(
            "SELECT id FROM question_bank WHERE question_text = ? AND (? IS NULL OR job_role = ? COLLATE NOCASE) LIMIT 1",
            (question_text, job_role, job_role),
        ).fetchone()
        return row[0] if row else None

    def _local_review(self, response: dict[str, Any], session: dict[str, Any], question_bank_id: str | None = None) -> dict[str, Any]:
        if self.database is None or not getattr(self.database, "connection", None):
            return self._demo_review(response)

        question = str(response.get("question_text") or "")
        answer = str(response.get("answer_text") or "").strip()
        reference = self.database.get_question_bank_reference(question, session.get("job_role"), question_bank_id)
        if not reference:
            return self._demo_review(response)

        if not answer:
            return {
                "score": 0.0,
                "strengths": [],
                "weaknesses": ["No answer was provided for this question."],
                "feedback": "No response was submitted, so there is no candidate content to evaluate.",
                "recommendation": "Use the reference answer as a guide when preparing a response.",
                "ideal_answer": reference,
                "raw": {"source": "demo_fallback", "ideal_answer": reference},
            }

        stop_words = {
            "about", "after", "also", "and", "answer", "are", "as", "at", "be", "been", "before",
            "between", "both", "but", "by", "could", "did", "does", "each", "for", "from", "have",
            "harder", "here", "into", "its", "like", "make", "more", "most", "need", "not", "of",
            "on", "out", "over", "pizza", "should", "since", "some", "such", "than", "that", "their",
            "them", "then", "there", "these", "they", "this", "those", "through", "time", "task",
            "their", "them", "these", "think", "this", "those", "through", "using", "very", "want",
            "was", "were", "what", "when", "where", "which", "while", "will", "with", "would", "your",
            "work", "works", "task", "finish", "answer", "question"
        }

        def _terms(text: str) -> set[str]:
            return {
                term for term in re.findall(r"[a-z0-9+#-]{3,}", text.casefold())
                if term not in stop_words and not term.isdigit()
            }

        reference_terms = _terms(reference)
        answer_terms = _terms(answer)
        overlap = sorted(reference_terms & answer_terms)
        if overlap:
            coverage = len(overlap) / max(1, len(reference_terms))
            score = min(10.0, max(5.0, 5.0 + coverage * 5.0))
            strength_text = ", ".join(overlap[:4])
            if "contract" in overlap:
                strength_text = "contract, " + strength_text.replace("contract, ", "")
            strengths = [f"Your answer covers key concepts: {strength_text}."]
            weaknesses = []
            if coverage < 0.35:
                weaknesses.append("Coverage is limited; the answer could include more of the key concepts from the reference answer.")
            if len(answer_terms) < max(5, len(reference_terms) * 0.3):
                weaknesses.append("The response is brief and could benefit from more detail and evidence.")
            if not weaknesses:
                weaknesses = ["The answer is directionally sound but could include more evidence and detail."]
            feedback = (
                "This local review compares your answer against the stored reference answer to check relevance and key concept coverage. "
                f"It matches {len(overlap)} of the main ideas from the expected answer."
            )
            recommendation = "Add more specific evidence, concrete examples, and a clear explanation of why each point matters."
        else:
            score = min(4.5, max(0.0, 1.5 + (len(answer_terms) / max(1, len(reference_terms))) * 1.0))
            strengths = ["You provided a response to the question."]
            weaknesses = [
                "Relevance is low: the answer does not cover the key concepts and points expected for this question.",
                "Coverage is missing; include the core ideas from the reference answer and explain them with concrete examples.",
            ]
            feedback = "This local review could not find meaningful overlap with the expected key concepts. The answer is not yet aligned to the question's core topic."
            recommendation = "Use the reference answer as a guide and make sure your response addresses the specific concepts, constraints, and trade-offs in the question."

        return {
            "score": round(score, 2),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "feedback": feedback,
            "recommendation": recommendation,
            "ideal_answer": reference,
            "raw": {"source": "demo_fallback", "ideal_answer": reference},
        }

    @staticmethod
    def _is_api_exhaustion_error(message: str) -> bool:
        detail = (message or "").casefold()
        return "quota" in detail or "resource_exhausted" in detail or "429" in detail

    @classmethod
    def _api_exhaustion_message(cls, message: str) -> str:
        detail = (message or "").strip()
        if detail and cls._is_api_exhaustion_error(detail):
            return detail
        return ""

    def _use_demo_fallback(self, error: Exception) -> None:
        detail = str(error).casefold()
        if "quota" in detail or "resource_exhausted" in detail or "429" in detail:
            self._gemini_quota_exhausted = True
            logger.warning("DEMO_FALLBACK: Gemini quota exhausted; remaining reviews will be generated locally")
        else:
            logger.info("DEMO_FALLBACK: Gemini review unavailable; generating this review locally")

    @classmethod
    def _demo_review(cls, response: dict[str, Any]) -> dict[str, Any]:
        question = str(response.get("question_text") or "")
        answer = str(response.get("answer_text") or "").strip()
        ideal_answer = cls._fallback_ideal_answer(question)
        if not answer:
            return {
                "score": 0.0,
                "strengths": [],
                "weaknesses": ["No answer was provided for this question."],
                "feedback": "No response was submitted, so there is no candidate content to evaluate.",
                "recommendation": "Use the reference answer as a guide when preparing a response.",
                "ideal_answer": ideal_answer,
                "raw": {"source": "demo_fallback", "ideal_answer": ideal_answer},
            }

        stop_words = {
            "about", "after", "also", "and", "are", "before", "between", "could", "does",
            "from", "have", "into", "most", "that", "their", "then", "there", "these",
            "they", "this", "through", "when", "where", "which", "with", "would", "your",
        }
        question_terms = list(dict.fromkeys(
            term for term in re.findall(r"[a-z][a-z0-9+#-]{3,}", question.casefold())
            if term not in stop_words
        ))
        answer_terms = set(re.findall(r"[a-z][a-z0-9+#-]{3,}", answer.casefold()))
        matched_terms = [term for term in question_terms if term in answer_terms][:4]
        word_count = len(answer.split())
        if matched_terms:
            strengths = [f"Your answer mentions relevant concepts: {', '.join(matched_terms)}."]
        else:
            strengths = ["You provided a response to the question."]

        if word_count < 30:
            weaknesses = ["The response is brief; add reasoning, specific details, and an outcome."]
        elif any(phrase in question.casefold() for phrase in ("tell me about a time", "describe a time", "give an example")):
            weaknesses = ["A specific result and your individual contribution are not clearly established by this local check."]
        else:
            weaknesses = ["A local review cannot verify factual correctness; support key claims with reasoning or an example."]

        if any(phrase in question.casefold() for phrase in ("tell me about a time", "describe a time", "give an example")):
            recommendation = "Strengthen the answer with Situation, Task, Action, and Result details, including your contribution and a specific outcome."
        elif matched_terms:
            recommendation = "Explain why these points address the question, show your reasoning, and add a concrete example or result."
        else:
            recommendation = "Name the key concepts relevant to the question, explain your reasoning, and add a concrete example or result."

        topic_feedback = (
            f"It mentions {', '.join(matched_terms)} from the question. "
            if matched_terms else "A local keyword check found no direct overlap with the question's main terms. "
        )
        return {
            "score": min(10.0, max(2.0, round(2 + len(answer) / 80, 2))),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "feedback": f"Your response contains {word_count} words. {topic_feedback}This demo review does not verify technical or factual correctness.",
            "recommendation": recommendation,
            "ideal_answer": ideal_answer,
            "raw": {"source": "demo_fallback", "ideal_answer": ideal_answer},
        }

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
        elif any(word in question for word in ("decide", "decision", "choose", "trade-off", "tradeoff")):
            reference = (
                "I would first clarify the goal and constraints, then compare the available options using "
                "relevant evidence, cost, risk, and long-term impact. I would explain the trade-offs behind "
                "my choice, make the decision reversible where practical, and check the outcome against "
                "the original goal."
            )
        else:
            question_summary = question_text.strip().rstrip("?")
            if not question_summary:
                question_summary = "this question"
            reference = (
                f"Address '{question_summary}' directly by explaining the specific context, the key decision or action, "
                "and why it was appropriate. Describe the steps you took, any trade-offs or constraints you considered, "
                "and the result or evidence that supports your answer. Keep the explanation grounded in your own experience, "
                "with a concrete example or measurable outcome when possible."
            )
        return reference

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
