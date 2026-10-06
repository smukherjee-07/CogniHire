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
	def __init__(self):
		self.calls = 0

	def evaluate_answer(self, **_kwargs):
		self.calls += 1
		raise ValueError("Gemini request failed")

	def generate_ideal_answer(self, **_kwargs):
		self.calls += 1
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
	assert "Offline reference (not AI-generated)" in result["ideal_answer"]
	assert result["raw"]["source"] == "ai_unavailable"
	assert "Gemini evaluation is unavailable" in result["feedback"]


def test_evaluate_returns_truthful_fallback_when_gemini_fails(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = FailedEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["raw"]["source"] == "ai_unavailable"
	assert result["feedback"] == "Gemini evaluation is unavailable right now. The reference answer is still shown."
	assert result["recommendation"].startswith("Compare your response with the reference answer")
	assert "Offline reference (not AI-generated)" in result["ideal_answer"]
	assert "Gemini request failed" not in result["feedback"]


def test_quota_error_is_sanitized_for_the_review():
	message = InterviewService._evaluation_failure_message(
		ValueError("429 RESOURCE_EXHAUSTED: quota exceeded; internal provider details")
	)

	assert "quota is currently exhausted" in message
	assert "internal provider details" not in message


def test_refactor_rewrite_fallback_ideal_answer_is_question_specific():
	answer = InterviewService._fallback_ideal_answer(
		"How do you decide when to refactor versus rewrite code?"
	)

	assert "Offline reference (not AI-generated)" in answer
	assert "incrementally" in answer
	assert "delivery cost, risk, maintainability" in answer


def test_results_fill_missing_ideal_answer_on_existing_saved_evaluation(tmp_path, monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	database = Database(tmp_path / "saved-without-ideal.db")
	database.initialize()
	user = database.create_user("candidate", "password")
	interview = database.create_interview(user["id"], "Engineer", "technical", question_count=1)
	question = database.add_questions(
		interview["id"], ["How do you decide when to refactor versus rewrite code?"]
	)[0]
	response = database.save_response(interview["id"], question["id"], "I compare the options.")
	database.save_evaluation(
		response["id"],
		score=0,
		feedback="Gemini evaluation is unavailable: 429 RESOURCE_EXHAUSTED quota exceeded; provider details",
		raw={"source": "ai_unavailable"},
	)
	service = InterviewService(database)
	service._evaluator = FailedEvaluator()

	try:
		result = service.results(interview["id"])
	finally:
		database.close()

	assert "Offline reference (not AI-generated)" in result["responses"][0]["ideal_answer"]
	assert "refactor" in result["responses"][0]["ideal_answer"]
	assert "quota is currently exhausted" in result["responses"][0]["feedback"]
	assert "provider details" not in result["responses"][0]["feedback"]
	assert result["responses"][0]["recommendation"].startswith("Compare your response")
	assert service._evaluator.calls == 0


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


@pytest.mark.parametrize("question_count", [3, 5, 10])
def test_results_review_every_question_with_its_own_answer(tmp_path, monkeypatch, question_count):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	database = Database(tmp_path / f"review-{question_count}.db")
	database.initialize()
	user = database.create_user("candidate", "password")
	interview = database.create_interview(user["id"], "Engineer", "technical", question_count=question_count)
	questions = database.add_questions(
		interview["id"], [f"Question {number}?" for number in range(1, question_count + 1)]
	)
	answers = [f"Answer {number}" for number in range(1, question_count + 1)]
	for question, answer in zip(questions, answers):
		database.save_response(interview["id"], question["id"], answer)
	evaluator = QuestionSpecificEvaluator()
	service = InterviewService(database)
	service._evaluator = evaluator

	try:
		result = service.results(interview["id"])
	finally:
		database.close()

	assert len(result["responses"]) == question_count
	assert [(row["question_text"], row["answer_text"]) for row in result["responses"]] == [
		(question["question_text"], answer) for question, answer in zip(questions, answers)
	]
	assert evaluator.calls == [
		(question["question_text"], answer) for question, answer in zip(questions, answers)
	]
	assert all(row["ideal_answer"] and row["score"] is not None for row in result["responses"])


def test_results_persist_gemini_failure_without_repeating_request(tmp_path, monkeypatch):
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
		second_result = service.results(interview["id"])
		stored_response = database.list_responses(interview["id"])[0]
	finally:
		database.close()

	assert result["responses"][0]["evaluation_source"] == "ai_unavailable"
	assert "Gemini evaluation is unavailable" in result["responses"][0]["feedback"]
	assert second_result["responses"][0]["evaluation_source"] == "ai_unavailable"
	assert service._evaluator.calls == 1
	assert stored_response["evaluation_id"] is not None
