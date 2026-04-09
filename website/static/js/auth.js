/* OPDex — Supabase Auth (Google login, session management, nav UI) */

(function () {
    'use strict';

    // Bail if Supabase config is missing (local dev without Supabase)
    if (!window.SUPABASE_URL || !window.SUPABASE_ANON_KEY) {
        window.opdexAuth = {
            isLoggedIn: () => false,
            getUser: () => null,
            getToken: async () => null,
            getProfile: () => null,
            fetchWithAuth: (url, opts) => fetch(url, opts),
            signIn: () => alert('Supabase is not configured.'),
            signOut: () => {},
            showAvatarPicker: () => {},
            onReady: (cb) => cb(),
        };
        document.getElementById('navSignIn').style.display = 'none';
        return;
    }

    const supabase = window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
    window._supabase = supabase;

    let currentUser = null;
    let currentProfile = null;
    let accessToken = null;
    const readyCallbacks = [];
    let isReady = false;

    // DOM refs
    const navAuth = document.getElementById('navAuth');
    const navSignIn = document.getElementById('navSignIn');
    const navUser = document.getElementById('navUser');
    const navAvatar = document.getElementById('navAvatar');
    const navUsername = document.getElementById('navUsername');

    // -----------------------------------------------------------------
    // Session init
    // -----------------------------------------------------------------

    async function init() {
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
            currentUser = session.user;
            accessToken = session.access_token;
            await loadProfile();
            updateNav();
        } else {
            updateNav();
        }
        isReady = true;
        readyCallbacks.forEach(cb => cb());
        readyCallbacks.length = 0;

        // Listen for auth changes (login/logout)
        supabase.auth.onAuthStateChange(async (event, session) => {
            if (event === 'SIGNED_IN' && session) {
                currentUser = session.user;
                accessToken = session.access_token;
                await loadProfile();
                updateNav();
                checkLocalStorageImport();
            } else if (event === 'SIGNED_OUT') {
                currentUser = null;
                currentProfile = null;
                accessToken = null;
                updateNav();
            }
        });
    }

    // -----------------------------------------------------------------
    // Profile
    // -----------------------------------------------------------------

    async function loadProfile() {
        if (!currentUser) return;
        try {
            const resp = await fetchWithAuth('/api/profile');
            if (resp.ok) {
                currentProfile = await resp.json();
            }
        } catch (_) {
            currentProfile = null;
        }
    }

    // -----------------------------------------------------------------
    // Nav UI
    // -----------------------------------------------------------------

    function updateNav() {
        if (currentUser) {
            navSignIn.style.display = 'none';
            navUser.style.display = '';

            const name = currentProfile?.username
                || currentUser.user_metadata?.name
                || currentUser.email?.split('@')[0]
                || 'Player';
            navUsername.textContent = name;

            if (currentProfile?.avatar_leader_code) {
                navAvatar.src = '/card-image/' + currentProfile.avatar_leader_code;
                navAvatar.style.objectPosition = 'center 33%';
            } else {
                // Default avatar — first letter
                navAvatar.style.display = 'none';
            }
        } else {
            navSignIn.style.display = '';
            navUser.style.display = 'none';
        }
    }

    // -----------------------------------------------------------------
    // Auth actions
    // -----------------------------------------------------------------

    async function signIn() {
        await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: window.location.origin },
        });
    }

    async function signOut() {
        await supabase.auth.signOut();
        window.location.reload();
    }

    // -----------------------------------------------------------------
    // Authenticated fetch helper
    // -----------------------------------------------------------------

    async function fetchWithAuth(url, opts = {}) {
        // Refresh token if needed
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
            accessToken = session.access_token;
        }

        const headers = { ...opts.headers };
        if (accessToken) {
            headers['Authorization'] = 'Bearer ' + accessToken;
        }
        return fetch(url, { ...opts, headers });
    }

    // -----------------------------------------------------------------
    // localStorage import check (first login)
    // -----------------------------------------------------------------

    function checkLocalStorageImport() {
        const STORAGE_KEY = 'opdex_library';
        const local = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        if (!local.length) return;

        // Only prompt once per user
        const importKey = 'opdex_import_done_' + currentUser.id;
        if (localStorage.getItem(importKey)) return;

        const count = local.length;
        const modal = document.createElement('div');
        modal.className = 'import-modal';
        modal.innerHTML = `
            <div class="import-modal-content">
                <h3>Import Local Decks</h3>
                <p>We found <strong>${count}</strong> deck${count > 1 ? 's' : ''} saved on this device.
                   Import them to your account?</p>
                <div class="import-modal-actions">
                    <button type="button" class="btn btn-primary" id="importYes">Import</button>
                    <button type="button" class="btn btn-secondary" id="importNo">Skip</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        document.getElementById('importYes').addEventListener('click', async () => {
            try {
                const resp = await fetchWithAuth('/api/decks/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ decks: local }),
                });
                if (resp.ok) {
                    localStorage.setItem(importKey, '1');
                    modal.remove();
                    if (window.location.pathname === '/library') {
                        window.location.reload();
                    }
                }
            } catch (_) {
                alert('Import failed. Please try again.');
            }
        });

        document.getElementById('importNo').addEventListener('click', () => {
            localStorage.setItem(importKey, '1');
            modal.remove();
        });
    }

    // -----------------------------------------------------------------
    // Avatar picker (delegated to avatar-picker.js)
    // -----------------------------------------------------------------

    function showAvatarPicker() {
        if (window.avatarPicker) {
            window.avatarPicker.open();
        }
    }

    // -----------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------

    window.opdexAuth = {
        isLoggedIn: () => !!currentUser,
        getUser: () => currentUser,
        getToken: async () => {
            const { data: { session } } = await supabase.auth.getSession();
            return session?.access_token || null;
        },
        getProfile: () => currentProfile,
        fetchWithAuth,
        signIn,
        signOut,
        showAvatarPicker,
        setProfile: (profile) => { currentProfile = profile; updateNav(); },
        onReady: (cb) => {
            if (isReady) cb();
            else readyCallbacks.push(cb);
        },
    };

    init();
})();
