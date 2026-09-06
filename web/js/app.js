/* ==========================================================================
   COGNIHIRE - Main Application Logic (app.js)
   ========================================================================== */

let currentSession = null;
let currentUser = JSON.parse(localStorage.getItem('cognihire-current-user') || 'null');

const careerOptions = {
    technical: { fields: ['Software Development', 'Data Science', 'AI / ML', 'Cyber Security', 'Cloud / DevOps', 'Web / Mobile'], roles: ['Software Engineer'], rolesByField: { 'Software Development': ['Software Engineer', 'Backend Developer', 'Frontend Developer'], 'Data Science': ['Data Scientist', 'Data Analyst', 'Product Analyst'], 'AI / ML': ['ML Engineer', 'AI Researcher', 'NLP Engineer'], 'Cyber Security': ['Security Analyst', 'Penetration Tester', 'Security Engineer'], 'Cloud / DevOps': ['DevOps Engineer', 'Cloud Engineer', 'Site Reliability Engineer'], 'Web / Mobile': ['Web Developer', 'Mobile App Developer', 'Full Stack Developer'] }, topicsByField: { 'Software Development': ['Data structures', 'Algorithms', 'System design', 'Code quality'], 'Data Science': ['Statistics', 'Data analysis', 'Machine learning', 'Business insight'], 'AI / ML': ['Model fundamentals', 'Feature engineering', 'Evaluation', 'AI ethics'], 'Cyber Security': ['Threat analysis', 'Network security', 'Incident response', 'Risk management'], 'Cloud / DevOps': ['Cloud architecture', 'CI/CD', 'Infrastructure', 'Reliability'], 'Web / Mobile': ['Frontend architecture', 'APIs', 'Performance', 'Accessibility'] } },
    'non-technical': { fields: ['HR', 'Marketing', 'Finance', 'Sales', 'Operations', 'Business Development'], roles: ['HR Executive'], rolesByField: { HR: ['HR Executive', 'Talent Acquisition Specialist', 'People Operations Manager'], Marketing: ['Marketing Manager', 'Brand Strategist', 'Digital Marketing Specialist'], Finance: ['Financial Analyst', 'Investment Analyst', 'Accounts Manager'], Sales: ['Sales Executive', 'Account Manager', 'Business Sales Manager'], Operations: ['Operations Manager', 'Process Analyst', 'Supply Chain Coordinator'], 'Business Development': ['Business Development Manager', 'Partnerships Manager', 'Growth Executive'] }, topicsByField: { HR: ['Recruitment', 'Employee relations', 'Conflict resolution', 'People strategy'], Marketing: ['Customer research', 'Brand strategy', 'Campaign planning', 'Marketing metrics'], Finance: ['Financial statements', 'Valuation', 'Risk analysis', 'Business cases'], Sales: ['Needs discovery', 'Objection handling', 'Negotiation', 'Account growth'], Operations: ['Process improvement', 'Planning', 'Quality control', 'Resource decisions'], 'Business Development': ['Market expansion', 'Partnerships', 'Lead qualification', 'Revenue strategy'] } },
    government: { fields: ['UPSC Civil Services', 'SSC', 'Banking', 'Railway', 'Defence', 'State PSC'], roles: ['IAS Officer', 'IPS Officer', 'Bank PO', 'Defence Officer'], rolesByField: { 'UPSC Civil Services': ['IAS Officer', 'IPS Officer', 'IFS Officer', 'IRS Officer'], SSC: ['SSC CGL Officer', 'SSC CHSL Executive', 'SSC JE Engineer', 'SSC MTS Staff'], Banking: ['Bank PO', 'Bank Clerk', 'Specialist Officer', 'RBI Grade B Officer'], Railway: ['RRB NTPC Executive', 'Railway Group D', 'Assistant Loco Pilot', 'Junior Engineer'], Defence: ['NDA Officer', 'CDS Officer', 'AFCAT Officer', 'Agniveer'], 'State PSC': ['State Civil Services Officer', 'State Police Officer', 'Revenue Officer', 'Municipal Officer'] }, topicsByField: { 'UPSC Civil Services': ['Current affairs', 'Polity and governance', 'Ethics and judgment', 'Essay and administration'], SSC: ['Quantitative aptitude', 'Reasoning', 'English language', 'General awareness'], Banking: ['Banking awareness', 'Quantitative aptitude', 'Reasoning ability', 'Financial awareness'], Railway: ['General science', 'Mathematics', 'Reasoning', 'Railway awareness'], Defence: ['National security', 'Leadership', 'Current affairs', 'Situational judgment'], 'State PSC': ['State history and culture', 'Constitution', 'Local governance', 'Current affairs'] } },
    academic: { fields: ['University Admission', 'Scholarship', 'Research', 'Teaching'], roles: ['Research candidate'], rolesByField: { 'University Admission': ['Undergraduate applicant', 'Postgraduate applicant', 'International applicant'], Scholarship: ['Scholarship applicant', 'Merit scholar applicant', 'Fellowship applicant'], Research: ['Research candidate', 'Research assistant', 'PhD scholar'], Teaching: ['Teaching fellow', 'Lecturer applicant', 'Academic coordinator'] }, topicsByField: { 'University Admission': ['Subject foundation', 'Academic goals', 'Course fit', 'Future plans'], Scholarship: ['Achievements', 'Financial need', 'Community impact', 'Long-term goals'], Research: ['Research proposal', 'Methodology', 'Literature knowledge', 'Research impact'], Teaching: ['Subject knowledge', 'Lesson planning', 'Student engagement', 'Assessment methods'] } }
};

function updateCareerOptions() {
    const path = document.getElementById('career-path').value;
    const data = careerOptions[path];
    document.getElementById('career-field').innerHTML = data.fields.map(item => `<option value="${item}">${item}</option>`).join('');
    updateTargetRoles(data, data.fields[0]);
    document.getElementById('role-label').textContent = path === 'government' ? 'Exam / target service' : path === 'academic' ? 'Target programme / role' : 'Target role';
    updateQuestionPreview();
}

function updateTargetRoles(data, field) {
    const roles = data.rolesByField?.[field] || data.roles;
    document.getElementById('job-role').innerHTML = roles.map(item => `<option value="${item}">${item}</option>`).join('');
}

function updateQuestionPreview() {
    const path = document.getElementById('career-path').value;
    const field = document.getElementById('career-field').value;
    const data = careerOptions[path];
    updateTargetRoles(data, field);
    const selectedRole = document.getElementById('job-role').value;
    document.getElementById('question-preview-title').textContent = `${field} interview focus`;
    document.getElementById('question-preview-copy').textContent = `Your AI interviewer will combine ${field.toLowerCase()} knowledge with realistic ${selectedRole.toLowerCase()} scenarios.`;
    const topics = data.topicsByField?.[field] || data.topics;
    document.getElementById('question-topics').innerHTML = topics.map(topic => `<span>${topic}</span>`).join('');
}

document.getElementById('career-path')?.addEventListener('change', updateCareerOptions);
document.getElementById('career-field')?.addEventListener('change', updateQuestionPreview);
if (document.getElementById('career-path')) updateCareerOptions();

// Screen Navigation
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    const targetScreen = document.getElementById(screenId);
    if (targetScreen) {
        targetScreen.classList.add('active');
    }
}

function openApp(view = 'dashboard') {
    if (view === 'logout') { logoutUser(); return; }
    showScreen(`${view}-screen`);
    document.querySelectorAll('.taskbar-item').forEach(item => item.classList.toggle('active', item.dataset.view === view));
    if (view === 'dashboard') renderDashboard();
    if (view === 'history') renderHistory();
    if (view === 'profile') renderProfile();
}

document.getElementById('login-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const message = document.getElementById('auth-message');
    const result = authenticateUser(username, password);
    if (!result.ok) { message.textContent = result.message; return; }
    currentUser = result.user;
    localStorage.setItem('cognihire-current-user', JSON.stringify(currentUser));
    openApp();
});

document.getElementById('auth-toggle')?.addEventListener('click', toggleAuthMode);
document.getElementById('theme-toggle')?.addEventListener('click', toggleMonoTheme);
document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => openApp(button.dataset.view)));
document.getElementById('logout-btn')?.addEventListener('click', logoutUser);
document.getElementById('profile-logout')?.addEventListener('click', logoutUser);
document.getElementById('new-interview-btn')?.addEventListener('click', () => showScreen('setup-screen'));

// Start Setup Process
document.getElementById('start-btn')?.addEventListener('click', async () => {
    const jobRole = document.getElementById('job-role').value;
    const careerPath = document.getElementById('career-path').value;
    const careerField = document.getElementById('career-field').value;
    const purpose = document.getElementById('interview-purpose').value;
    const difficulty = document.getElementById('difficulty').value;
    const interviewType = document.getElementById('interview-type').value;
    const questionCount = Number(document.getElementById('question-count').value);
    
    // Apply dynamic theme based on selection
    applyTheme(jobRole);
    
    // Transition to Live Interview
    startInterviewFlow(jobRole, interviewType, questionCount, { careerPath, careerField, purpose, difficulty });
});

if (currentUser) openApp();
