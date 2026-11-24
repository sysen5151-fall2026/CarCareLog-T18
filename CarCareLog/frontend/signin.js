const form = document.getElementById('auth-form');
const username = document.getElementById('username');
const password = document.getElementById('password');
const action = document.getElementById('auth-submit');
const toggle = document.getElementById('auth-switch');
const errorText = document.getElementById('auth-error');
let registering = false;
toggle.addEventListener('click', () => {
  registering = !registering;
  action.textContent = registering ? 'Create account' : 'Sign in';
  document.getElementById('form-title').textContent = registering ? 'Create a local account' : 'Sign in';
  toggle.textContent = registering ? 'Sign in to an existing account' : 'Create a local account';
  password.autocomplete = registering ? 'new-password' : 'current-password';
  password.minLength = registering ? 12 : 1;
  document.getElementById('password-hint').hidden = !registering;
  password.value = '';
  errorText.textContent = '';
  username.focus();
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  action.disabled = true;
  toggle.disabled = true;
  errorText.textContent = '';
  try {
    const response = await fetch('/api/auth/' + (registering ? 'register' : 'login'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: username.value, password: password.value})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not open your workspace.');
    try { localStorage.setItem('carcare-session-change', String(Date.now())); } catch {}
    location.replace('/');
  } catch (err) {
    errorText.textContent = err.message;
  } finally {
    action.disabled = false;
    toggle.disabled = false;
  }
});
