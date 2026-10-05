import pytest

from backend import interview as interview_module
from backend.interview import InterviewService
from database.database import Database


class StubEvaluator:
	def evaluate_answer(self, **_kwargs):
		return {
			"score": 8,
			"strengths": ["Explains the tradeoff clearly."],
			"weaknesses": ["Could quantify the outcome."],
			"feedback": "Good reasoning.",
			"recommendation": "Add a measurable result.",
			"ideal_answer": "I chose the safer design and measured its effect: [specific result].",
		}

	def generate_ideal_answer(self, question, **_kwargs):
		return f"Ideal answer for: {question}"


class FailedEvaluator:
	def evaluate_answer(self, **_kwargs):
		raise ValueError("Gemini request failed")

	def generate_ideal_answer(self, **_kwargs):
		raise ValueError("Gemini request failed")


class QuestionSpecificEvaluator:
	def __init__(self):
		self.calls = []

	def evaluate_answer(self, question, candidate_answer, **_kwargs):
		self.calls.append((question, candidate_answer))
		return {"ideal_answer": f"Question-specific answer for: {question}"}

	def generate_ideal_answer(self, question, **_kwargs):
		self.calls.append((question, ""))
		return f"Question-specific answer for: {question}"


def _response():
	return {
		"answer_text": "I compared the options and selected the safer design.",
		"question_text": "How did you make the decision?",
	}


def test_evaluate_returns_gemini_strengths_and_weaknesses(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = StubEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["strengths"] == ["Explains the tradeoff clearly."]
	assert result["weaknesses"] == ["Could quantify the outcome."]
	assert result["ideal_answer"] == "I chose the safer design and measured its effect: [specific result]."
	assert result["raw"]["source"] == "ai"
	assert result["raw"]["ideal_answer"] == result["ideal_answer"]


def test_skipped_answer_still_gets_a_gemini_ideal_answer(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = StubEvaluator()
	response = {**_response(), "answer_text": ""}

	result = service._evaluate(response, {"job_role": "Engineer", "experience_level": "mid"})

	assert result["score"] == 0
	assert result["ideal_answer"] == "Ideal answer for: How did you make the decision?"
	assert result["raw"]["source"] == "ai"


def test_skipped_answer_gemini_failure_does_not_crash_review(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = FailedEvaluator()
	response = {**_response(), "answer_text": ""}

	result = service._evaluate(response, {"job_role": "Engineer", "experience_level": "mid"})

	assert result["score"] == 0
	assert result["ideal_answer"] == ""
	assert result["raw"]["source"] == "ai_unavailable"
	assert "Gemini evaluation is unavailable" in result["feedback"]


def test_evaluate_returns_truthful_fallback_when_gemini_fails(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = FailedEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["raw"]["source"] == "ai_unavailable"
	assert result["feedback"] == "Gemini evaluation is unavailable: Gemini request failed"
	assert result["recommendation"].startswith("This is a local estimate")


def test_local_evaluation_has_no_invented_strengths_or_weaknesses(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: False)
	service = InterviewService(database=None)

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["strengths"] == []
	assert result["weaknesses"] == []


def test_results_include_suggestions_for_unreached_questions(tmp_path, monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	database = Database(tmp_path / "interview.db")
	database.initialize()
	database.connection.execute("PRAGMA user_version = 0")
	database.initialize()
	user = database.create_user("candidate", "password")
	interview = database.create_interview(user["id"], "Engineer", "technical", question_count=2)
	questions = database.add_questions(interview["id"], ["First question?", "Second question?"])
	database.save_response(interview["id"], questions[0]["id"], "My answer.")
	service = InterviewService(database)
	service._evaluator = StubEvaluator()

	try:
		result = service.results(interview["id"])
		summary = database.list_interview_summaries(user["id"])[0]
	finally:
		database.close()

	assert len(result["responses"]) == 2
	assert all(response["ideal_answer"] for response in result["responses"])
	assert result["questions_answered"] == 1
	assert summary["responses_submitted"] == 1


def test_all_blank_answers_get_individual_question_specific_ideal_answers(tmp_path, monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	database = Database(tmp_path / "all-blank.db")
	database.initialize()
	user = database.create_user("candidate", "password")
	interview = database.create_interview(user["id"], "Engineer", "technical", question_count=3)
	questions = database.add_questions(interview["id"], ["Question alpha?", "Question beta?", "Question gamma?"])
	evaluator = QuestionSpecificEvaluator()
	service = InterviewService(database)
	service._evaluator = evaluator

	try:
		result = service.results(interview["id"])
	finally:
		database.close()

	assert evaluator.calls == [(question["question_text"], "") for question in questions]
	assert [response["answer_text"] for response in result["responses"]] == ["", "", ""]
	assert [response["ideal_answer"] for response in result["responses"]] == [
		f"Question-specific answer for: {question['question_text']}" for question in questions
	]


def test_results_survive_gemini_failure_and_leave_evaluation_retryable(tmp_path, monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	database = Database(tmp_path / "retryable.db")
	database.initialize()
	user = database.create_user("candidate", "password")
	interview = database.create_interview(user["id"], "Engineer", "technical", question_count=1)
	question = database.add_questions(interview["id"], ["Explain your approach?"])[0]
	database.save_response(interview["id"], question["id"], "I compare several approaches before choosing.")
	service = InterviewService(database)
	service._evaluator = FailedEvaluator()

	try:
		result = service.results(interview["id"])
		stored_response = database.list_responses(interview["id"])[0]
	finally:
		database.close()

	assert result["responses"][0]["evaluation_source"] == "ai_unavailable"
	assert "Gemini evaluation is unavailable" in result["responses"][0]["feedback"]
	assert stored_response["evaluation_id"] is None
