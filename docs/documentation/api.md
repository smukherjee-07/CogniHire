# CogniHire HTTP API

Base URL: `http://127.0.0.1:8000` - the same server also serves the web app at `/`.
Interactive docs (Swagger UI): `/docs`. All bodies are JSON.

## Interview lifecycle (what `web/js/api.js` calls)

| # | Method & path | Purpose |
|---|---|---|
| 1 | `POST /api/interviews` | Start a session and generate its questions |
| 2 | `GET /api/interviews/{session_id}/next-question` | First question that has no answer yet |
| 3 | `POST /api/interviews/{session_id}/responses` | Save (or update) the answer to a question |
| 4 | `GET /api/interviews/{session_id}/results` | Score all answers, complete the session, return the report |

Repeat 2 -> 3 until step 2 answers **404** (`No unanswered question found`): that is the "interview finished" signal.

### 1. Start - `POST /api/interviews`

```json
{ "job_role": "Data Scientist", "interview_type": "Technical", "question_count": 5 }
```

| Field | Type | Notes |
|---|---|---|
| `job_role` | string, required | Any text. The AI uses it as-is; the question bank maps it to the closest of its 5 roles |
| `interview_type` | string | `technical` (default) or anything else; case-insensitive |
| `question_count` | int 1-20 | default 5 |
| `experience_level` | string | default `mid`; passed to the AI prompts |
| `focus_areas` | string[] | optional; passed to the AI question prompt |
| `user_id` | string | optional; omitted = shared local demo user. Unknown id -> **400** |

Response: `{ "session_id": "...", "interview": {...}, "questions": [{ "id", "question_number", "question_text", "source" }] }`
where `source` is `ai`, `bank` (question_bank table) or `local` (built-in last resort).

### 2. Next question - `GET /api/interviews/{session_id}/next-question`

`200 { "question_id": "...", "question_number": 1, "question": "..." }` - **404** when nothing is left or the session does not exist.

### 3. Submit answer - `POST /api/interviews/{session_id}/responses`

```json
{ "question_id": "...", "answer_text": "...", "answer_mode": "text" }
```

`answer_mode`: `text` | `audio` | `video` | `audio_video`. `audio_file_path` / `video_file_path` are optional strings.
`skipped` (optional, default `false`): set this to `true` to submit an empty `answer_text` with no media - e.g. when
speech capture didn't get anything for that question. Without `skipped: true`, an empty answer with no media is rejected.
Response: `{ "response_id": "...", "saved": true }`.

Submitting the same `question_id` again **updates** the answer and returns the same `response_id` (safe to retry).
Errors -> **400**: question not in this session, empty answer without `skipped: true`, bad `answer_mode`, session already completed.

### 4. Results - `GET /api/interviews/{session_id}/results`

Evaluates every unevaluated answer (AI when configured, otherwise local scoring), marks the session completed, and returns:

```json
{
  "final_result": {
    "session": { "id": "...", "job_role": "...", "status": "completed" },
    "score": 7.5,
    "questions_total": 5,
    "questions_answered": 5,
    "responses": [{
      "question_number": 1, "question_text": "...", "answer_text": "...",
      "score": 8.0, "strengths": ["..."], "weaknesses": ["..."],
      "feedback": "...", "recommendation": "...",
      "evaluation_source": "ai"
    }]
  },
  "ai_evaluation": { "score": 7.5, "responses": [ ...same rows... ] }
}
```

`score` is 0-10 (average over answered questions, skipped ones included as 0). `evaluation_source` is `ai`, `local`, or `skipped`
(question was submitted with `skipped: true` - scored 0, no AI call made). Unanswered questions (never submitted at all) appear
with `response_id: null`. Calling results again is safe and returns the same data.

## Other endpoints

| Method & path | Purpose |
|---|---|
| `GET /api/health` | `{ "status": "ok", "ai_configured": bool, "ai_model": "..." }` |
| `GET /api/interviews?user_id=` | History/dashboard rows for a user (demo user if omitted): `interview_id, job_role, interview_type, status, question_count, responses_submitted, average_score, started_at, completed_at` |
| `POST /api/auth/register` | `{ username (>=2), password (>=4), email? }` -> **201** `{ "user": {...} }`; duplicate username -> 400 |
| `POST /api/auth/login` | `{ username, password }` -> `{ "user": { "id", "username", ... } }`; wrong credentials -> 401 |

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `AI_API_KEY` (or `GEMINI_API_KEY`) | unset | Gemini key. Unset = run without AI (question bank + local scoring) |
| `AI_MODEL` | `gemini-3.5-flash` | Any Gemini model id that supports `generateContent` |
| `AI_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `AI_MAX_RETRIES` | `2` | Retries on 429 / 5xx / dropped connections |
| `DATABASE_PATH` / `DATABASE_URL` | `database/cognihire.db` | SQLite file (`sqlite:///path` also accepted) |

## Fallback behaviour

Question generation: **AI -> question_bank (750 questions) -> 5 built-in questions**.
Answer scoring: **AI -> local length-based score**. Each AI failure is logged as a warning that includes Google's error text.
