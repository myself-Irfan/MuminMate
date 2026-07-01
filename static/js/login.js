document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        UIUtils.clearValidation(['email', 'password']);
        UIUtils.clearAlert('alert');

        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;

        if (!validateForm(email, password)) return;

        UIUtils.setLoadingState('submit-btn', true, 'Signing in…');
        try {
            const resp = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });
            const data = await apiClient.handleResponse(resp);
            apiClient.setAccessToken(data.access_token);
            UIUtils.showAlert('alert', 'success', 'Login successful. Redirecting…');
            UIUtils.redirectAfterDelay('/');
        } catch (err) {
            UIUtils.showAlert('alert', 'danger', err.message);
        } finally {
            UIUtils.setLoadingState('submit-btn', false);
        }
    });

    function validateForm(email, password) {
        let valid = true;
        if (!email) {
            UIUtils.showFieldError('email', 'Email is required.');
            valid = false;
        } else if (!UIUtils.isValidEmail(email)) {
            UIUtils.showFieldError('email', 'Enter a valid email address.');
            valid = false;
        }
        if (!password) {
            UIUtils.showFieldError('password', 'Password is required.');
            valid = false;
        }
        return valid;
    }
});