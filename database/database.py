"""SQLite persistence for CogniHire using only the Python standard library."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid


from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "cognihire.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def _database_path() -> Path:
	configured = os.getenv("DATABASE_PATH")
	if configured:
		return Path(configured).expanduser().resolve()
	database_url = os.getenv("DATABASE_URL", "")
	if database_url.startswith("sqlite:///"):
		return Path(database_url[10:]).expanduser().resolve()
	return DEFAULT_DB_PATH


def _now() -> str:
	return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str | None = None) -> str:
	salt = salt or secrets.token_hex(16)
	digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
	return f"pbkdf2_sha256${salt}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
	try:
		algorithm, salt, expected = stored.split("$", 2)
		if algorithm != "pbkdf2_sha256":
			return False
		actual = _hash_password(password, salt).split("$", 2)[2]
		return secrets.compare_digest(actual, expected)
	except ValueError:
		return False


class Database:
	def __init__(self, path: str | Path | None = None):
		self.path = Path(path).expanduser().resolve() if path else _database_path()
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self.connection = sqlite3.connect(self.path, timeout=30)
		self.connection.row_factory = sqlite3.Row
		self.connection.execute("PRAGMA foreign_keys = ON")
		self.connection.execute("PRAGMA journal_mode = WAL")

	def __enter__(self) -> "Database":
		return self

	def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
		if exc_type:
			self.connection.rollback()
		self.close()

	def close(self) -> None:
		self.connection.close()

	def initialize(self) -> None:
		tables = self.connection.execute(
			"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?)",
			("users", "interviews", "question_bank"),
		).fetchall()
		if len(tables) == 3:
			return
		self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
		self.connection.commit()

	def _one(self, query: str, parameters: Iterable[Any] = ()) -> dict[str, Any] | None:
		row = self.connection.execute(query, tuple(parameters)).fetchone()
		return dict(row) if row else None

	def get_user_by_username(self, username: str) -> dict[str, Any] | None:
		return self._one(
			"SELECT id, username, email, created_at FROM users WHERE username = ? COLLATE NOCASE",
			(username.strip(),),
		)

	def create_user(self, username: str, password: str, email: str | None = None) -> dict[str, Any]:
		user_id = str(uuid.uuid4())
		self.connection.execute("INSERT INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)", (user_id, username.strip(), email.strip() if email else None, _hash_password(password)))
		self.connection.commit()
		return self._one("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)) or {}

	def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
		row = self.connection.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
		if not row or not _check_password(password, row["password_hash"]):
			return None
		return {key: row[key] for key in ("id", "username", "email", "created_at")}

	def create_interview(self, user_id: str, job_role: str, interview_type: str, question_count: int = 5, experience_level: str = "mid") -> dict[str, Any]:
		interview_id = str(uuid.uuid4())
		self.connection.execute("INSERT INTO interviews (id, user_id, job_role, interview_type, experience_level, question_count) VALUES (?, ?, ?, ?, ?, ?)", (interview_id, user_id, job_role.strip(), interview_type.strip(), experience_level, question_count))
		self.connection.commit()
		return self._one("SELECT * FROM interviews WHERE id = ?", (interview_id,)) or {}

	def get_interview(self, interview_id: str) -> dict[str, Any] | None:
		return self._one("SELECT * FROM interviews WHERE id = ?", (interview_id,))

	def add_questions(self, interview_id: str, questions: Iterable[str], source: str = "ai") -> list[dict[str, Any]]:
		rows = [ (str(uuid.uuid4()), interview_id, number, str(text).strip(), source) for number, text in enumerate(questions, 1) if str(text).strip() ]
		self.connection.executemany("INSERT INTO questions (id, interview_id, question_number, question_text, source) VALUES (?, ?, ?, ?, ?)", rows)
		self.connection.commit()
		return [dict(row) for row in self.connection.execute("SELECT * FROM questions WHERE interview_id = ? ORDER BY question_number", (interview_id,))]

	def next_question(self, interview_id: str) -> dict[str, Any] | None:
		return self._one("SELECT q.* FROM questions q LEFT JOIN responses r ON r.question_id = q.id WHERE q.interview_id = ? AND r.id IS NULL ORDER BY q.question_number LIMIT 1", (interview_id,))

	def get_question(self, interview_id: str, question_id: str) -> dict[str, Any] | None:
		return self._one(
			"SELECT * FROM questions WHERE interview_id = ? AND id = ?",
			(interview_id, question_id),
		)

	def list_responses(self, interview_id: str) -> list[dict[str, Any]]:
		return [
			dict(row)
			for row in self.connection.execute(
				"""
				SELECT r.*, q.question_text, e.id AS evaluation_id
				FROM responses r
				JOIN questions q ON q.id = r.question_id
				LEFT JOIN evaluations e ON e.response_id = r.id
				WHERE r.interview_id = ?
				ORDER BY q.question_number
				""",
				(interview_id,),
			)
		]

	def save_response(self, interview_id: str, question_id: str, answer_text: str = "", answer_mode: str = "text", audio_file_path: str | None = None, video_file_path: str | None = None) -> dict[str, Any]:
		response_id = str(uuid.uuid4())
		self.connection.execute("INSERT INTO responses (id, interview_id, question_id, answer_text, answer_mode) VALUES (?, ?, ?, ?, ?)", (response_id, interview_id, question_id, answer_text, answer_mode))
		uploads = [(audio_file_path, "audio"), (video_file_path, "video")]
		self.connection.executemany("INSERT INTO media_uploads (id, response_id, media_type, file_path) VALUES (?, ?, ?, ?)", [(str(uuid.uuid4()), response_id, kind, path) for path, kind in uploads if path])
		self.connection.commit()
		return self._one("SELECT * FROM responses WHERE id = ?", (response_id,)) or {}

	def save_evaluation(self, response_id: str, score: float, strengths: list[str] | None = None, weaknesses: list[str] | None = None, feedback: str = "", recommendation: str = "", raw: Any = None) -> dict[str, Any]:
		evaluation_id = str(uuid.uuid4())
		self.connection.execute("INSERT OR REPLACE INTO evaluations (id, response_id, score, strengths_json, weaknesses_json, feedback, recommendation, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (evaluation_id, response_id, score, json.dumps(strengths or []), json.dumps(weaknesses or []), feedback, recommendation, json.dumps(raw) if raw is not None else None))
		self.connection.commit()
		return self._one("SELECT * FROM evaluations WHERE response_id = ?", (response_id,)) or {}

	def complete_interview(self, interview_id: str) -> None:
		self.connection.execute("UPDATE interviews SET status = 'completed', completed_at = ? WHERE id = ?", (_now(), interview_id))
		self.connection.commit()

	def get_results(self, interview_id: str) -> dict[str, Any]:
		interview = self._one("SELECT * FROM interviews WHERE id = ?", (interview_id,))
		rows = [dict(row) for row in self.connection.execute("SELECT q.*, r.id AS response_id, r.answer_text, r.answer_mode, e.score, e.strengths_json, e.weaknesses_json, e.feedback, e.recommendation FROM questions q LEFT JOIN responses r ON r.question_id = q.id LEFT JOIN evaluations e ON e.response_id = r.id WHERE q.interview_id = ? ORDER BY q.question_number", (interview_id,))]
		scores = [row["score"] for row in rows if row["score"] is not None]
		return {"session": interview, "responses": rows, "score": round(sum(scores) / len(scores), 2) if scores else 0}

	def list_interviews(self, user_id: str) -> list[dict[str, Any]]:
		return [dict(row) for row in self.connection.execute("SELECT * FROM interviews WHERE user_id = ? ORDER BY started_at DESC", (user_id,))]


def get_database(path: str | Path | None = None) -> Database:
	database = Database(path)
	database.initialize()
	return database


__all__ = ["Database", "get_database"]
