class UIUtils {
    static showAlert(containerId, type, message) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
    }

    static clearAlert(containerId) {
        const container = document.getElementById(containerId);
        if (container) container.innerHTML = '';
    }

    static showFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        const feedback = field?.nextElementSibling;
        if (field) field.classList.add('is-invalid');
        if (feedback) feedback.textContent = message;
    }

    static clearValidation(fieldIds) {
        fieldIds.forEach(id => {
            const field = document.getElementById(id);
            const feedback = field?.nextElementSibling;
            if (field) field.classList.remove('is-invalid');
            if (feedback) feedback.textContent = '';
        });
    }

    static handleServerValidation(errors) {
        if (Array.isArray(errors)) {
            errors.forEach(err => {
                const field = err.loc?.[1];
                if (field && document.getElementById(field)) {
                    this.showFieldError(field, err.msg);
                }
            });
        }
    }

    static setLoadingState(buttonId, isLoading, loadingText = 'Loading…') {
        const btn = document.getElementById(buttonId);
        if (!btn) return;
        if (!btn._originalHTML) btn._originalHTML = btn.innerHTML;
        btn.disabled = isLoading;
        btn.innerHTML = isLoading
            ? `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${loadingText}`
            : btn._originalHTML;
    }

    static isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    static redirectAfterDelay(url, delay = 1500) {
        setTimeout(() => { window.location.href = url; }, delay);
    }

    static toggleVisibility(elementId, show) {
        const el = document.getElementById(elementId);
        if (el) el.classList.toggle('d-none', !show);
    }
}

window.UIUtils = UIUtils;