"""Session-level orchestration for CogniHire interviews."""

from __future__ import annotations

from typing import Any

from database.database import Database


class SessionService:
    """Own interview lifecycle operations that do not depend on HTTP."""

    def __init__(self, database: Database):
        self.database = database

    def get(self, session_id: str) -> dict[str, Any] | None:
        return self.database.get_interview(session_id)

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return self.database.list_interviews(user_id)

    def complete(self, session_id: str) -> dict[str, Any]:
        session = self.database.get_interview(session_id)
        if not session:
            raise ValueError("Interview session not found")
        self.database.complete_interview(session_id)
        return self.database.get_interview(session_id) or session


__all__ = ["SessionService"]
