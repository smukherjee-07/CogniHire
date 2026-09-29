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
    document.querySelectorAll('.tab-pane').forEach(pane => {
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

    // Populate Attire Feedback into the Professional Presence tab...
}
