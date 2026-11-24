const exitButton = document.getElementById('sign-out');
const ownerBadge = document.querySelector('.local');
const workspaceId = document.querySelector('meta[name="carcare-workspace"]').content;
const coreFetch = window.fetch.bind(window);
window.fetch = async (url, options = {}) => {
  if (typeof url !== 'string' || !url.startsWith('/api/')) return coreFetch(url, options);
  const headers = new Headers(options.headers);
  headers.set('X-CarCare-Workspace', workspaceId);
  const response = await coreFetch(url, {...options, headers});
  if (response.status === 401 || response.status === 409) {
    const result = await response.clone().json().catch(() => ({}));
    if (response.status === 401 || result.code === 'workspace_changed') {
      location.replace('/');
    }
  }
  return response;
};
fetch('/api/auth/session').then(async response => {
  if (response.status === 401) return location.replace('/');
  if (response.ok) ownerBadge.textContent = 'Signed in as ' + (await response.json()).username;
}).catch(() => {});
exitButton.addEventListener('click', async () => {
  exitButton.disabled = true;
  try {
    const response = await fetch('/api/auth/logout', {method: 'POST'});
    if (!response.ok) throw new Error();
    try { localStorage.setItem('carcare-session-change', String(Date.now())); } catch {}
    location.replace('/');
  } catch {
    exitButton.disabled = false;
    const banner = document.getElementById('message');
    banner.hidden = false;
    banner.textContent = 'Could not sign out. Check that the local app is running and try again.';
  }
});
// A restored browser-history snapshot must recheck the active account before showing private data.
addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
addEventListener('storage', event => { if (event.key === 'carcare-session-change') location.replace('/'); });
