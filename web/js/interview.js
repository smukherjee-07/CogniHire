/* ==========================================================================
   COGNIHIRE - Live Interview Flow (interview.js)
   ========================================================================== */

let isFocusModeActive = false;
let interviewTimer = null;
let isEndingInterview = false;

async function startInterviewFlow(jobRole, interviewType, questionCount, interviewContext = {}) {
    isEndingInterview = false;
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

    const actualQuestionCount = serverSession.questions?.length
        ?? serverSession.interview?.question_count
        ?? questionCount;
    currentSession = { ...serverSession, role: jobRole, type: interviewType, questions: actualQuestionCount, ...interviewContext };
    showScreen('interview-screen');
    
    // Activate Focus Mode UI
    document.body.classList.add('focus-mode');
    isFocusModeActive = true;
    
    // Initialize Media (Camera & Scanner)
    await initMedia();
    
    await loadNextQuestion();
    
    startTimer(300); // 5 minutes mock timer
    setupSpeechAndRecording();
}

async function submitCurrentAnswer(answerText = getCurrentAnswerText()) {
    if (!currentSession?.currentQuestionId
        || currentSession.lastSubmittedQuestionId === currentSession.currentQuestionId) return null;
    const submittedAnswer = typeof answerText === 'string' ? answerText.trim() : '';
    logMediaEvent('submitting answer', {
        questionId: currentSession.currentQuestionId,
        characterCount: submittedAnswer.length
    });
    const response = await API.submitAnswer(currentSession.session_id, currentSession.currentQuestionId, {
        answer_text: submittedAnswer,
        answer_mode: 'text',
        skipped: !submittedAnswer
    });
    currentSession.lastResponseId = response.response_id;
    currentSession.lastSubmittedQuestionId = currentSession.currentQuestionId;
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
    const answerInput = document.getElementById('answer-input');
    if (answerInput) answerInput.value = '';
    finalTranscript = '';
    speechDraft = '';
    setAvatarMode('listening');
}

async function endInterview() {
    if (isEndingInterview) return;
    isEndingInterview = true;
    const endButton = document.getElementById('end-interview-btn');
    if (endButton) {
        endButton.disabled = true;
        endButton.textContent = 'Submitting...';
    }
    clearInterval(interviewTimer);
    document.body.classList.remove('focus-mode');
    isFocusModeActive = false;

    try {
        await stopAnswerListening();
        await submitCurrentAnswer();
        let attireEvaluation = null;
        const cameraFrame = captureAttireFrame();
        showScreen('loading-screen');
        const attireRequest = cameraFrame
            ? API.evaluatePresence(currentSession.session_id, cameraFrame).catch(() => ({
                feedback: 'Attire review is unavailable. Check Gemini configuration and try again.'
            }))
            : Promise.resolve({ feedback: 'Attire was not assessed because no camera image was available.' });
        const [result, presence] = await Promise.all([
            API.getResults(currentSession.session_id),
            attireRequest
        ]);
        attireEvaluation = presence;
        currentSession.score = result.ai_evaluation.score;
        result.ai_evaluation.presence = attireEvaluation;
        currentSession.report = result;
        saveInterviewSession();
        renderReportCard(result.final_result, result.ai_evaluation);
    } catch (error) {
        console.error('Unable to complete interview', error);
        showScreen('interview-screen');
        isEndingInterview = false;
        if (endButton) {
            endButton.disabled = false;
            endButton.textContent = 'End & Submit';
        }
        window.alert(error instanceof Error ? error.message : 'Unable to load interview results.');
        return;
    }
    
    // Cleanup Media
    await stopMedia();
    showScreen('results-screen');
}

function saveInterviewSession() {
    if (!currentUser || !currentSession) return;
    const key = `cognihire-sessions-${currentUser.username}`;
    const sessions = JSON.parse(localStorage.getItem(key) || '[]');
    sessions.unshift({ ...currentSession, date: new Date().toLocaleDateString() });
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
