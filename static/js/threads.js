const RENAME_ICON_HTML = '<i class="fa-regular fa-pen-to-square"></i>';

const DELETE_ICON_HTML = '<i class="fa-regular fa-trash-can"></i>';

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
    let editingId = null;

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

            if (thread.id === editingId) {
                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'form-control form-control-sm thread-rename-input';
                input.value = thread.title;
                input.addEventListener('click', e => e.stopPropagation());
                input.addEventListener('keydown', e => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        commitRename(thread.id, input.value);
                    } else if (e.key === 'Escape') {
                        e.preventDefault();
                        cancelRename();
                    }
                });
                input.addEventListener('blur', () => commitRename(thread.id, input.value));

                li.appendChild(input);
                threadListEl.appendChild(li);
                input.focus();
                input.select();
                return;
            }

            const titleSpan = document.createElement('span');
            titleSpan.className = 'thread-title';
            titleSpan.textContent = thread.title;
            titleSpan.addEventListener('click', () => selectThread(thread.id));

            const actions = document.createElement('div');
            actions.className = 'thread-actions';

            const renameBtn = document.createElement('button');
            renameBtn.type = 'button';
            renameBtn.className = 'btn btn-sm btn-link rename-thread-btn';
            renameBtn.innerHTML = RENAME_ICON_HTML;
            renameBtn.setAttribute('aria-label', `Rename ${thread.title}`);
            renameBtn.addEventListener('click', e => {
                e.stopPropagation();
                editingId = thread.id;
                renderThreadList();
            });

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn btn-sm btn-link text-danger delete-thread-btn';
            deleteBtn.innerHTML = DELETE_ICON_HTML;
            deleteBtn.setAttribute('aria-label', `Delete ${thread.title}`);
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteThread(thread.id);
            });

            actions.appendChild(renameBtn);
            actions.appendChild(deleteBtn);

            li.appendChild(titleSpan);
            li.appendChild(actions);
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

    function cancelRename() {
        editingId = null;
        renderThreadList();
    }

    function commitRename(id, rawTitle) {
        if (editingId !== id) return; // already committed or cancelled
        editingId = null;

        const thread = threads.find(t => t.id === id);
        const trimmed = rawTitle.trim();
        if (!thread || !trimmed || trimmed === thread.title) {
            renderThreadList();
            return;
        }
        renameThread(id, trimmed);
    }

    async function renameThread(id, title) {
        UIUtils.clearAlert('thread-list-alert');
        try {
            const resp = await apiClient.patch(`/threads/${id}`, { title });
            const updated = await apiClient.handleResponse(resp);
            threads = threads.map(t => (t.id === id ? updated : t));
            if (selectedId === id) detailTitleEl.textContent = updated.title;
        } catch (err) {
            UIUtils.showAlert('thread-list-alert', 'danger', err.message);
        }
        renderThreadList();
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
