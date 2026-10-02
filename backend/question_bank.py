"""Pick interview questions from the reusable ``question_bank`` table (works without any AI key)."""

from __future__ import annotations

import random
import re

from database.database import Database

# These four categories contain the same role-agnostic questions for every role in the bank,
# so they are safe to use for roles the bank has no dedicated questions for.
GENERIC_CATEGORIES = ("behavioral", "background", "communication", "culture_fit")

# The frontend offers far more roles than the five stored in question_bank. First keyword hit wins
# (so "ML Engineer" lands on Data Scientist before it could reach Software Engineer).
# Single words match token prefixes ("partnership" matches "Partnerships"); words of 3 letters
# or fewer ("ai", "ml", "web") must match a whole word.
ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Product Manager", ("product",)),
    ("Data Scientist", ("data", "machine learning", "ml", "ai", "nlp", "analytics")),
    ("Marketing Manager", ("marketing", "brand", "digital")),
    ("Sales Representative", ("sales", "account manager", "business development", "growth", "partnership")),
    (
        "Software Engineer",
        ("software", "developer", "devops", "cloud", "reliability", "security", "web", "mobile", "stack", "penetration"),
    ),
)


def match_bank_role(job_role: str, bank_roles: list[str]) -> str | None:
    """Return the question_bank role that best fits ``job_role``, or None if nothing fits."""
    wanted = job_role.strip().lower()
    for role in bank_roles:
        if role.lower() == wanted:
            return role
    tokens = re.findall(r"[a-z0-9]+", wanted)
    phrase = " ".join(tokens)
    for role, keywords in ROLE_KEYWORDS:
        if role not in bank_roles:
            continue
        for keyword in keywords:
            if " " in keyword:
                hit = keyword in phrase
            elif len(keyword) <= 3:
                hit = keyword in tokens
            else:
                hit = any(token.startswith(keyword) for token in tokens)
            if hit:
                return role
    return None


def _category_plan(technical: bool, has_role: bool) -> list[str]:
    """Categories to draw from, in rotation (repeats weight the mix)."""
    if not has_role:
        return ["behavioral", "background", "communication", "culture_fit"]
    if technical:
        return ["technical", "technical", "situational", "technical", "behavioral"]
    return ["behavioral", "situational", "communication", "background", "culture_fit"]


def pick_questions(
    database: Database,
    job_role: str,
    interview_type: str,
    count: int,
    rng: random.Random | None = None,
) -> list[str]:
    """Up to ``count`` distinct questions; may return fewer if the bank runs out."""
    rng = rng or random.Random()
    bank_role = match_bank_role(job_role, database.question_bank_roles())
    technical = interview_type.strip().lower() in {"technical", "tech"}
    plan = _category_plan(technical, has_role=bank_role is not None)

    pools = database.question_bank_texts(set(plan), job_role=bank_role)
    for texts in pools.values():
        rng.shuffle(texts)

    picked: list[str] = []
    while len(picked) < count and any(pools[category] for category in plan):
        for category in plan:
            if len(picked) >= count:
                break
            if pools[category]:
                picked.append(pools[category].pop())
    return picked


__all__ = ["GENERIC_CATEGORIES", "match_bank_role", "pick_questions"]
