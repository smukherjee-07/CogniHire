/* ==========================================================================
   COGNIHIRE - Live Interview Flow (interview.js)
   ========================================================================== */

let isFocusModeActive = false;
let interviewTimer = null;

async function startInterviewFlow(jobRole, interviewType, questionCount, interviewContext = {}) {
    let serverSession;
    try {
        serverSession = await API.startSession({
            job_role: jobRole,
            interview_type: interviewType,
            question_count: questionCount,
            user_id: currentUser?.id
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to connect to the interview server.';
        window.alert(`${message}. Start the API with: uvicorn app:app --reload`);
        return;
    }

    currentSession = { ...serverSession, role: jobRole, type: interviewType, questions: questionCount, ...interviewContext };
    showScreen('interview-screen');
    
    // Activate Focus Mode UI
    document.body.classList.add('focus-mode');
    isFocusModeActive = true;
    
    // Initialize Media (Camera & Scanner)
    await initMedia();
    
    // Start Background Attire Scan
    triggerAttireScan();

    await loadNextQuestion();
    
    startTimer(300); // 5 minutes mock timer
    setupSpeechAndRecording();
}

async function submitCurrentAnswer() {
    if (!currentSession?.currentQuestionId || !finalTranscript.trim()) return null;
    const response = await API.submitAnswer(currentSession.session_id, currentSession.currentQuestionId, {
        answer_text: finalTranscript.trim(),
        answer_mode: 'text'
    });
    currentSession.lastResponseId = response.response_id;
    return response;
}

async function loadNextQuestion() {
    const question = await API.getNextQuestion(currentSession.session_id);
    currentSession.currentQuestionId = question.question_id;
    questionIndex = question.question_number - 1;
    questionText = question.question;
    const prompt = document.getElementById('question-prompt');
    const transcript = document.getElementById('transcript-text');
    if (prompt) prompt.textContent = `Question ${question.question_number}: ${questionText}`;
    if (transcript) transcript.textContent = 'New question ready. Play question to hear it.';
    finalTranscript = '';
    setAvatarMode('listening');
}

async function endInterview() {
    clearInterval(interviewTimer);
    document.body.classList.remove('focus-mode');
    isFocusModeActive = false;

    try {
        await submitCurrentAnswer();
        const result = await API.getResults(currentSession.session_id);
        currentSession.score = result.ai_evaluation.score;
        currentSession.report = result;
        saveInterviewSession();
        renderReportCard(result.final_result, result.ai_evaluation);
    } catch (error) {
        console.error('Unable to complete interview', error);
        window.alert(error instanceof Error ? error.message : 'Unable to load interview results.');
        return;
    }
    
    // Cleanup Media
    stopMedia();
    showScreen('results-screen');
}

function saveInterviewSession() {
    if (!currentUser || !currentSession) return;
    const key = `cognihire-sessions-${currentUser.username}`;
    const sessions = JSON.parse(localStorage.getItem(key) || '[]');
    sessions.unshift({ ...currentSession, score: 8, date: new Date().toLocaleDateString() });
    localStorage.setItem(key, JSON.stringify(sessions));
}

function startTimer(seconds) {
    let timeLeft = seconds;
    const timerDisplay = document.getElementById('timer-display');
    
    interviewTimer = setInterval(() => {
        if (timeLeft <= 0) {
            endInterview();
        } else {
            let m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
            let s = (timeLeft % 60).toString().padStart(2, '0');
            if (timerDisplay) timerDisplay.textContent = `${m}:${s}`;
            timeLeft--;
        }
    }, 1000);
}
