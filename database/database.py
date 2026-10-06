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
ANSWERS_PATH = Path(__file__).with_name("answers.sql")


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


def _loads(value: str | None, default: Any) -> Any:
	try:
		return json.loads(value) if value else default
	except (TypeError, ValueError):
		return default


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
		if tables:
			question_bank_columns = {
				row[1]
				for row in self.connection.execute("PRAGMA table_info(question_bank)").fetchall()
			}
			if "answer_text" not in question_bank_columns:
				self.connection.execute("ALTER TABLE question_bank ADD COLUMN answer_text TEXT NOT NULL DEFAULT ''")
				self.connection.commit()
		if len(tables) == 3:
			version = self.connection.execute("PRAGMA user_version").fetchone()[0]
			if version < 1:
				self.connection.executescript(
					"DROP VIEW IF EXISTS v_interview_summary; "
					"CREATE VIEW v_interview_summary AS "
					"SELECT i.id AS interview_id, i.user_id, u.username, i.job_role, i.interview_type, "
					"i.experience_level, i.question_count, i.status, i.started_at, i.completed_at, "
					"COUNT(DISTINCT q.id) AS questions_created, "
					"COUNT(DISTINCT CASE WHEN TRIM(r.answer_text) <> '' THEN r.id END) AS responses_submitted, "
					"ROUND(AVG(e.score), 2) AS average_score "
					"FROM interviews i JOIN users u ON u.id = i.user_id "
					"LEFT JOIN questions q ON q.interview_id = i.id "
					"LEFT JOIN responses r ON r.interview_id = i.id "
					"LEFT JOIN evaluations e ON e.response_id = r.id "
					"GROUP BY i.id; PRAGMA user_version = 1;"
				)
			if version < 2:
				self.connection.executescript(ANSWERS_PATH.read_text(encoding="utf-8"))
				self.connection.execute("PRAGMA user_version = 2")
				self.connection.commit()
			return
		self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
		self.connection.commit()
		self.connection.executescript(ANSWERS_PATH.read_text(encoding="utf-8"))
		self.connection.execute("PRAGMA user_version = 2")
		self.connection.commit()

	def _one(self, query: str, parameters: Iterable[Any] = ()) -> dict[str, Any] | None:
		row = self.connection.execute(query, tuple(parameters)).fetchone()
		return dict(row) if row else None

	def get_user_by_username(self, username: str) -> dict[str, Any] | None:
		return self._one(
			"SELECT id, username, email, created_at FROM users WHERE username = ? COLLATE NOCASE",
			(username.strip(),),
		)

	def get_user(self, user_id: str) -> dict[str, Any] | None:
		return self._one("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,))

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

	def ensure_empty_responses(self, interview_id: str) -> None:
		"""Create skipped response rows for questions with no submitted response."""
		questions = self.connection.execute(
			"SELECT q.id FROM questions q LEFT JOIN responses r ON r.question_id = q.id "
			"WHERE q.interview_id = ? AND r.id IS NULL",
			(interview_id,),
		).fetchall()
		if questions:
			self.connection.executemany(
				"INSERT INTO responses (id, interview_id, question_id, answer_text, answer_mode) VALUES (?, ?, ?, '', 'text')",
				[(str(uuid.uuid4()), interview_id, question["id"]) for question in questions],
			)
			self.connection.commit()

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
		"""Save an answer. Submitting the same question again updates it instead of failing (idempotent)."""
		self.connection.execute(
			"INSERT INTO responses (id, interview_id, question_id, answer_text, answer_mode) VALUES (?, ?, ?, ?, ?) "
			"ON CONFLICT(interview_id, question_id) DO UPDATE SET answer_text = excluded.answer_text, answer_mode = excluded.answer_mode",
			(str(uuid.uuid4()), interview_id, question_id, answer_text, answer_mode),
		)
		response = self._one("SELECT * FROM responses WHERE interview_id = ? AND question_id = ?", (interview_id, question_id)) or {}
		for path, kind in ((audio_file_path, "audio"), (video_file_path, "video")):
			if path and not self._one("SELECT 1 FROM media_uploads WHERE response_id = ? AND media_type = ? AND file_path = ?", (response["id"], kind, path)):
				self.connection.execute("INSERT INTO media_uploads (id, response_id, media_type, file_path) VALUES (?, ?, ?, ?)", (str(uuid.uuid4()), response["id"], kind, path))
		self.connection.commit()
		return response

	def save_evaluation(self, response_id: str, score: float, strengths: list[str] | None = None, weaknesses: list[str] | None = None, feedback: str = "", recommendation: str = "", ideal_answer: str = "", raw: Any = None) -> dict[str, Any]:
		evaluation_id = str(uuid.uuid4())
		if ideal_answer and isinstance(raw, dict):
			raw = {**raw, "ideal_answer": ideal_answer}
		self.connection.execute("INSERT OR REPLACE INTO evaluations (id, response_id, score, strengths_json, weaknesses_json, feedback, recommendation, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (evaluation_id, response_id, score, json.dumps(strengths or []), json.dumps(weaknesses or []), feedback, recommendation, json.dumps(raw) if raw is not None else None))
		self.connection.commit()
		return self._one("SELECT * FROM evaluations WHERE response_id = ?", (response_id,)) or {}

	def complete_interview(self, interview_id: str) -> None:
		self.connection.execute("UPDATE interviews SET status = 'completed', completed_at = ? WHERE id = ?", (_now(), interview_id))
		self.connection.commit()

	def get_results(self, interview_id: str) -> dict[str, Any]:
		interview = self._one("SELECT * FROM interviews WHERE id = ?", (interview_id,))
		rows = []
		for row in self.connection.execute("SELECT q.*, r.id AS response_id, r.answer_text, r.answer_mode, e.score, e.strengths_json, e.weaknesses_json, e.feedback, e.recommendation, e.raw_json FROM questions q LEFT JOIN responses r ON r.question_id = q.id LEFT JOIN evaluations e ON e.response_id = r.id WHERE q.interview_id = ? ORDER BY q.question_number", (interview_id,)):
			item = dict(row)
			item["strengths"] = _loads(item["strengths_json"], [])
			item["weaknesses"] = _loads(item["weaknesses_json"], [])
			raw = _loads(item.pop("raw_json"), {})
			item["evaluation_source"] = raw.get("source") if isinstance(raw, dict) else None
			item["ideal_answer"] = raw.get("ideal_answer", raw.get("suggested_answer", "")) if isinstance(raw, dict) else ""
			rows.append(item)
		scores = [row["score"] for row in rows if row["score"] is not None]
		return {
			"session": interview,
			"responses": rows,
			"score": round(sum(scores) / len(scores), 2) if scores else 0,
			"questions_total": len(rows),
			"questions_answered": sum(1 for row in rows if (row["answer_text"] or "").strip()),
		}

	def list_interviews(self, user_id: str) -> list[dict[str, Any]]:
		return [dict(row) for row in self.connection.execute("SELECT * FROM interviews WHERE user_id = ? ORDER BY started_at DESC", (user_id,))]


	def list_interview_summaries(self, user_id: str) -> list[dict[str, Any]]:
		"""Dashboard/history rows (question and answer counts, average score) from v_interview_summary."""
		return [dict(row) for row in self.connection.execute("SELECT * FROM v_interview_summary WHERE user_id = ? ORDER BY started_at DESC", (user_id,))]

	def question_bank_roles(self) -> list[str]:
		return [row[0] for row in self.connection.execute("SELECT DISTINCT job_role FROM question_bank ORDER BY job_role")]

	def get_question_bank_reference(self, question_text: str, job_role: str | None = None, question_bank_id: str | None = None) -> str:
		"""Return the stored ideal/reference answer for a bank question when available."""
		if question_bank_id:
			row = self.connection.execute(
				"SELECT answer_text FROM question_bank WHERE id = ? LIMIT 1",
				(question_bank_id,),
			).fetchone()
			if row and (row["answer_text"] or "").strip():
				return row["answer_text"].strip()

		parameters: list[Any] = [question_text.strip()]
		query = "SELECT answer_text FROM question_bank WHERE question_text = ?"
		if job_role:
			query += " AND job_role = ? COLLATE NOCASE"
			parameters.append(job_role.strip())
		row = self.connection.execute(query + " LIMIT 1", tuple(parameters)).fetchone()
		if row and (row["answer_text"] or "").strip():
			return row["answer_text"].strip()
		return ""

	def question_bank_texts(self, categories: Iterable[str], job_role: str | None = None) -> dict[str, list[str]]:
		"""Distinct question texts per category, for one bank role or (job_role=None) across all roles."""
		categories = list(categories)
		query = f"SELECT category, question_text FROM question_bank WHERE category IN ({','.join('?' * len(categories))})"
		parameters: list[Any] = list(categories)
		if job_role:
			query += " AND job_role = ? COLLATE NOCASE"
			parameters.append(job_role)
		result: dict[str, list[str]] = {category: [] for category in categories}
		seen: set[tuple[str, str]] = set()
		for category, text in self.connection.execute(query + " ORDER BY id", parameters):
			if (category, text) not in seen:
				seen.add((category, text))
				result[category].append(text)
		return result


def get_database(path: str | Path | None = None) -> Database:
	database = Database(path)
	database.initialize()
	return database


__all__ = ["Database", "get_database"]
