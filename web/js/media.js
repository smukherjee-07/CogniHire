/* ==========================================================================
   COGNIHIRE - Media & Hardware Controls (media.js)
   ========================================================================== */

let localStream = null;
let microphoneStream = null;
let cameraMessage = 'Camera is not connected.';
let microphoneMessage = 'Microphone has not been initialized.';
let isMicrophoneActive = false;
let mediaRecorder = null;
let recordedChunks = [];
let speechRecognition = null;
let speechRecognitionSupported = false;
let recognitionShouldRun = false;
let recognitionIsRunning = false;
let recognitionStartPending = false;
let recognitionStopRequested = false;
let recognitionStopResolver = null;
let recognitionStopTimeout = null;
let recognitionRestartTimer = null;
let recognitionRestartAttempts = 0;
const RECOGNITION_RESTART_DELAY_MS = 300;
let finalTranscript = '';
let speechDraft = '';
let questionIndex = 0;
let questionText = 'Tell me about a project you are proud of.';
const questionBank = [
    'Tell me about a project you are proud of.',
    'What challenge did you face, and how did you solve it?',
    'What would you improve if you worked on that project again?'
];

async function initMedia() {
    if (!navigator.mediaDevices?.getUserMedia) {
        const message = window.isSecureContext
            ? 'This browser does not support camera or microphone access.'
            : 'Camera and microphone access require localhost or HTTPS.';
        cameraMessage = message;
        microphoneMessage = message;
        logMediaEvent('getUserMedia unavailable', { secureContext: window.isSecureContext });
        updateMediaStatus(message, true);
        return false;
    }

    const errors = [];
    let cameraReady = false;
    let microphoneReady = false;
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        const videoElement = document.getElementById('candidate-video');
        if (videoElement) {
            videoElement.srcObject = localStream;
            try {
                await videoElement.play();
            } catch (error) {
                logMediaEvent('video playback blocked', { name: error.name, message: error.message });
            }
        }
        cameraReady = true;
        cameraMessage = 'Camera connected.';
        logMediaEvent('camera stream started', { tracks: localStream.getTracks().map(track => track.kind) });
    } catch (error) {
        const detail = mediaDeviceErrorMessage(error, 'camera');
        cameraMessage = detail;
        errors.push(detail);
        logMediaEvent('camera initialization failed', { name: error.name, message: error.message });
    }

    try {
        logMediaEvent('microphone permission requested during interview initialization');
        microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        const audioTracks = microphoneStream.getAudioTracks();
        if (!audioTracks.length) throw new Error('Microphone stream contains no audio track.');
        audioTracks.forEach(track => { track.enabled = true; });
        microphoneReady = true;
        microphoneMessage = 'Microphone connected.';
        logMediaEvent('microphone stream started', {
            tracks: audioTracks.map(track => ({ kind: track.kind, state: track.readyState, enabled: track.enabled }))
        });
    } catch (error) {
        microphoneMessage = mediaDeviceErrorMessage(error, 'microphone');
        errors.push(microphoneMessage);
        logMediaEvent('microphone initialization failed', { name: error.name, message: error.message });
    }

    if (cameraReady && microphoneReady) {
        updateMediaStatus('Camera and microphone connected. Press Start listening to answer.', false);
    } else if (cameraReady) {
        updateMediaStatus(`Camera connected. ${microphoneMessage} Speech recognition can still request microphone access when started.`, true);
    } else if (microphoneReady) {
        updateMediaStatus(`Camera unavailable. ${cameraMessage} Microphone connected.`, true);
    } else {
        updateMediaStatus(errors.join(' ') || 'Camera and microphone could not be initialized.', true);
    }
    return cameraReady || microphoneReady;
}

function mediaDeviceErrorMessage(error, device) {
    const label = device === 'camera' ? 'Camera' : 'Microphone';
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError' || error.name === 'SecurityError') {
        return `${label} permission was denied. Allow access in browser settings and retry.`;
    }
    if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        return device === 'microphone'
            ? 'No microphone was detected. Connect a microphone and retry.'
            : 'No camera was detected. Connect a camera and retry.';
    }
    if (error.name === 'AbortError') {
        return `${label} access was interrupted before it could start. Retry, and close other apps if the problem continues.`;
    }
    if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        return `The ${device} is already in use or could not be opened. Close other apps using it and retry.`;
    }
    if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
        return `The available ${device} does not meet the browser's requirements.`;
    }
    return `${label} could not be started (${error.name || 'unknown error'}). Check browser permissions and device availability, then retry.`;
}

function logMediaEvent(message, details = {}) {
    const isDevelopment = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
    if (isDevelopment) console.info(`[CogniHire media] ${message}`, details);
}

function getSpeechRecognitionEnvironment() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    return {
        supported: Boolean(Recognition),
        online: navigator.onLine,
        secureContext: window.isSecureContext,
        protocol: window.location.protocol,
        hostname: window.location.hostname,
        userAgent: navigator.userAgent
    };
}

function captureAttireFrame() {
    const video = document.getElementById('candidate-video');
    if (!video?.videoWidth || !video.videoHeight) return null;
    const scale = Math.min(1, 960 / video.videoWidth);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.75);
}

function startAudioVisualizer() {
    isMicrophoneActive = true;
    const bars = document.querySelectorAll('.bar');
    // Simple CSS animation toggle based on mic state
    bars.forEach(bar => bar.classList.add('active'));
}

function stopAudioVisualizer() {
    isMicrophoneActive = false;
    document.querySelectorAll('.bar').forEach(bar => bar.classList.remove('active'));
}

async function stopMedia() {
    if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
    await stopAnswerListening();
    if (speechRecognition) {
        speechRecognition.onstart = null;
        speechRecognition.onresult = null;
        speechRecognition.onerror = null;
        speechRecognition.onend = null;
        speechRecognition = null;
        speechRecognitionSupported = false;
    }
    [localStream, microphoneStream].forEach(stream => {
        stream?.getTracks().forEach(track => track.stop());
    });
    const videoElement = document.getElementById('candidate-video');
    if (videoElement) videoElement.srcObject = null;
    localStream = null;
    microphoneStream = null;
    stopAudioVisualizer();
    stopQuestionSpeech();
}

function setupSpeechAndRecording() {
    if (speechRecognition) {
        logMediaEvent('SpeechRecognition setup skipped; instance already exists');
        return;
    }
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
    speechRecognitionSupported = Boolean(Recognition);
    const speechEnvironment = getSpeechRecognitionEnvironment();
    console.log('[CogniHire] Speech recognition environment:', speechEnvironment);
    setAvatarMode('listening');
    if (Recognition) {
        speechRecognition = new Recognition();
        speechRecognition.continuous = false;
        speechRecognition.interimResults = true;
        speechRecognition.lang = 'en-US';
        logMediaEvent('SpeechRecognition initialized', {
            language: speechRecognition.lang,
            continuous: speechRecognition.continuous,
            interimResults: speechRecognition.interimResults
        });
        speechRecognition.onresult = (event) => {
            console.log('[CogniHire] Speech recognition result received:', event);
            let interimTranscript = '';
            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const result = event.results[index];
                if (result.isFinal) finalTranscript += `${result[0].transcript} `;
                else interimTranscript += result[0].transcript;
            }
            const answerInput = document.getElementById('answer-input');
            const recognizedText = `${finalTranscript}${interimTranscript}`.trim();
            if (answerInput && (!answerInput.value || answerInput.value === speechDraft)) {
                answerInput.value = recognizedText;
                speechDraft = recognizedText;
            }
            if (transcript) transcript.textContent = recognizedText || 'Listening...';
            if (interimTranscript || recognizedText) {
                updateMediaStatus(`${cameraMessage} Speech transcript received.`, cameraMessage !== 'Camera connected.');
            }
            logMediaEvent('speech recognition result', {
                finalCharacterCount: finalTranscript.trim().length,
                interimCharacterCount: interimTranscript.length
            });
        };
        speechRecognition.onstart = () => {
            recognitionStartPending = false;
            recognitionIsRunning = true;
            console.log('[CogniHire] Speech recognition started.');
            logMediaEvent('speech recognition started');
            if (recognitionStopRequested || !recognitionShouldRun) {
                recognitionStopRequested = false;
                try {
                    speechRecognition.stop();
                } catch (error) {
                    recognitionIsRunning = false;
                    logMediaEvent('speech recognition stop after pending start failed', { name: error.name, message: error.message });
                    if (recognitionStopResolver) recognitionStopResolver();
                }
                return;
            }
            startAudioVisualizer();
            updateAnswerControls('listening');
        };
        speechRecognition.onend = () => {
            recognitionIsRunning = false;
            recognitionStartPending = false;
            recognitionStopRequested = false;
            console.log('[CogniHire] Speech recognition ended.', {
                recognitionShouldRun,
                recognitionIsRunning
            });
            logMediaEvent('SpeechRecognition ended', {
                shouldRun: recognitionShouldRun,
                isRunning: recognitionIsRunning,
                finalCharacterCount: finalTranscript.trim().length,
                restartAttempts: recognitionRestartAttempts
            });
            if (recognitionStopResolver) recognitionStopResolver();
            if (recognitionShouldRun) restartSpeechRecognition();
            else {
                updateAnswerControls('stopped');
                if (mediaRecorder?.state !== 'recording') stopAudioVisualizer();
            }
        };
        speechRecognition.onerror = (event) => {
            recognitionIsRunning = false;
            recognitionStartPending = false;
            const keepListeningForRetry =
                event.error === 'no-speech' && recognitionShouldRun;
            if (!keepListeningForRetry) {
                recognitionShouldRun = false;
                cancelRecognitionRestart();
            }
            updateAnswerControls('stopped');
            logMediaEvent('SpeechRecognition error', {
                error: event.error,
                message: event.message,
                shouldRun: recognitionShouldRun,
                isRunning: recognitionIsRunning
            });
            const messages = {
                'not-allowed': 'Microphone permission was denied. Allow microphone access, then retry or type your answer.',
                'service-not-allowed': 'The browser blocked speech recognition. Check microphone and speech permissions, then retry.',
                'audio-capture': 'The speech engine could not capture audio. Check that your microphone is connected, enabled, and not being used exclusively by another application, then retry or type your answer.',
                'no-speech': 'No speech was detected. Press Start listening to retry, or type your answer.',
                network: 'Browser speech recognition is unavailable. Check your internet connection and browser speech permissions, then press Start listening again. You can also type your answer.',
                aborted: 'Speech recognition was stopped. Press Start listening to retry, or type your answer.',
                'language-not-supported': 'Speech recognition does not support the configured language in this browser.',
                'bad-grammar': 'Speech recognition could not process this answer. Press Start listening to retry.'
            };
            updateMediaStatus(messages[event.error] || `Speech recognition failed (${event.error}). Press Start listening to retry, or type your answer.`, true);
            if (mediaRecorder?.state !== 'recording') stopAudioVisualizer();
        };
        const mediaError = cameraMessage !== 'Camera connected.' || microphoneMessage !== 'Microphone connected.';
        updateMediaStatus(`${cameraMessage} ${microphoneMessage} Press Start listening to speak, or type your answer below.`, mediaError);
    } else {
        logMediaEvent('speech recognition unsupported');
        updateMediaStatus(`${cameraMessage} ${microphoneMessage} Voice recognition is unavailable in this browser. Type your answer below instead.`, true);
    }
    speakButton.onclick = speakQuestion;
    pauseQuestionButton.onclick = pauseQuestionSpeech;
    stopQuestionButton.onclick = stopQuestionSpeech;
    listenButton.onclick = startAnswerListening;
    pauseAnswerButton.onclick = pauseAnswerListening;
    continueAnswerButton.onclick = continueAnswerListening;
    retryAnswerButton.onclick = retryAnswer;
    nextQuestionButton.onclick = nextQuestion;
    recordButton.onclick = async () => {
        if (!microphoneStream && navigator.mediaDevices?.getUserMedia) {
            logMediaEvent('recording microphone permission requested');
            try {
                microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                logMediaEvent('recording microphone stream started', { tracks: microphoneStream.getTracks().map(track => track.kind) });
            } catch (error) {
                logMediaEvent('recording microphone initialization failed', { name: error.name, message: error.message });
                updateMediaStatus(mediaDeviceErrorMessage(error, 'microphone'), true);
                return;
            }
        }
        const tracks = [
            ...(localStream?.getVideoTracks() || []),
            ...(microphoneStream?.getAudioTracks() || [])
        ];
        if (!tracks.length || !window.MediaRecorder) {
            updateMediaStatus('Recording is unavailable because no media device is active.', true);
            return;
        }
        if (mediaRecorder?.state === 'recording') { mediaRecorder.stop(); recordButton.textContent = 'Start recording'; return; }
        recordedChunks = [];
        mediaRecorder = new MediaRecorder(new MediaStream(tracks));
        mediaRecorder.ondataavailable = (event) => recordedChunks.push(event.data);
        mediaRecorder.onstop = () => {
            if (!recognitionIsRunning) stopAudioVisualizer();
        };
        mediaRecorder.start();
        startAudioVisualizer();
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

function cancelRecognitionRestart() {
    if (recognitionRestartTimer !== null) {
        window.clearTimeout(recognitionRestartTimer);
        recognitionRestartTimer = null;
    }
}

function restartSpeechRecognition() {
    if (!recognitionShouldRun || recognitionIsRunning || recognitionStartPending || recognitionRestartTimer !== null) return;

    recognitionRestartAttempts += 1;
    const delay = Math.min(RECOGNITION_RESTART_DELAY_MS * (2 ** (recognitionRestartAttempts - 1)), 2400);
    logMediaEvent('SpeechRecognition restart scheduled', {
        delay,
        attempt: recognitionRestartAttempts,
        shouldRun: recognitionShouldRun,
        isRunning: recognitionIsRunning
    });
    recognitionRestartTimer = window.setTimeout(() => {
        recognitionRestartTimer = null;
        if (!recognitionShouldRun || recognitionIsRunning || recognitionStartPending) return;
        startAnswerListening(true);
    }, delay);
}

function startAnswerListening(isAutomaticRestart = false) {
    if (!speechRecognitionSupported || !speechRecognition) {
        updateMediaStatus('Speech recognition is unavailable. Type your answer below.', true);
        return;
    }
    if (recognitionIsRunning || recognitionStartPending) return;
    if (isAutomaticRestart) {
        if (!recognitionShouldRun) return;
    } else {
        cancelRecognitionRestart();
        recognitionRestartAttempts = 0;
        recognitionShouldRun = true;
    }

    recognitionStopRequested = false;
    recognitionStartPending = true;
    logMediaEvent('SpeechRecognition start requested', {
        shouldRun: recognitionShouldRun,
        isRunning: recognitionIsRunning,
        language: speechRecognition.lang,
        continuous: speechRecognition.continuous,
        interimResults: speechRecognition.interimResults,
        automaticRestart: isAutomaticRestart
    });
    try {
        console.log('[CogniHire] Starting SpeechRecognition.', {
            isAutomaticRestart,
            online: navigator.onLine,
            secureContext: window.isSecureContext,
            protocol: window.location.protocol,
            hostname: window.location.hostname
        });
        speechRecognition.start();
    } catch (error) {
        recognitionStartPending = false;
        logMediaEvent('SpeechRecognition start failed', {
            name: error.name,
            message: error.message,
            automaticRestart: isAutomaticRestart
        });
        if (error.name === 'InvalidStateError') {
            recognitionIsRunning = true;
            logMediaEvent('SpeechRecognition start ignored because a session is already active');
            return;
        }
        recognitionIsRunning = false;
        recognitionShouldRun = false;
        updateAnswerControls('stopped');
        updateMediaStatus(`Speech recognition could not start: ${error.message}. Check microphone permission and retry.`, true);
    }
}

function pauseAnswerListening() {
    recognitionShouldRun = false;
    void stopAnswerListening();
}

function continueAnswerListening() {
    updateMediaStatus('Continuing answer listening.', false);
    startAnswerListening();
}

function stopAnswerListening() {
    recognitionShouldRun = false;
    cancelRecognitionRestart();
    updateAnswerControls('stopped');
    if (!speechRecognition || (!recognitionIsRunning && !recognitionStartPending)) return Promise.resolve();
    return new Promise(resolve => {
        let settled = false;
        const finish = () => {
            if (settled) return;
            settled = true;
            window.clearTimeout(recognitionStopTimeout);
            recognitionStopTimeout = null;
            recognitionStopResolver = null;
            resolve();
        };
        recognitionStopResolver = finish;
        recognitionStopTimeout = window.setTimeout(() => {
            logMediaEvent('SpeechRecognition stop timed out; aborting pending session');
            recognitionIsRunning = false;
            recognitionStartPending = false;
            recognitionStopRequested = false;
            try {
                speechRecognition.abort();
            } catch (error) {
                logMediaEvent('SpeechRecognition abort after stop timeout failed', { name: error.name, message: error.message });
            }
            finish();
        }, 2500);
        if (recognitionStartPending && !recognitionIsRunning) {
            recognitionStopRequested = true;
            return;
        }
        try {
            speechRecognition.stop();
        } catch (error) {
            recognitionIsRunning = false;
            recognitionStartPending = false;
            recognitionStopRequested = false;
            logMediaEvent('speech recognition stop failed', { name: error.name, message: error.message });
            finish();
        }
    });
}

async function retryAnswer() {
    await stopAnswerListening();
    finalTranscript = '';
    speechDraft = '';
    const transcript = document.getElementById('transcript-text');
    const answerInput = document.getElementById('answer-input');
    if (transcript) transcript.textContent = 'Your answer was cleared. Press Start listening to try again.';
    if (answerInput) answerInput.value = '';
    stopAnswerListening();
}

async function nextQuestion() {
    await stopAnswerListening();
    stopQuestionSpeech();
    const answerText = getCurrentAnswerText();
    try {
        await submitCurrentAnswer(answerText);
        await loadNextQuestion();
        updateMediaStatus(answerText ? 'Next question ready.' : 'Question skipped. Next question ready.', false);
    } catch (error) {
        if (error instanceof Error && error.message.includes('(404)')) {
            await endInterview();
            return;
        }
        updateMediaStatus(error instanceof Error ? error.message : 'Unable to load the next question.', true);
    }
}

function getCurrentAnswerText() {
    const typedAnswer = document.getElementById('answer-input')?.value.trim() || '';
    if (typedAnswer && speechDraft && typedAnswer.startsWith(speechDraft)) return typedAnswer;
    return [finalTranscript.trim(), typedAnswer].filter(Boolean).join('\n');
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
