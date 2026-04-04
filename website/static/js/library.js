/* OPDex — Deck Library */

(function () {
    'use strict';

    const STORAGE_KEY = 'opdex_library';
    const grid = document.getElementById('libraryGrid');
    const empty = document.getElementById('libraryEmpty');
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightboxImg');

    function loadLibrary() {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    }

    function saveLibrary(library) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(library));
    }

    function render() {
        const library = loadLibrary();

        if (!library.length) {
            empty.style.display = '';
            return;
        }
        empty.style.display = 'none';

        const html = library.map((deck, i) => {
            const date = new Date(deck.savedAt).toLocaleDateString();
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
            btn.addEventListener('click', () => {
                const id = btn.dataset.id;
                const lib = loadLibrary().filter(d => d.id !== id);
                saveLibrary(lib);
                render();
            });
        });

        // PDF buttons
        grid.querySelectorAll('.btn-pdf').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const deck = loadLibrary().find(d => d.id === id);
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

    render();
})();
