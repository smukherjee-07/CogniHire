"""Authentication helpers used by the HTTP API and local frontend."""

from __future__ import annotations

from typing import Any

from database.database import Database


DEMO_USERNAME = "local-demo"
DEMO_PASSWORD = "local-demo-password"


def get_or_create_demo_user(database: Database) -> dict[str, Any]:
    """Return a stable local user for frontend sessions without authentication."""
    user = database.get_user_by_username(DEMO_USERNAME)
    if user:
        return user
    try:
        return database.create_user(DEMO_USERNAME, DEMO_PASSWORD)
    except Exception:
        user = database.get_user_by_username(DEMO_USERNAME)
        if user:
            return user
        raise


def register_user(
    database: Database,
    username: str,
    password: str,
    email: str | None = None,
) -> dict[str, Any]:
    username = username.strip()
    if len(username) < 2:
        raise ValueError("Username must contain at least 2 characters")
    if len(password) < 4:
        raise ValueError("Password must contain at least 4 characters")
    if database.get_user_by_username(username):
        raise ValueError("Username already exists")
    return database.create_user(username, password, email)


def authenticate_user(database: Database, username: str, password: str) -> dict[str, Any] | None:
    return database.authenticate_user(username.strip(), password)


__all__ = [
    "DEMO_PASSWORD",
    "DEMO_USERNAME",
    "authenticate_user",
    "get_or_create_demo_user",
    "register_user",
]
