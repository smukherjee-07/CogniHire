from ai.api import AIServiceClient
from ai.evaluator import AnswerEvaluator
from ai.question_generator import QuestionGenerator


def test_generate_includes_camera_image_as_gemini_inline_data(monkeypatch):
	captured = {}

	class StubModels:
		@staticmethod
		def generate_content(**kwargs):
			captured["request"] = kwargs
			return type("Response", (), {"text": '{"feedback":"The outfit is clearly visible."}'})()

	class StubClient:
		def __init__(self, **kwargs):
			captured["client"] = kwargs
			self.models = StubModels()

	monkeypatch.setattr("ai.api.genai.Client", StubClient)
	client = AIServiceClient(api_key="test-key", max_retries=0)

	result = client.generate("Assess interview attire", image=("image/jpeg", "aGVsbG8="))

	assert result["data"]["feedback"] == "The outfit is clearly visible."
	assert captured["client"]["api_key"] == "test-key"
	assert captured["request"]["contents"].parts[1].inline_data.data == b"hello"
	assert captured["request"]["contents"].parts[1].inline_data.mime_type == "image/jpeg"


def test_client_does_not_retry_quota_errors(monkeypatch):
	captured = {}

	class StubClient:
		def __init__(self, **kwargs):
			captured.update(kwargs)

	monkeypatch.setattr("ai.api.genai.Client", StubClient)
	AIServiceClient(api_key="test-key", max_retries=2)

	retry_options = captured["http_options"].retry_options
	assert retry_options.attempts == 3
	assert 429 not in retry_options.http_status_codes
	assert {408, 500, 502, 503, 504}.issubset(retry_options.http_status_codes)


class StubAIClient:
	def __init__(self, data):
		self.data = data
		self.prompt = ""

	def generate(self, prompt):
		self.prompt = prompt
		return {"data": self.data}


def test_question_generator_sends_selected_count_in_prompt():
	client = StubAIClient({"questions": ["Question 1?", "Question 2?", "Question 3?"]})
	questions = QuestionGenerator(client).generate_questions("Engineer", count=3)

	assert len(questions) == 3
	assert "exactly 3" in client.prompt


def test_answer_evaluator_parses_gemini_ideal_answer():
	client = StubAIClient({"score": 8, "ideal_answer": "A role-relevant, specific answer."})
	evaluation = AnswerEvaluator(client).evaluate_answer(
		question="How would you improve reliability?",
		candidate_answer="I would add monitoring.",
		job_role="Engineer",
	)

	assert evaluation["ideal_answer"] == "A role-relevant, specific answer."
	assert '"ideal_answer"' in client.prompt


def test_skipped_response_uses_question_specific_ideal_answer_prompt():
	client = StubAIClient({"ideal_answer": "Use a measurable, role-relevant example."})
	answer = AnswerEvaluator(client).generate_ideal_answer(
		question="How would you improve reliability?",
		job_role="Engineer",
		experience_level="senior",
	)

	assert answer == "Use a measurable, role-relevant example."
	assert "How would you improve reliability?" in client.prompt
	assert "senior" in client.prompt
	assert "Candidate answer:" not in client.prompt
