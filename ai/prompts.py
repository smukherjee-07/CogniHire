"""Prompt builders for interview question generation and answer evaluation."""

from __future__ import annotations


def build_question_generation_prompt(
    job_role: str,
    experience_level: str = "mid",
    focus_areas: list[str] | None = None,
    interview_type: str = "technical",
    count: int = 5,
) -> str:
    """Create a prompt for generating interview questions."""
    focus_areas = focus_areas or []
    focus_text = ", ".join(focus_areas) if focus_areas else "general role fit and core skills"

    return f"""
You are an expert hiring coach for a {job_role} role.
Generate {count} high-quality {interview_type} interview questions for a candidate at {experience_level} level.
Focus on: {focus_text}.

Return valid JSON only, with this schema:
{{
  "questions": [
    "question 1",
    "question 2"
  ]
}}

Rules:
- Keep the questions practical and job-relevant.
- Avoid repeated questions.
- Include a mix of conceptual, scenario-based, and behavioral prompts when appropriate.
- Do not include extra explanation outside the JSON.
""".strip()


def build_answer_evaluation_prompt(
    question: str,
    candidate_answer: str,
    job_role: str,
    experience_level: str = "mid",
    skills: list[str] | None = None,
) -> str:
    """Create a prompt for evaluating an interview answer."""
    skills = skills or []
    skill_text = ", ".join(skills) if skills else "core domain skills"

    return f"""
You are an expert technical interviewer scoring a candidate response.
Evaluate the answer to this interview question for the {job_role} role at {experience_level} level.

Question:
{question}

Candidate answer:
{candidate_answer}

Focus areas: {skill_text}

Return valid JSON only with this schema:
{{
  "score": 0,
  "strengths": ["..."],
  "weaknesses": ["..."],
  "feedback": "...",
  "recommendation": "..."
}}

Scoring guidance:
- 0 to 10 scale where 10 is excellent.
- Consider correctness, reasoning, structure, depth, clarity, and relevance.
- Keep the feedback actionable and concise.
- Do not add any text outside the JSON object.
""".strip()


def build_followup_question_prompt(question: str, candidate_answer: str) -> str:
    """Generate a follow-up question based on the candidate answer."""
    return f"""
You are an interview coach.
You have a question and a candidate answer. Generate one strong follow-up question that probes the candidate deeper.

Original question:
{question}

Candidate answer:
{candidate_answer}

Return valid JSON only:
{{
  "follow_up_question": "..."
}}
""".strip()
