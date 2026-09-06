function renderHistory() {
	const sessions = getSessions();
	document.getElementById('history-list').innerHTML = sessions.length ? sessions.map(sessionCard).join('') : '<p class="empty-state">No interviews completed yet.</p>';
}
