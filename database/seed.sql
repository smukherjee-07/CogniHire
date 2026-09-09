-- Local development seed. Demo login: demo / demo1234

INSERT OR IGNORE INTO users (id, username, email, password_hash)
VALUES (
	'seed-user-demo',
	'demo',
	'demo@cognihire.local',
	'pbkdf2_sha256$cognihire-demo$9ea5a9d997dfb18b4e611510df6b32a0d6017f6e29f9cfe01cdbf2606d16e458'
);

INSERT OR IGNORE INTO interviews (
	id, user_id, job_role, interview_type, experience_level, question_count, status, completed_at
)
VALUES (
	'seed-interview-demo',
	'seed-user-demo',
	'Software Engineer',
	'technical',
	'mid',
	2,
	'completed',
	CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO questions (id, interview_id, question_number, question_text, source)
VALUES
	('seed-question-1', 'seed-interview-demo', 1, 'How do you design a maintainable API?', 'seed'),
	('seed-question-2', 'seed-interview-demo', 2, 'Describe a difficult bug you fixed and how you found its cause.', 'seed');

INSERT OR IGNORE INTO responses (id, interview_id, question_id, answer_text, answer_mode)
VALUES
	('seed-response-1', 'seed-interview-demo', 'seed-question-1', 'I start with clear resource boundaries, validation, consistent errors, and tests.', 'text'),
	('seed-response-2', 'seed-interview-demo', 'seed-question-2', 'I reproduce the issue, narrow it with logs and tests, then fix the smallest responsible change.', 'text');

INSERT OR IGNORE INTO media_uploads (id, response_id, media_type, file_path, mime_type)
VALUES
	('seed-media-audio-1', 'seed-response-1', 'audio', 'data/audio/demo-response-1.webm', 'audio/webm'),
	('seed-media-video-1', 'seed-response-1', 'video', 'data/video/demo-response-1.webm', 'video/webm');

INSERT OR IGNORE INTO evaluations (
	id, response_id, score, strengths_json, weaknesses_json, feedback, recommendation
)
VALUES
	(
		'seed-evaluation-1',
		'seed-response-1',
		8.5,
		'["Good API structure", "Mentions validation and tests"]',
		'["Could explain versioning in more detail"]',
		'A clear and practical answer with strong engineering fundamentals.',
		'Add a concrete example of API versioning.'
	),
	(
		'seed-evaluation-2',
		'seed-response-2',
		8.0,
		'["Uses a systematic debugging process"]',
		'["Could mention monitoring or rollback"]',
		'The answer shows a disciplined approach to troubleshooting.',
		'Include the production safety step used after the fix.'
	);
