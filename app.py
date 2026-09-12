from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth import authenticate_user, get_or_create_demo_user, register_user
from backend.interview import InterviewService
from database.database import get_database


WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="CogniHire API")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
	return FileResponse(WEB_DIR / "index.html")


app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
app.mount("/css", StaticFiles(directory=WEB_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=WEB_DIR / "js"), name="js")
app.mount("/media", StaticFiles(directory=WEB_DIR), name="media")


class InterviewRequest(BaseModel):
	interview_type: str = "technical"
	job_role: str = Field(min_length=1)
	question_count: int = Field(default=5, ge=1, le=20)
	experience_level: str = "mid"
	user_id: str | None = None
	focus_areas: list[str] = Field(default_factory=list)


class ResponseRequest(BaseModel):
	question_id: str = Field(min_length=1)
	answer_text: str = ""
	answer_mode: str = "text"
	audio_file_path: str | None = None
	video_file_path: str | None = None


class AuthRequest(BaseModel):
	username: str = Field(min_length=2)
	password: str = Field(min_length=4)
	email: str | None = None


@app.get("/api/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/api/auth/register", status_code=201)
def create_account(request: AuthRequest) -> dict[str, Any]:
	with get_database() as database:
		try:
			return {"user": register_user(database, request.username, request.password, request.email)}
		except ValueError as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login(request: AuthRequest) -> dict[str, Any]:
	with get_database() as database:
		user = authenticate_user(database, request.username, request.password)
		if not user:
			raise HTTPException(status_code=401, detail="Invalid username or password")
		return {"user": user}


@app.post("/api/interviews")
def start_interview(request: InterviewRequest) -> dict[str, Any]:
	with get_database() as database:
		user_id = request.user_id or get_or_create_demo_user(database)["id"]
		try:
			return InterviewService(database).start(
				user_id=user_id,
				job_role=request.job_role,
				interview_type=request.interview_type,
				question_count=request.question_count,
				experience_level=request.experience_level,
				focus_areas=request.focus_areas,
			)
		except (ValueError, KeyError) as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/interviews/{session_id}/next-question")
def next_question(session_id: str) -> dict[str, Any]:
	with get_database() as database:
		try:
			question = InterviewService(database).next_question(session_id)
		except ValueError as exc:
			raise HTTPException(status_code=404, detail=str(exc)) from exc
		if not question:
			raise HTTPException(status_code=404, detail="No unanswered question found")
		return {
			"question_id": question["id"],
			"question_number": question["question_number"],
			"question": question["question_text"],
		}


@app.post("/api/interviews/{session_id}/responses")
def submit_response(session_id: str, request: ResponseRequest) -> dict[str, Any]:
	with get_database() as database:
		try:
			response = InterviewService(database).submit_response(
				session_id=session_id,
				question_id=request.question_id,
				answer_text=request.answer_text,
				answer_mode=request.answer_mode,
				audio_file_path=request.audio_file_path,
				video_file_path=request.video_file_path,
			)
		except (ValueError, KeyError) as exc:
			raise HTTPException(status_code=400, detail=str(exc)) from exc
		return {"response_id": response["id"], "saved": True}


@app.get("/api/interviews/{session_id}/results")
def interview_results(session_id: str) -> dict[str, Any]:
	with get_database() as database:
		try:
			result = InterviewService(database).results(session_id)
		except ValueError as exc:
			raise HTTPException(status_code=404, detail=str(exc)) from exc
		return {
			"final_result": result,
			"ai_evaluation": {
				"score": result["score"],
				"responses": result["responses"],
			},
		}


if __name__ == "__main__":
	import uvicorn

	uvicorn.run("app:app", host="127.0.0.1", port=8000)
