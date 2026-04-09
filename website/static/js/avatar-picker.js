/* OPDex — Leader Avatar Picker Modal */

(function () {
    'use strict';

    let modal = null;
    let leaders = null;

    async function fetchLeaders() {
        if (leaders) return leaders;
        const resp = await fetch('/api/leaders');
        leaders = await resp.json();
        return leaders;
    }

    function createModal() {
        if (modal) return modal;

        modal = document.createElement('div');
        modal.className = 'avatar-modal';
        modal.innerHTML = `
            <div class="avatar-modal-panel">
                <div class="avatar-modal-header">
                    <h3>Choose Your Leader</h3>
                    <button type="button" class="avatar-modal-close" id="avatarClose">&times;</button>
                </div>
                <div class="avatar-modal-search">
                    <input type="text" id="avatarSearch" placeholder="Search leaders..." autocomplete="off">
                </div>
                <div class="avatar-grid" id="avatarGrid"></div>
            </div>
        `;
        document.body.appendChild(modal);

        // Close handlers
        document.getElementById('avatarClose').addEventListener('click', close);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) close();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) close();
        });

        // Search
        document.getElementById('avatarSearch').addEventListener('input', (e) => {
            const q = e.target.value.toLowerCase();
            modal.querySelectorAll('.avatar-option').forEach(el => {
                const name = el.dataset.name.toLowerCase();
                const code = el.dataset.code.toLowerCase();
                el.style.display = (name.includes(q) || code.includes(q)) ? '' : 'none';
            });
        });

        return modal;
    }

    async function renderGrid() {
        const grid = document.getElementById('avatarGrid');
        const list = await fetchLeaders();

        const currentCode = opdexAuth.getProfile()?.avatar_leader_code || '';

        grid.innerHTML = list.map(l => `
            <div class="avatar-option ${l.code === currentCode ? 'selected' : ''}"
                 data-code="${l.code}" data-name="${l.name}">
                <img src="/card-image/${l.code}" alt="${l.name}" loading="lazy">
                <span class="avatar-option-name">${l.name}</span>
            </div>
        `).join('');

        // Click to select
        grid.querySelectorAll('.avatar-option').forEach(el => {
            el.addEventListener('click', async () => {
                const code = el.dataset.code;

                // Visual feedback
                grid.querySelectorAll('.avatar-option').forEach(o => o.classList.remove('selected'));
                el.classList.add('selected');

                // Save to profile
                try {
                    const resp = await opdexAuth.fetchWithAuth('/api/profile', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ avatar_leader_code: code }),
                    });
                    if (resp.ok) {
                        const profile = await resp.json();
                        opdexAuth.setProfile(profile);
                        close();
                    }
                } catch (_) {
                    alert('Failed to update avatar.');
                }
            });
        });
    }

    function open() {
        const m = createModal();
        m.classList.add('active');
        renderGrid();
        document.getElementById('avatarSearch').value = '';
        document.getElementById('avatarSearch').focus();
    }

    function close() {
        if (modal) modal.classList.remove('active');
    }

    window.avatarPicker = { open, close };
})();
