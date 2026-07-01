document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('register-form');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        UIUtils.clearValidation(['email', 'username', 'password']);
        UIUtils.clearAlert('alert');

        const email = document.getElementById('email').value.trim();
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        if (!validateForm(email, username, password)) return;

        UIUtils.setLoadingState('submit-btn', true, 'Creating account…');
        try {
            const resp = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, username, password }),
            });

            if (resp.status === 422) {
                const data = await resp.json();
                UIUtils.handleServerValidation(data.detail);
                return;
            }

            await apiClient.handleResponse(resp);
            UIUtils.showAlert('alert', 'success', 'Account created! Redirecting to login…');
            UIUtils.redirectAfterDelay('/login');
        } catch (err) {
            UIUtils.showAlert('alert', 'danger', err.message);
        } finally {
            UIUtils.setLoadingState('submit-btn', false);
        }
    });

    function validateForm(email, username, password) {
        let valid = true;
        if (!email) {
            UIUtils.showFieldError('email', 'Email is required.');
            valid = false;
        } else if (!UIUtils.isValidEmail(email)) {
            UIUtils.showFieldError('email', 'Enter a valid email address.');
            valid = false;
        }
        if (!username || username.length < 3) {
            UIUtils.showFieldError('username', 'Username must be at least 3 characters.');
            valid = false;
        }
        if (!password || password.length < 8) {
            UIUtils.showFieldError('password', 'Password must be at least 8 characters.');
            valid = false;
        }
        return valid;
    }
});