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

// Function to parse the FINAL RESULT and AI EVALUATION objects from backend
function renderReportCard(finalResultData, aiEvaluationData) {
    // Populate Overall Score from the backend result.
    const scoreElement = document.getElementById('overall-score');
    if (scoreElement) {
        const score = Number(aiEvaluationData?.score ?? finalResultData?.score);
        scoreElement.textContent = Number.isFinite(score) ? `${score}/10` : '--/10';
    }
    
    // Populate Strengths & Weaknesses...
    // Populate Attire Feedback into the Professional Presence tab...
}
