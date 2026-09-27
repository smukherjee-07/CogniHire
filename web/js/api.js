/* ==========================================================================
   COGNIHIRE - API Contract & Communication (api.js)
   ========================================================================== */

const API_BASE_URL = 'http://localhost:8000/api'; // Update to your backend URL

const API = {
    // 1. Initialize Session
    async startSession(config) {
        // Enforcing config variables: interview_type, job_role, question_count
        const response = await fetch(`${API_BASE_URL}/interviews`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        if (!response.ok) throw new Error(`Unable to start interview (${response.status})`);
        return await response.json(); // Returns SESSION object (session_id, etc.)
    },

    // 2. Fetch Next Question
    async getNextQuestion(session_id) {
        const response = await fetch(`${API_BASE_URL}/interviews/${session_id}/next-question`);
        if (!response.ok) throw new Error(`Unable to load question (${response.status})`);
        return await response.json(); // Returns QUESTION object
    },

    // 3. Submit Answer
    async submitAnswer(session_id, question_id, answerData) {
        // Enforcing ANSWER variables: answer_text, answer_mode, audio_file_path, video_file_path
        const response = await fetch(`${API_BASE_URL}/interviews/${session_id}/responses`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question_id: question_id,
                ...answerData
            })
        });
        if (!response.ok) throw new Error(`Unable to save response (${response.status})`);
        return await response.json();
    },

    // 4. Get Final Results
    async getResults(session_id) {
        const response = await fetch(`${API_BASE_URL}/interviews/${session_id}/results`);
        if (!response.ok) throw new Error(`Unable to load results (${response.status})`);
        // Returns aggregated FINAL RESULT and AI EVALUATION objects
        return await response.json();
    }
};
