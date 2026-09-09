-- CogniHire SQLite table names, views, and common queries.
-- Run schema.sql first, then seed.sql.

-- TABLE NAMES
-- users           Accounts and login data
-- interviews      Interview sessions and configuration
-- questions       AI/local questions for each session
-- responses       Candidate answers
-- media_uploads   Audio/video file paths linked to answers
-- evaluations     AI scores and feedback for answers
-- question_bank   Reusable profession/category interview questions

-- VIEW NAMES
-- v_interview_summary   Dashboard and interview history summary
-- v_interview_answers   Questions, answers, scores, and feedback
-- v_pending_questions   Unanswered questions in active sessions
-- v_media_uploads       Uploaded media with interview context
-- v_question_bank_by_role Reusable question-bank view

-- 1. List all tables and views.
SELECT type, name
FROM sqlite_master
WHERE type IN ('table', 'view')
  AND name NOT LIKE 'sqlite_%'
ORDER BY type, name;

-- 1b. Browse questions for one role and category.
SELECT *
FROM v_question_bank_by_role
WHERE job_role = 'Software Engineer'
    AND category = 'behavioral'
ORDER BY difficulty, id
LIMIT 20;

-- 1c. Count question-bank coverage by role and category.
SELECT job_role, category, difficulty, COUNT(*) AS question_count
FROM question_bank
GROUP BY job_role, category, difficulty
ORDER BY job_role, category, difficulty;

-- 2. Dashboard: all sessions for one user.
-- Replace 'seed-user-demo' with the user's id.
SELECT *
FROM v_interview_summary
WHERE user_id = 'seed-user-demo'
ORDER BY started_at DESC;

-- 3. Dashboard: average score and completed interview count.
SELECT
    user_id,
    username,
    COUNT(*) AS total_interviews,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_interviews,
    ROUND(AVG(average_score), 2) AS overall_average_score
FROM v_interview_summary
GROUP BY user_id, username;

-- 4. History page: completed interviews.
SELECT
    interview_id,
    username,
    job_role,
    interview_type,
    question_count,
    responses_submitted,
    average_score,
    completed_at
FROM v_interview_summary
WHERE status = 'completed'
ORDER BY completed_at DESC;

-- 5. Full report for one interview.
-- Replace 'seed-interview-demo' with the interview id.
SELECT *
FROM v_interview_answers
WHERE interview_id = 'seed-interview-demo'
ORDER BY question_number;

-- 6. Find the next unanswered question in an active interview.
SELECT *
FROM v_pending_questions
WHERE interview_id = 'seed-interview-demo'
ORDER BY question_number
LIMIT 1;

-- 7. Review uploaded audio/video files.
SELECT
    media_id,
    username,
    job_role,
    question_number,
    media_type,
    file_path,
    mime_type,
    file_size,
    created_at
FROM v_media_uploads
ORDER BY created_at DESC;

-- 8. Top-performing answers.
SELECT
    interview_id,
    username,
    question_number,
    question_text,
    score,
    feedback
FROM v_interview_answers
WHERE score IS NOT NULL
ORDER BY score DESC, answered_at DESC;

-- 9. Users and their session counts.
SELECT
    u.id AS user_id,
    u.username,
    u.email,
    COUNT(i.id) AS interview_count
FROM users u
LEFT JOIN interviews i ON i.user_id = u.id
GROUP BY u.id, u.username, u.email
ORDER BY interview_count DESC, u.username;

-- 10. Inspect the structure of a table.
-- Change 'interviews' to any table name above.
PRAGMA table_info(interviews);
