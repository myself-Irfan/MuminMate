document.addEventListener('DOMContentLoaded', async () => {
    await requireAuth();

    const usernameDisplayEl = document.getElementById('username-display');
    const user = apiClient.getUser();
    if (user) usernameDisplayEl.textContent = user.username;

    const threadListEl = document.getElementById('thread-list');
    const emptyStateEl = document.getElementById('empty-state');
    const detailEl = document.getElementById('thread-detail');
    const detailTitleEl = document.getElementById('thread-detail-title');
    const detailMetaEl = document.getElementById('thread-detail-meta');
    const newThreadBtn = document.getElementById('new-thread-btn');
    const logoutBtn = document.getElementById('logout-btn');

    let threads = [];
    let selectedId = null;

    async function loadThreads() {
        try {
            const resp = await apiClient.get('/threads');
            threads = await apiClient.handleResponse(resp);
            renderThreadList();
        } catch (err) {
            UIUtils.showAlert('thread-list-alert', 'danger', err.message);
        }
    }

    function renderThreadList() {
        threadListEl.innerHTML = '';

        if (threads.length === 0) {
            const empty = document.createElement('li');
            empty.className = 'thread-list-empty text-muted small';
            empty.textContent = 'No threads yet.';
            threadListEl.appendChild(empty);
            return;
        }

        threads.forEach(thread => {
            const li = document.createElement('li');
            li.className = 'thread-item d-flex justify-content-between align-items-center' +
                (thread.id === selectedId ? ' active' : '');

            const titleSpan = document.createElement('span');
            titleSpan.className = 'thread-title';
            titleSpan.textContent = thread.title;
            titleSpan.addEventListener('click', () => selectThread(thread.id));

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn btn-sm btn-link text-danger delete-thread-btn';
            deleteBtn.textContent = '×';
            deleteBtn.setAttribute('aria-label', `Delete ${thread.title}`);
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteThread(thread.id);
            });

            li.appendChild(titleSpan);
            li.appendChild(deleteBtn);
            threadListEl.appendChild(li);
        });
    }

    function selectThread(id) {
        const thread = threads.find(t => t.id === id);
        if (!thread) return;

        selectedId = id;
        emptyStateEl.classList.add('d-none');
        detailEl.classList.remove('d-none');
        detailTitleEl.textContent = thread.title;
        detailMetaEl.textContent = `Created ${new Date(thread.created_at).toLocaleDateString()}`;
        renderThreadList();
    }

    function clearSelection() {
        selectedId = null;
        detailEl.classList.add('d-none');
        emptyStateEl.classList.remove('d-none');
    }

    async function createThread() {
        UIUtils.clearAlert('thread-list-alert');
        UIUtils.setLoadingState('new-thread-btn', true, 'Creating…');
        try {
            const resp = await apiClient.post('/threads', {});
            const thread = await apiClient.handleResponse(resp);
            threads.unshift(thread);
            selectThread(thread.id);
        } catch (err) {
            UIUtils.showAlert('thread-list-alert', 'danger', err.message);
        } finally {
            UIUtils.setLoadingState('new-thread-btn', false);
        }
    }

    async function deleteThread(id) {
        if (!confirm('Delete this thread?')) return;

        UIUtils.clearAlert('thread-list-alert');
        try {
            const resp = await apiClient.delete(`/threads/${id}`);
            await apiClient.handleResponse(resp);
            threads = threads.filter(t => t.id !== id);
            if (selectedId === id) clearSelection();
            renderThreadList();
        } catch (err) {
            UIUtils.showAlert('thread-list-alert', 'danger', err.message);
        }
    }

    newThreadBtn.addEventListener('click', createThread);
    logoutBtn.addEventListener('click', logout);

    await loadThreads();
});
