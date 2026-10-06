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
Generate exactly {count} high-quality {interview_type} interview questions for a candidate at {experience_level} level.
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
- Return exactly {count} questions.
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
  "feedback": "What you did correctly: ...\\nWhat was missing or incorrect: ...\\nHow to improve: ...",
  "recommendation": "...",
  "ideal_answer": "..."
}}

Scoring guidance:
- 0 to 10 scale where 10 is excellent.
- Consider correctness, reasoning, structure, depth, clarity, and relevance.
- Make feedback detailed and specific to the candidate's answer. In the feedback string, include three clearly labeled sections: 'What you did correctly', 'What was missing or incorrect', and 'How to improve'.
- Write a concise ideal answer that directly addresses this exact question.
- For behavioral questions, use a clearly marked fill-in template rather than inventing personal experiences or achievements.
- Do not claim the candidate achieved or experienced facts they did not provide. Use clearly marked placeholders such as [specific result] when personal details are missing.
- Provide the ideal answer even if the candidate answer is empty; use placeholders rather than invented personal history.
- Do not add any text outside the JSON object.
""".strip()


def build_ideal_answer_prompt(question: str, job_role: str, experience_level: str = "mid") -> str:
    """Create a question-only prompt for a role-appropriate ideal interview answer."""
    return f"""
You are an expert interview coach for a {job_role} role at {experience_level} level.
Write a strong, accurate ideal answer to this exact interview question:

{question}

For technical questions, give a direct, correct answer with concise reasoning.
For behavioral questions, provide a customizable first-person template with bracketed placeholders; never invent a candidate's personal history, employers, or results.
Make the answer specific to this question and do not reuse a generic answer.

Return valid JSON only:
{{
  "ideal_answer": "..."
}}
""".strip()


def build_attire_evaluation_prompt(job_role: str) -> str:
    """Create an image-grounded, objective professional-attire assessment prompt."""
    return f"""
Assess only the visible clothing and interview presentation in this image for a {job_role} interview.
Do not identify the person or infer protected traits, personality, socioeconomic status, or competence.
If clothing is not clearly visible, say that the image is inconclusive. Keep feedback respectful, specific, and actionable.

Return valid JSON only with this schema:
{{
  "feedback": "..."
}}
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
