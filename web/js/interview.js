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
    
    // TODO: Call API.startSession() here and begin the QUESTION -> ANSWER loop
    startTimer(300); // 5 minutes mock timer
    setupSpeechAndRecording();
}

async function endInterview() {
    clearInterval(interviewTimer);
    document.body.classList.remove('focus-mode');
    isFocusModeActive = false;
    
    // Cleanup Media
    stopMedia();
    saveInterviewSession();
    
    // Simulate API fetch delay for final report
    showScreen('loading-screen'); // Show AI processing animation
    setTimeout(() => {
        showScreen('results-screen');
    }, 2000);
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
