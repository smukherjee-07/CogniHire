/* ==========================================================================
   COGNIHIRE - Media & Hardware Controls (media.js)
   ========================================================================== */

let localStream = null;
let isAnalyzingAttire = false;
let isMicrophoneActive = false;
let mediaRecorder = null;
let recordedChunks = [];
let speechRecognition = null;
let speechRecognitionSupported = false;
let recognitionShouldRun = false;
let recognitionIsRunning = false;
let finalTranscript = '';
let questionIndex = 0;
let questionText = 'Tell me about a project you are proud of.';
const questionBank = [
    'Tell me about a project you are proud of.',
    'What challenge did you face, and how did you solve it?',
    'What would you improve if you worked on that project again?'
];

async function initMedia() {
    const status = document.getElementById('media-status');
    if (!navigator.mediaDevices?.getUserMedia) {
        updateMediaStatus('Camera and microphone require localhost or HTTPS.', true);
        return false;
    }
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        const videoElement = document.getElementById('candidate-video');
        if (videoElement) {
            videoElement.srcObject = localStream;
        }
        
        // Start audio visualizer simulation
        startAudioVisualizer();
        updateMediaStatus('Camera and microphone connected.', false);
        return true;
    } catch (error) {
        console.error("Camera/Mic access denied", error);
        updateMediaStatus('Camera or microphone permission is blocked. Allow access and try again.', true);
        return false;
    }
}

function triggerAttireScan() {
    isAnalyzingAttire = true;
    const scanner = document.getElementById('attire-scanner');
    if (scanner) {
        scanner.style.display = 'block';
        // Simulate scan completion after 3.5s
        setTimeout(() => {
            scanner.style.display = 'none';
            isAnalyzingAttire = false;
        }, 3500);
    }
}

function startAudioVisualizer() {
    isMicrophoneActive = true;
    const bars = document.querySelectorAll('.bar');
    // Simple CSS animation toggle based on mic state
    bars.forEach(bar => bar.classList.add('active'));
}

function stopMedia() {
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
    }
    document.querySelectorAll('.bar').forEach(bar => bar.classList.remove('active'));
    isMicrophoneActive = false;
    stopAnswerListening();
    stopQuestionSpeech();
}

function setupSpeechAndRecording() {
    const speakButton = document.getElementById('speak-question-btn');
    const pauseQuestionButton = document.getElementById('pause-question-btn');
    const stopQuestionButton = document.getElementById('stop-question-btn');
    const listenButton = document.getElementById('listen-answer-btn');
    const pauseAnswerButton = document.getElementById('pause-answer-btn');
    const continueAnswerButton = document.getElementById('continue-answer-btn');
    const retryAnswerButton = document.getElementById('retry-answer-btn');
    const nextQuestionButton = document.getElementById('next-question-btn');
    const recordButton = document.getElementById('record-btn');
    const transcript = document.getElementById('transcript-text');
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    setAvatarMode('listening');
    speechRecognitionSupported = Boolean(Recognition);
    if (Recognition) {
        speechRecognition = new Recognition();
        speechRecognition.continuous = false;
        speechRecognition.interimResults = true;
        speechRecognition.lang = 'en-US';
        speechRecognition.onresult = (event) => {
            let interimTranscript = '';
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const result = event.results[index];
                if (result.isFinal) finalTranscript += `${result[0].transcript} `;
                else interimTranscript += result[0].transcript;
            }
            transcript.textContent = `${finalTranscript}${interimTranscript}`.trim() || 'Listening...';
        };
        speechRecognition.onstart = () => { recognitionIsRunning = true; updateAnswerControls('listening'); };
        speechRecognition.onend = () => {
            recognitionIsRunning = false;
            if (recognitionShouldRun) window.setTimeout(startAnswerListening, 100);
            else updateAnswerControls('stopped');
        };
        speechRecognition.onerror = (event) => {
            recognitionIsRunning = false;
            if (event.error !== 'aborted' && event.error !== 'no-speech') updateMediaStatus(`Speech recognition: ${event.error}. Press Start listening to retry.`, true);
        };
        updateMediaStatus('Camera and microphone connected. Press Start listening to answer.', false);
    } else {
        updateMediaStatus('Voice recognition is not supported in this browser. Use Chrome or Edge.', true);
    }
    speakButton.onclick = speakQuestion;
    pauseQuestionButton.onclick = pauseQuestionSpeech;
    stopQuestionButton.onclick = stopQuestionSpeech;
    listenButton.onclick = startAnswerListening;
    pauseAnswerButton.onclick = pauseAnswerListening;
    continueAnswerButton.onclick = continueAnswerListening;
    retryAnswerButton.onclick = retryAnswer;
    nextQuestionButton.onclick = nextQuestion;
    recordButton.onclick = () => {
        if (!localStream || !window.MediaRecorder) return;
        if (mediaRecorder?.state === 'recording') { mediaRecorder.stop(); recordButton.textContent = 'Start recording'; return; }
        recordedChunks = [];
        mediaRecorder = new MediaRecorder(localStream);
        mediaRecorder.ondataavailable = (event) => recordedChunks.push(event.data);
        mediaRecorder.start();
        recordButton.textContent = 'Stop recording';
    };
}

function speakQuestion() {
    if (!('speechSynthesis' in window)) { updateMediaStatus('Text-to-speech is not supported in this browser.', true); return; }
    speechSynthesis.cancel();
    setAvatarMode('speaking');
    const utterance = new SpeechSynthesisUtterance(questionText);
    utterance.lang = 'en-US';
    utterance.onstart = () => updateMediaStatus('Question is speaking.', false);
    utterance.onend = () => { setAvatarMode('listening'); updateMediaStatus('Question finished. Press Start listening to answer.', false); };
    utterance.onerror = () => setAvatarMode('listening');
    speechSynthesis.speak(utterance);
}

function pauseQuestionSpeech() {
    if ('speechSynthesis' in window && speechSynthesis.speaking) speechSynthesis.pause();
}

function stopQuestionSpeech() {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    setAvatarMode('listening');
}

function setAvatarMode(mode) {
    const speakingAvatar = document.getElementById('speaking-avatar');
    const listeningAvatar = document.getElementById('listening-avatar');
    if (!speakingAvatar || !listeningAvatar) return;
    const isSpeaking = mode === 'speaking';
    speakingAvatar.classList.toggle('avatar-visible', isSpeaking);
    listeningAvatar.classList.toggle('avatar-visible', !isSpeaking);
    if (isSpeaking) {
        listeningAvatar.pause();
        speakingAvatar.currentTime = 0;
        speakingAvatar.play().catch(() => {});
    } else {
        speakingAvatar.pause();
        listeningAvatar.play().catch(() => {});
    }
}

function startAnswerListening() {
    if (!speechRecognitionSupported || !speechRecognition || recognitionIsRunning) return;
    recognitionShouldRun = true;
    try { speechRecognition.start(); } catch (error) { if (error.name !== 'InvalidStateError') console.error(error); }
}

function pauseAnswerListening() {
    recognitionShouldRun = false;
    if (recognitionIsRunning) speechRecognition.stop();
}

function continueAnswerListening() {
    updateMediaStatus('Continuing answer listening.', false);
    startAnswerListening();
}

function stopAnswerListening() {
    recognitionShouldRun = false;
    if (speechRecognition && recognitionIsRunning) speechRecognition.stop();
    recognitionIsRunning = false;
    updateAnswerControls('stopped');
}

function retryAnswer() {
    finalTranscript = '';
    const transcript = document.getElementById('transcript-text');
    if (transcript) transcript.textContent = 'Your answer was cleared. Press Start listening to try again.';
    stopAnswerListening();
    window.setTimeout(startAnswerListening, 120);
}

async function nextQuestion() {
    stopAnswerListening();
    stopQuestionSpeech();
    try {
        await submitCurrentAnswer();
        await loadNextQuestion();
        updateMediaStatus('Next question ready.', false);
    } catch (error) {
        if (error instanceof Error && error.message.includes('(404)')) {
            await endInterview();
            return;
        }
        updateMediaStatus(error instanceof Error ? error.message : 'Unable to load the next question.', true);
    }
}

function updateAnswerControls(state) {
    const listenButton = document.getElementById('listen-answer-btn');
    if (!listenButton) return;
    listenButton.textContent = state === 'listening' ? 'Listening...' : 'Start listening';
    listenButton.classList.toggle('active-control', state === 'listening');
}

function updateMediaStatus(message, isError) {
    const status = document.getElementById('media-status');
    if (status) {
        status.textContent = message;
        status.classList.toggle('media-error', isError);
    }
}
