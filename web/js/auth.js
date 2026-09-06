let isCreateMode = false;

function toggleAuthMode() {
	isCreateMode = !isCreateMode;
	document.getElementById('auth-title').textContent = isCreateMode ? 'Create your account' : 'Welcome Back';
	document.getElementById('login-btn').textContent = isCreateMode ? 'Create account' : 'Sign In';
	document.getElementById('auth-toggle').textContent = isCreateMode ? 'Already have an account? Sign in' : 'Need an account? Create one';
	document.getElementById('auth-message').textContent = '';
}

function authenticateUser(username, password) {
	if (username.length < 2 || password.length < 4) return { ok: false, message: 'Use a username and a password with at least 4 characters.' };
	const accounts = JSON.parse(localStorage.getItem('cognihire-accounts') || '{}');
	if (isCreateMode) {
		if (accounts[username]) return { ok: false, message: 'That username already exists.' };
		accounts[username] = { username, password };
		localStorage.setItem('cognihire-accounts', JSON.stringify(accounts));
		return { ok: true, user: { username } };
	}
	if (!accounts[username]) accounts[username] = { username, password };
	if (accounts[username].password !== password) return { ok: false, message: 'Incorrect username or password.' };
	return { ok: true, user: { username } };
}

function logoutUser() {
	localStorage.removeItem('cognihire-current-user');
	currentUser = null;
	showScreen('login-screen');
}
