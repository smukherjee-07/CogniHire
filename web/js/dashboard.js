function getSessions() {
	return JSON.parse(localStorage.getItem(`cognihire-sessions-${currentUser?.username}`) || '[]');
}

function renderDashboard() {
	const sessions = getSessions();
	document.getElementById('dashboard-greeting').textContent = `Good to see you, ${currentUser.username}`;
	document.getElementById('session-count').textContent = sessions.length;
	document.getElementById('average-score').textContent = sessions.length ? `${Math.round(sessions.reduce((sum, item) => sum + item.score, 0) / sessions.length)}/10` : '--';
	document.getElementById('last-practice').textContent = sessions[0]?.date || 'Not yet';
	document.getElementById('recent-sessions').innerHTML = sessions.length ? sessions.slice(0, 3).map(sessionCard).join('') : '<p class="empty-state">Your completed interviews will appear here.</p>';
}

function renderProfile() {
	document.getElementById('profile-name').textContent = currentUser.username;
	document.getElementById('profile-avatar').textContent = currentUser.username.charAt(0).toUpperCase();
}

function sessionCard(session) {
	return `<article class="session-item"><div><strong>${session.role}</strong><span>${session.type} · ${session.questions} questions · ${session.date}</span></div><b>${session.score}/10</b></article>`;
}
