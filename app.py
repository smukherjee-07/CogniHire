from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database.database import get_database


app = FastAPI(title="CogniHire API")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"],
)


class InterviewRequest(BaseModel):
	interview_type: str = "technical"
	job_role: str = Field(min_length=1)
	question_count: int = Field(default=5, ge=1, le=20)
	experience_level: str = "mid"
	user_id: str | None = None


class ResponseRequest(BaseModel):
	question_id: str
	answer_text: str = ""
	answer_mode: str = "text"
	audio_file_path: str | None = None
	video_file_path: str | None = None


def _demo_user_id(database: Any) -> str:
	user = database._one("SELECT id FROM users WHERE username = 'local-demo'")
	if user:
		return user["id"]
	return database.create_user("local-demo", "local-demo-password")["id"]


def _fallback_questions(job_role: str, interview_type: str, count: int) -> list[str]:
	questions = [
		f"What interests you most about working as a {job_role}?",
		f"Describe a challenging problem you solved in a {interview_type} setting.",
		"How do you check the quality of your work before delivering it?",
		"Tell me about a time you received difficult feedback and acted on it.",
		"What would you focus on during your first 30 days in this role?",
	]
	return questions[:count]


@app.get("/api/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/api/interviews")
def start_interview(request: InterviewRequest) -> dict[str, Any]:
	with get_database() as database:
		user_id = request.user_id or _demo_user_id(database)
		interview = database.create_interview(
			user_id=user_id,
			job_role=request.job_role,
			interview_type=request.interview_type,
			question_count=request.question_count,
			experience_level=request.experience_level,
		)
		questions = database.add_questions(
			interview["id"],
			_fallback_questions(request.job_role, request.interview_type, request.question_count),
			source="local",
		)
		return {"session_id": interview["id"], "interview": interview, "questions": questions}


@app.get("/api/interviews/{session_id}/next-question")
def next_question(session_id: str) -> dict[str, Any]:
	with get_database() as database:
		question = database.next_question(session_id)
		if not question:
			raise HTTPException(status_code=404, detail="No unanswered question found")
		return {"question_id": question["id"], "question_number": question["question_number"], "question": question["question_text"]}


@app.post("/api/interviews/{session_id}/responses")
def submit_response(session_id: str, request: ResponseRequest) -> dict[str, Any]:
	with get_database() as database:
		try:
			response = database.save_response(
				interview_id=session_id,
				question_id=request.question_id,
				answer_text=request.answer_text,
				answer_mode=request.answer_mode,
				audio_file_path=request.audio_file_path,
				video_file_path=request.video_file_path,
			)
		except Exception as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		return {"response_id": response["id"], "saved": True}


@app.get("/api/interviews/{session_id}/results")
def interview_results(session_id: str) -> dict[str, Any]:
	with get_database() as database:
		result = database.get_results(session_id)
		if not result["session"]:
			raise HTTPException(status_code=404, detail="Interview session not found")
		database.complete_interview(session_id)
		return {"final_result": result, "ai_evaluation": {"score": result["score"]}}
