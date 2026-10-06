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


class QuotaEvaluator:
	def __init__(self):
		self.calls = []

	def evaluate_answer(self, question, **_kwargs):
		self.calls.append(question)
		if len(self.calls) == 1:
			raise ValueError("429 RESOURCE_EXHAUSTED: quota exceeded")
		raise AssertionError("Gemini must not be called after a quota response")

	def generate_ideal_answer(self, question, **_kwargs):
		self.calls.append(question)
		if len(self.calls) == 1:
			raise ValueError("429 RESOURCE_EXHAUSTED: quota exceeded")
		raise AssertionError("Gemini must not be called after a quota response")


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
	assert "I would first clarify" in result["ideal_answer"]
	assert result["raw"]["source"] == "demo_fallback"
	assert "No response was submitted" in result["feedback"]


def test_evaluate_returns_truthful_fallback_when_gemini_fails(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = FailedEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["raw"]["source"] == "demo_fallback"
	assert result["strengths"] == ["You provided a response to the question."]
	assert "response is brief" in result["weaknesses"][0]
	assert "concrete example or result" in result["recommendation"]
	assert "I would first clarify" in result["ideal_answer"]
	assert "Gemini request failed" not in result["feedback"]


def test_api_quota_error_is_preserved_in_review_feedback(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = QuotaEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["feedback"] == "429 RESOURCE_EXHAUSTED: quota exceeded"
	assert "429 RESOURCE_EXHAUSTED" in result["feedback"]
	assert result["raw"]["source"] == "demo_fallback"


def test_refactor_rewrite_fallback_ideal_answer_is_question_specific():
	answer = InterviewService._fallback_ideal_answer(
		"How do you decide when to refactor versus rewrite code?"
	)

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

	assert "I would refactor" in result["responses"][0]["ideal_answer"]
	assert "refactor" in result["responses"][0]["ideal_answer"]
	assert result["responses"][0]["evaluation_source"] == "demo_fallback"
	assert "429 RESOURCE_EXHAUSTED quota exceeded" in result["responses"][0]["feedback"]
	assert "provider details" in result["responses"][0]["feedback"]
	assert service._evaluator.calls == 0


def test_local_demo_review_uses_answer_content_without_claiming_verified_correctness(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: False)
	service = InterviewService(database=None)

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["strengths"] == ["You provided a response to the question."]
	assert "response is brief" in result["weaknesses"][0]
	assert result["raw"]["source"] == "demo_fallback"


def test_blank_demo_reviews_use_question_specific_ideal_answers(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: False)
	service = InterviewService(database=None)

	refactor_result = service._evaluate(
		{"answer_text": "", "question_text": "How do you decide when to refactor versus rewrite code?"},
		{"job_role": "Engineer", "experience_level": "mid"},
	)
	star_result = service._evaluate(
		{"answer_text": "", "question_text": "Tell me about a time you improved a system after a production incident."},
		{"job_role": "Engineer", "experience_level": "mid"},
	)

	assert "incrementally" in refactor_result["ideal_answer"]
	assert "STAR" in star_result["ideal_answer"]
	assert refactor_result["ideal_answer"] != star_result["ideal_answer"]


def test_generic_fallback_ideal_answers_are_question_specific():
	first = InterviewService._fallback_ideal_answer("Describe how you would improve performance in a large application.")
	second = InterviewService._fallback_ideal_answer("Explain how you would communicate a production incident to stakeholders.")

	assert first != second
	assert "large application" in first.lower()
	assert "production incident" in second.lower()


def test_force_demo_review_skips_evaluator_calls(monkeypatch):
	monkeypatch.setenv("COGNIHIRE_FORCE_DEMO_REVIEW", "1")
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	service._evaluator = FailedEvaluator()

	result = service._evaluate(_response(), {"job_role": "Engineer", "experience_level": "mid"})

	assert result["raw"]["source"] == "demo_fallback"
	assert service._evaluator.calls == 0


def test_reference_answer_from_question_bank_is_used_for_local_scoring(tmp_path):
	database = Database(tmp_path / "reference-answer.db")
	database.initialize()
	question_bank_id = "bank-123"
	database.connection.execute(
		"INSERT INTO question_bank (id, job_role, category, difficulty, question_text, answer_text) VALUES (?, ?, ?, ?, ?, ?)",
		(
			question_bank_id,
			"Software Engineer",
			"technical",
			"mid",
			"Explain the difference between an abstract class and an interface.",
			"An abstract class can provide shared implementation and state, while an interface defines a contract. Use an abstract class for common behavior and an interface when multiple types need a common capability.",
		),
	)
	database.connection.commit()
	service = InterviewService(database)
	result = service._local_review(
		{
			"question_text": "Explain the difference between an abstract class and an interface.",
			"answer_text": "An abstract class shares behavior and state, while an interface defines a contract that multiple classes can implement for the same capability.",
		},
		{"job_role": "Software Engineer", "experience_level": "mid"},
		question_bank_id=question_bank_id,
	)
	assert result["raw"]["source"] == "demo_fallback"
	assert result["score"] >= 7
	assert any("contract" in item.lower() for item in result["strengths"])
	assert "reference answer" not in " ".join(result["strengths"]).lower()


def test_local_review_gives_low_score_for_irrelevant_answer(tmp_path):
	database = Database(tmp_path / "low-score.db")
	database.initialize()
	query = "What is the difference between SQL and NoSQL databases?"
	database.connection.execute(
		"INSERT INTO question_bank (id, job_role, category, difficulty, question_text, answer_text) VALUES (?, ?, ?, ?, ?, ?)",
		(
			"bank-low",
			"Software Engineer",
			"technical",
			"mid",
			query,
			"SQL uses schema-based tables and transactions; NoSQL is flexible and horizontally scalable. Use SQL for structured relational data and NoSQL for flexible high-scale workloads.",
		),
	)
	database.connection.commit()
	service = InterviewService(database)
	result = service._local_review(
		{
			"question_text": query,
			"answer_text": "I like pizza and I would work harder to finish the task.",
		},
		{"job_role": "Software Engineer", "experience_level": "mid"},
		question_bank_id="bank-low",
	)
	assert result["score"] <= 4.5
	assert any("relevance" in item.lower() or "coverage" in item.lower() or "key concepts" in item.lower() for item in result["weaknesses"])


def test_quota_failure_stops_gemini_calls_for_remaining_questions(monkeypatch):
	monkeypatch.setattr(interview_module, "ai_configured", lambda: True)
	service = InterviewService(database=None)
	evaluator = QuotaEvaluator()
	service._evaluator = evaluator
	responses = [
		{**_response(), "question_text": f"How do you make decision {number}?", "answer_text": f"I make decision {number} with evidence."}
		for number in range(1, 4)
	]

	results = service._evaluate_many(responses, {"job_role": "Engineer", "experience_level": "mid"})

	assert evaluator.calls == [responses[0]["question_text"]]
	assert all(result["raw"]["source"] == "demo_fallback" for result in results)
	assert all(result["ideal_answer"] for result in results)


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

	assert result["responses"][0]["evaluation_source"] == "demo_fallback"
	assert result["responses"][0]["strengths"]
	assert second_result["responses"][0]["evaluation_source"] == "demo_fallback"
	assert service._evaluator.calls == 1
	assert stored_response["evaluation_id"] is not None


def test_database_initialization_loads_reference_answers(tmp_path):
	database = Database(tmp_path / "answers-seed.db")
	database.initialize()
	try:
		count, populated = database.connection.execute(
			"SELECT COUNT(*), SUM(LENGTH(TRIM(answer_text)) > 0) FROM question_bank"
		).fetchone()
		answer = database.get_question_bank_reference(
			"Explain the difference between an abstract class and an interface.",
			"Software Engineer",
		)
	finally:
		database.close()

	assert count == 750
	assert populated == 750
	assert "abstract class" in answer
