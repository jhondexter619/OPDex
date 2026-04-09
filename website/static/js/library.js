/* OPDex — Deck Library (Supabase + localStorage fallback) */

(function () {
    'use strict';

    const STORAGE_KEY = 'opdex_library';
    const grid = document.getElementById('libraryGrid');
    const empty = document.getElementById('libraryEmpty');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImg');

    // -----------------------------------------------------------------
    // Storage abstraction
    // -----------------------------------------------------------------

    function loadLocal() {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    }

    function saveLocal(library) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(library));
    }

    function useCloud() {
        return window.opdexAuth && opdexAuth.isLoggedIn() && window.deckStore;
    }

    async function loadLibrary() {
        if (useCloud()) {
            const decks = await deckStore.list();
            // Normalize Supabase shape to match localStorage shape
            return decks.map(d => ({
                id: d.id,
                name: d.name,
                cards: d.cards,
                totalCards: d.total_cards,
                uniqueCards: d.unique_cards,
                leaderCode: d.leader_code,
                savedAt: d.updated_at || d.created_at,
                isPublic: d.is_public,
            }));
        }
        return loadLocal();
    }

    async function deleteDeck(id) {
        if (useCloud()) {
            await deckStore.remove(id);
        } else {
            const lib = loadLocal().filter(d => d.id !== id);
            saveLocal(lib);
        }
    }

    async function togglePublic(id, isPublic) {
        if (useCloud()) {
            await deckStore.togglePublic(id, isPublic);
        }
    }

    // -----------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------

    async function render() {
        const library = await loadLibrary();

        if (!library.length) {
            empty.style.display = '';
            return;
        }
        empty.style.display = 'none';

        const isCloud = useCloud();

        const html = library.map((deck, i) => {
            const date = new Date(deck.savedAt).toLocaleDateString();
            const shareBtn = isCloud ? `
                <button class="btn btn-sm ${deck.isPublic ? 'btn-save' : 'btn-secondary'} btn-share" data-id="${deck.id}" data-public="${deck.isPublic ? '1' : '0'}">
                    ${deck.isPublic ? 'Shared' : 'Share'}
                </button>
                ${deck.isPublic ? `<button class="btn btn-sm btn-secondary btn-copy-link" data-id="${deck.id}" title="Copy link">Link</button>` : ''}
            ` : '';

            return `
            <div class="library-card" style="--i:${i}">
                <div class="library-card-leader" data-code="${deck.leaderCode}">
                    <img src="/card-image/${deck.leaderCode}" alt="" loading="lazy"
                         onerror="this.style.display='none'">
                </div>
                <div class="library-card-info">
                    <h3 class="library-card-name">${deck.name}</h3>
                    <span class="library-card-stat">${deck.totalCards} cards &middot; ${deck.uniqueCards} unique</span>
                    <span class="library-card-date">Saved ${date}</span>
                </div>
                <div class="library-card-actions">
                    <a href="/builder?load=${deck.id}" class="btn btn-sm btn-primary">Edit</a>
                    <button class="btn btn-sm btn-secondary btn-pdf" data-id="${deck.id}">PDF</button>
                    ${shareBtn}
                    <button class="btn btn-sm btn-danger btn-delete" data-id="${deck.id}">Delete</button>
                </div>
            </div>`;
        }).join('');

        grid.innerHTML = `<div class="library-empty" id="libraryEmpty" style="display:none">
            <p>No saved decks yet.</p>
            <p>Build a deck in the <a href="/builder">Deck Builder</a> and save it here.</p>
        </div>` + html;

        // Animate cards in
        requestAnimationFrame(() => {
            grid.querySelectorAll('.library-card').forEach(el => {
                el.classList.add('card-enter');
            });
        });

        // Delete buttons
        grid.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
                await deleteDeck(btn.dataset.id);
                render();
            });
        });

        // PDF buttons
        grid.querySelectorAll('.btn-pdf').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const deck = library.find(d => d.id === id);
                if (!deck) return;

                btn.textContent = 'Generating\u2026';
                btn.disabled = true;

                try {
                    const resp = await fetch('/build-pdf', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cards: deck.cards, name: deck.name }),
                    });
                    if (!resp.ok) throw new Error();

                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `OPTCG_${deck.name.replace(/[^a-zA-Z0-9 _-]/g, '')}.pdf`;
                    a.click();
                    URL.revokeObjectURL(url);
                } catch (e) {
                    alert('PDF generation failed.');
                }

                btn.textContent = 'PDF';
                btn.disabled = false;
            });
        });

        // Share toggle buttons
        grid.querySelectorAll('.btn-share').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const currentlyPublic = btn.dataset.public === '1';
                const newState = !currentlyPublic;

                btn.disabled = true;
                try {
                    await togglePublic(id, newState);
                    render();
                } catch (e) {
                    alert('Failed to update sharing.');
                    btn.disabled = false;
                }
            });
        });

        // Copy link buttons
        grid.querySelectorAll('.btn-copy-link').forEach(btn => {
            btn.addEventListener('click', () => {
                const url = window.location.origin + '/shared/' + btn.dataset.id;
                navigator.clipboard.writeText(url).then(() => {
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Link'; }, 1500);
                });
            });
        });

        // Leader image zoom
        grid.querySelectorAll('.library-card-leader').forEach(el => {
            el.style.cursor = 'pointer';
            el.addEventListener('click', () => {
                openLightbox(`/card-image/${el.dataset.code}`);
            });
        });
    }

    // Lightbox
    function openLightbox(src) {
        lightboxImg.src = src;
        lightbox.classList.add('active');
    }

    lightbox.addEventListener('click', () => {
        lightbox.classList.remove('active');
        lightboxImg.src = '';
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            lightbox.classList.remove('active');
            lightboxImg.src = '';
        }
    });

    // Wait for auth to be ready, then render
    if (window.opdexAuth) {
        opdexAuth.onReady(() => render());
    } else {
        render();
    }
})();
