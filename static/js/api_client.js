class ApiClient {
    constructor() {
        this._accessToken = null;
    }

    setAccessToken(token) {
        this._accessToken = token;
    }

    clearAccessToken() {
        this._accessToken = null;
    }

    async refreshAccessToken() {
        try {
            const resp = await fetch('/api/auth/refresh', { method: 'POST' });
            if (!resp.ok) return false;
            const data = await resp.json();
            this._accessToken = data.access_token;
            return true;
        } catch {
            return false;
        }
    }

    _authHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (this._accessToken) headers['Authorization'] = `Bearer ${this._accessToken}`;
        return headers;
    }

    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`;
        const config = {
            ...options,
            headers: { ...this._authHeaders(), ...(options.headers || {}) },
        };

        let resp = await fetch(url, config);

        if (resp.status === 401 && !options._isRetry) {
            const refreshed = await this.refreshAccessToken();
            if (refreshed) {
                config.headers['Authorization'] = `Bearer ${this._accessToken}`;
                config._isRetry = true;
                resp = await fetch(url, config);
            }
        }

        if (resp.status === 401) {
            this.clearAccessToken();
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
                throw new Error('Session expired. Please log in again.');
            }
            throw new Error('Invalid email or password.');
        }

        return resp;
    }

    async handleResponse(resp) {
        if (!resp.ok) {
            let msg = this._statusMessage(resp.status);
            try {
                const data = await resp.json();
                if (Array.isArray(data.detail)) {
                    msg = data.detail.map(e => e.msg).join(', ');
                } else {
                    msg = data.detail || data.message || msg;
                }
            } catch {}
            throw new Error(msg);
        }
        if (resp.status === 204) return null;
        return resp.json();
    }

    _statusMessage(status) {
        const messages = {
            400: 'Invalid data provided.',
            401: 'Unauthorized. Please log in again.',
            403: 'You are not permitted to do this.',
            404: 'Not found.',
            409: 'Already exists.',
            422: 'Validation failed.',
            429: 'Too many attempts. Please wait and try again.',
            500: 'Server error. Please try again later.',
        };
        return messages[status] || `Unexpected error (${status}).`;
    }

    async get(endpoint) {
        return this.request(endpoint);
    }

    async post(endpoint, data) {
        return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) });
    }

    async put(endpoint, data) {
        return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data) });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
}

const apiClient = new ApiClient();
window.apiClient = apiClient;