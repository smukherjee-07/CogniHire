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
    // Populate Overall Score
    const scoreElement = document.getElementById('overall-score');
    if (scoreElement) {
        // Using strict API contract variable 'score' (0-10)
        scoreElement.textContent = `${aiEvaluationData.score}/10`; 
    }
    
    // Populate Strengths & Weaknesses...
    // Populate Attire Feedback into the Professional Presence tab...
}
