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
            const item = document.createElement('section');
            item.className = 'response-review-item';
            const heading = document.createElement('h3');
            heading.textContent = `Question ${response.question_number ?? index + 1}: ${response.question_text || 'Interview question'}`;
            item.appendChild(heading);
            const answerText = typeof response.answer_text === 'string' ? response.answer_text.trim() : '';
            item.appendChild(responseTextBlock(
                'Your Answer',
                answerText || 'No answer was captured. Press Start listening to retry, or type an answer before continuing.',
                'response-review-answer'
            ));
            item.appendChild(responseTextBlock(
                'Ideal Answer',
                response.ideal_answer || (response.evaluation_source === 'ai_unavailable'
                    ? 'Gemini could not generate an ideal answer. Check the API key and retry results.'
                    : 'No ideal answer was returned for this question.'),
                'response-review-suggestion'
            ));
            if (response.feedback) {
                item.appendChild(responseTextBlock('Evaluation Feedback', response.feedback, 'response-review-answer'));
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
