async function requireAuth() {
    const ok = await apiClient.refreshAccessToken();
    if (!ok) window.location.href = '/login';
}

async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    apiClient.clearAccessToken();
    window.location.href = '/login';
}