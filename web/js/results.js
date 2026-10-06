/* ==========================================================================
   COGNIHIRE - All-At-The-End Report Card (results.js)
   ========================================================================== */

let activeReportTab = 'performance'; // default

function switchTab(tabId) {
    activeReportTab = tabId;
    
    // Update Button Styling
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[onclick="switchTab('${tabId}')"]`)?.classList.add('active');

    // Update Pane Visibility
    document.querySelectorAll('.tab-content').forEach(pane => {
        pane.classList.remove('active');
    });
    const targetPane = document.getElementById(`pane-${tabId}`);
    if (targetPane) {
        targetPane.classList.add('active');
    }
}

function evaluationItems(value) {
    if (typeof value === 'string') {
        try {
            value = JSON.parse(value);
        } catch {
            return value.trim() ? [value.trim()] : [];
        }
    }
    if (!Array.isArray(value)) return [];
    return value.map(item => String(item).trim()).filter(Boolean);
}

function renderEvaluationItems(elementId, items, emptyMessage) {
    const list = document.getElementById(elementId);
    if (!list) return;
    list.replaceChildren();
    const displayedItems = items.length ? items : [emptyMessage];
    displayedItems.forEach(item => {
        const listItem = document.createElement('li');
        listItem.textContent = item;
        list.appendChild(listItem);
    });
}

// Function to parse the FINAL RESULT and AI EVALUATION objects from backend
function renderReportCard(finalResultData, aiEvaluationData) {
    // Populate Overall Score from the backend result.
    const scoreElement = document.getElementById('overall-score');
    if (scoreElement) {
        const score = Number(aiEvaluationData?.score ?? finalResultData?.score);
        scoreElement.textContent = Number.isFinite(score) ? `${score}/10` : '--/10';
    }

    const responses = aiEvaluationData?.responses ?? finalResultData?.responses ?? [];
    const strengths = [
        ...evaluationItems(aiEvaluationData?.strengths),
        ...responses.flatMap(response => evaluationItems(response.strengths_json ?? response.strengths))
    ];
    const weaknesses = [
        ...evaluationItems(aiEvaluationData?.weaknesses),
        ...responses.flatMap(response => evaluationItems(response.weaknesses_json ?? response.weaknesses))
    ];
    renderEvaluationItems('report-strengths', [...new Set(strengths)], 'No strengths were returned by the evaluation.');
    renderEvaluationItems('report-weaknesses', [...new Set(weaknesses)], 'No areas for improvement were returned by the evaluation.');

    const responseList = document.getElementById('report-responses');
    if (responseList) {
        responseList.replaceChildren();
        responses.forEach((response, index) => {
            if (['localhost', '127.0.0.1'].includes(window.location.hostname)) {
                const source = response.evaluation_source === 'demo_fallback' ? 'DEMO_FALLBACK' : 'Gemini';
                console.info(`[CogniHire review] Question ${response.question_number ?? index + 1}: ${source}`);
            }
            const item = document.createElement('section');
            item.className = 'response-review-item';
            const heading = document.createElement('h3');
            heading.textContent = `Question ${response.question_number ?? index + 1}: ${response.question_text || 'Interview question'}`;
            item.appendChild(heading);
            if (response.score !== null && response.score !== undefined) {
                item.appendChild(responseTextBlock(
                    'Score',
                    `${response.score}/10${['local', 'ai_unavailable', 'demo_fallback'].includes(response.evaluation_source) ? ' (local estimate)' : ''}`,
                    'response-review-answer'
                ));
            }
            const answerText = typeof response.answer_text === 'string' ? response.answer_text.trim() : '';
            item.appendChild(responseTextBlock(
                'Candidate Answer',
                answerText || 'No answer provided.',
                'response-review-answer'
            ));
            item.appendChild(responseTextBlock(
                'Ideal Answer',
                response.ideal_answer || (response.evaluation_source === 'ai_unavailable'
                    ? 'Gemini could not generate an ideal answer for this question.'
                    : 'No ideal answer was returned for this question.'),
                'response-review-suggestion'
            ));
            const strengths = evaluationItems(response.strengths_json ?? response.strengths);
            const weaknesses = evaluationItems(response.weaknesses_json ?? response.weaknesses);
            const unanswered = !answerText;
            const hasReviewData = Boolean(
                response.score !== null && response.score !== undefined ||
                strengths.length ||
                weaknesses.length ||
                response.recommendation ||
                response.feedback ||
                response.ideal_answer
            );
            const evaluation = document.createElement('div');
            evaluation.className = 'response-review-answer';
            const evaluationTitle = document.createElement('strong');
            evaluationTitle.className = 'response-review-label';
            evaluationTitle.textContent = 'Evaluation:';
            evaluation.appendChild(evaluationTitle);
            if (unanswered && !hasReviewData) {
                evaluation.appendChild(document.createTextNode(' This question was not answered and was not evaluated.'));
            } else if (strengths.length || weaknesses.length) {
                evaluation.appendChild(reviewList('What you did correctly', strengths, 'No specific strengths were returned.'));
                evaluation.appendChild(reviewList('What was missing or incorrect', weaknesses, 'No specific gaps were returned.'));
            } else if (response.feedback || response.recommendation) {
                evaluation.appendChild(document.createTextNode(' This question was left blank, but a question-specific review was still generated.'));
            } else {
                evaluation.appendChild(document.createTextNode(' A detailed evaluation is unavailable for this response.'));
            }
            item.appendChild(evaluation);
            if (hasReviewData && (response.feedback || response.recommendation || strengths.length || weaknesses.length)) {
                const detailedFeedback = document.createElement('div');
                detailedFeedback.className = 'response-review-suggestion';
                const feedbackTitle = document.createElement('strong');
                feedbackTitle.className = 'response-review-label';
                feedbackTitle.textContent = 'Detailed Feedback:';
                detailedFeedback.appendChild(feedbackTitle);
                detailedFeedback.appendChild(responseTextBlock(
                    'How to improve',
                    response.recommendation || response.feedback || 'Detailed feedback is unavailable for this response.',
                    'response-review-answer'
                ));
                if (response.feedback) {
                    detailedFeedback.appendChild(responseTextBlock('Evaluation details', response.feedback, 'response-review-answer'));
                }
                item.appendChild(detailedFeedback);
            }
            responseList.appendChild(item);
        });
        if (!responses.length) responseList.textContent = 'No question responses are available.';
    }

    const attireFeedback = document.getElementById('attire-feedback');
    if (attireFeedback) {
        attireFeedback.textContent = aiEvaluationData?.presence?.feedback || 'Attire was not assessed.';
    }
}

function reviewList(label, items, emptyMessage) {
    const section = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = `${label}:`;
    const list = document.createElement('ul');
    const displayedItems = items.length ? items : [emptyMessage];
    displayedItems.forEach(text => {
        const listItem = document.createElement('li');
        listItem.textContent = text;
        list.appendChild(listItem);
    });
    section.append(title, list);
    return section;
}

function responseTextBlock(label, text, className) {
    const block = document.createElement('div');
    block.className = className;
    const title = document.createElement('strong');
    title.className = 'response-review-label';
    title.textContent = `${label}:`;
    const content = document.createElement('span');
    content.textContent = text;
    block.append(title, content);
    return block;
}
