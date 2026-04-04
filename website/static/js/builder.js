/* OPDex — Deck Builder with Library save, All Cards, per-card Library, Matchup panel */

(function () {
    'use strict';

    const STORAGE_KEY = 'opdex_library';

    const setFilter     = document.getElementById('setFilter');
    const cardSearch    = document.getElementById('cardSearch');
    const colorFilter   = document.getElementById('colorFilter');
    const typeFilter    = document.getElementById('typeFilter');
    const costMin       = document.getElementById('costMin');
    const costMax       = document.getElementById('costMax');
    const costValue     = document.getElementById('costValue');
    const costTrackFill = document.getElementById('costTrackFill');
    const browserGrid   = document.getElementById('browserGrid');
    const browserHint   = document.getElementById('browserHint');
    const deckList      = document.getElementById('deckList');
    const deckCount     = document.getElementById('deckCount');
    const deckNameInput = document.getElementById('deckName');
    const downloadBtn   = document.getElementById('downloadDeckBtn');
    const saveBtn       = document.getElementById('saveDeckBtn');
    const clearBtn      = document.getElementById('clearDeckBtn');
    const saveFeedback  = document.getElementById('saveFeedback');
    const lightbox      = document.getElementById('lightbox');
    const lightboxImg   = document.getElementById('lightboxImg');

    // Matchup panel elements
    const builderMatchupEmpty = document.getElementById('builderMatchupEmpty');
    const builderMatchupCols  = document.getElementById('builderMatchupCols');

    // Deck state: { code: qty }
    const deck = {};
    let allCards  = [];
    let metaData  = null;  // cached /api/meta response
    let editingDeckId = null;  // track if we're editing an existing library deck

    // -----------------------------------------------------------------
    // Meta data fetch (for matchup panel)
    // -----------------------------------------------------------------

    async function fetchMeta() {
        try {
            const resp = await fetch('/api/meta');
            metaData = await resp.json();
        } catch (_) {
            metaData = null;
        }
    }
    fetchMeta();

    // -----------------------------------------------------------------
    // Filters
    // -----------------------------------------------------------------

    function enableFilters(on) {
        cardSearch.disabled  = !on;
        colorFilter.disabled = !on;
        typeFilter.disabled  = !on;
        costMin.disabled     = !on;
        costMax.disabled     = !on;
    }

    function applyFilters() {
        const q     = cardSearch.value.toLowerCase();
        const color = colorFilter.value;
        const type  = typeFilter.value;
        const cMin  = parseInt(costMin.value);
        const cMax  = parseInt(costMax.value);

        // Update cost label
        costValue.textContent = cMin + '\u2013' + cMax;

        const filtered = allCards.filter(c => {
            if (q && !c.code.toLowerCase().includes(q) &&
                !(c.name && c.name.toLowerCase().includes(q))) return false;
            if (color && (!c.color || !c.color.includes(color))) return false;
            if (type  && (!c.type  || c.type !== type))          return false;
            if (c.cost !== null && c.cost !== undefined) {
                if (c.cost < cMin || c.cost > cMax) return false;
            }
            return true;
        });

        renderBrowser(filtered);
    }

    cardSearch.addEventListener('input',  applyFilters);
    colorFilter.addEventListener('change', applyFilters);
    typeFilter.addEventListener('change',  applyFilters);

    // Dual range slider — track fill + clamping
    function updateTrackFill() {
        const min = parseInt(costMin.min);
        const max = parseInt(costMin.max);
        const lo  = parseInt(costMin.value);
        const hi  = parseInt(costMax.value);
        const leftPct  = ((lo - min) / (max - min)) * 100;
        const rightPct = 100 - ((hi - min) / (max - min)) * 100;
        if (costTrackFill) {
            costTrackFill.style.left  = leftPct  + '%';
            costTrackFill.style.right = rightPct + '%';
        }
    }

    costMin.addEventListener('input', () => {
        if (parseInt(costMin.value) > parseInt(costMax.value)) {
            costMin.value = costMax.value;
        }
        updateTrackFill();
        applyFilters();
    });
    costMax.addEventListener('input', () => {
        if (parseInt(costMax.value) < parseInt(costMin.value)) {
            costMax.value = costMin.value;
        }
        updateTrackFill();
        applyFilters();
    });

    // Initial fill
    updateTrackFill();

    function resetFilters() {
        cardSearch.value      = '';
        colorFilter.value     = '';
        typeFilter.value      = '';
        costMin.value         = 0;
        costMax.value         = 10;
        costValue.textContent = '0\u201310';
        updateTrackFill();
    }

    // -----------------------------------------------------------------
    // Card Browser
    // -----------------------------------------------------------------

    async function loadCards(set) {
        if (!set) {
            browserGrid.innerHTML = '';
            browserHint.style.display = '';
            enableFilters(false);
            return;
        }

        browserHint.style.display = 'none';
        browserGrid.innerHTML = '<div class="browser-loading">Loading cards\u2026</div>';
        resetFilters();
        enableFilters(true);

        try {
            const url = set === '__all__'
                ? '/api/cards'
                : `/api/cards?set=${encodeURIComponent(set)}`;
            const resp = await fetch(url);
            allCards = await resp.json();
            renderBrowser(allCards);
        } catch (e) {
            browserGrid.innerHTML = '<div class="browser-loading">Failed to load cards</div>';
        }
    }

    setFilter.addEventListener('change', function () {
        loadCards(this.value);
    });

    function renderBrowser(cards) {
        if (!cards.length) {
            browserGrid.innerHTML = '<div class="browser-loading">No cards found</div>';
            return;
        }

        browserGrid.innerHTML = cards.map((c, i) => `
            <div class="browser-card ${deck[c.code] ? 'in-deck' : ''}" data-code="${c.code}" style="--i:${i}">
                <div class="browser-card-img">
                    <img src="/card-image/${c.code}" alt="${c.code}" loading="lazy"
                         onerror="this.style.display='none'">
                    ${deck[c.code] ? `<span class="browser-qty">\u00d7${deck[c.code]}</span>` : ''}
                    ${c.type ? `<span class="browser-type-badge">${c.type}</span>` : ''}
                </div>
                <span class="browser-card-code">${c.code}</span>
                ${c.name && c.name !== c.code ? `<span class="browser-card-name">${c.name}</span>` : ''}
            </div>
        `).join('');

        // Animate cards in
        requestAnimationFrame(() => {
            browserGrid.querySelectorAll('.browser-card').forEach(el => {
                el.classList.add('card-enter');
            });
        });

        // Click to add, right-click to zoom
        browserGrid.querySelectorAll('.browser-card').forEach(el => {
            el.addEventListener('click', () => addToDeck(el.dataset.code));
            el.addEventListener('contextmenu', e => {
                e.preventDefault();
                openLightbox(`/card-image/${el.dataset.code}`);
            });
        });
    }

    // -----------------------------------------------------------------
    // Deck Management
    // -----------------------------------------------------------------

    function addToDeck(code) {
        const current = deck[code] || 0;
        if (current >= 4) return;
        deck[code] = current + 1;
        updateDeck();
        refreshBrowserQty(code);
    }

    function removeFromDeck(code) {
        if (!deck[code]) return;
        deck[code]--;
        if (deck[code] <= 0) delete deck[code];
        updateDeck();
        refreshBrowserQty(code);
    }

    function refreshBrowserQty(code) {
        const el = browserGrid.querySelector(`[data-code="${code}"]`);
        if (!el) return;
        const qty = deck[code] || 0;
        el.classList.toggle('in-deck', qty > 0);
        const badge = el.querySelector('.browser-qty');
        if (qty > 0) {
            if (badge) {
                badge.textContent = `\u00d7${qty}`;
            } else {
                const imgWrapper = el.querySelector('.browser-card-img');
                const span = document.createElement('span');
                span.className = 'browser-qty';
                span.textContent = `\u00d7${qty}`;
                imgWrapper.appendChild(span);
            }
        } else if (badge) {
            badge.remove();
        }
    }

    function updateDeck() {
        const entries = Object.entries(deck);
        const total   = entries.reduce((sum, [, qty]) => sum + qty, 0);

        deckCount.textContent   = total;
        downloadBtn.disabled    = total === 0;
        saveBtn.disabled        = total === 0;

        const cardsHTML = entries.map(([code, qty]) => `
            <div class="deck-card" data-code="${code}">
                <img src="/card-image/${code}" alt="${code}" loading="lazy">
                <span class="deck-card-qty">\u00d7${qty}</span>
                <span class="deck-card-code">${code}</span>
                <div class="deck-card-controls">
                    <button class="qty-btn minus" data-code="${code}">\u2212</button>
                    <button class="qty-btn plus"  data-code="${code}">+</button>
                    <button class="deck-card-lib" data-code="${code}" title="Add to Library">\u2295</button>
                </div>
            </div>
        `).join('');

        deckList.innerHTML = `<div class="deck-empty" style="display:${entries.length ? 'none' : ''}">`
            + 'Click cards below to add them to your deck</div>' + cardsHTML;

        deckList.querySelectorAll('.qty-btn.minus').forEach(btn => {
            btn.addEventListener('click', e => { e.stopPropagation(); removeFromDeck(btn.dataset.code); });
        });
        deckList.querySelectorAll('.qty-btn.plus').forEach(btn => {
            btn.addEventListener('click', e => { e.stopPropagation(); addToDeck(btn.dataset.code); });
        });
        deckList.querySelectorAll('.deck-card').forEach(el => {
            el.addEventListener('click', () => openLightbox(`/card-image/${el.dataset.code}`));
        });
        deckList.querySelectorAll('.deck-card-lib').forEach(btn => {
            btn.addEventListener('click', e => { e.stopPropagation(); saveCardToLibrary(btn.dataset.code); });
        });

        // Update matchup panel whenever deck changes
        updateMatchupPanel();
    }

    clearBtn.addEventListener('click', () => {
        Object.keys(deck).forEach(k => delete deck[k]);
        updateDeck();
        browserGrid.querySelectorAll('.browser-card').forEach(el => {
            el.classList.remove('in-deck');
            const badge = el.querySelector('.browser-qty');
            if (badge) badge.remove();
        });
    });

    // -----------------------------------------------------------------
    // Per-card Save to Library
    // -----------------------------------------------------------------

    function saveCardToLibrary(code) {
        const qty = deck[code] || 1;
        const name = deckNameInput.value.trim() || 'Custom Deck';
        const savedDeck = {
            id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
            name: `${name} — ${code}`,
            cards: [{ code, qty }],
            totalCards: qty,
            uniqueCards: 1,
            leaderCode: code,
            savedAt: new Date().toISOString(),
        };
        const library = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        library.unshift(savedDeck);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(library));

        showFeedback(`${code} ×${qty} saved to Library!`);
    }

    // -----------------------------------------------------------------
    // Save full deck to Library
    // -----------------------------------------------------------------

    saveBtn.addEventListener('click', () => {
        const name    = deckNameInput.value.trim() || 'Custom Deck';
        const entries = Object.entries(deck);
        if (!entries.length) return;

        const total      = entries.reduce((sum, [, qty]) => sum + qty, 0);
        const leaderCode = entries[0][0];

        const library = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

        if (editingDeckId) {
            // Overwrite existing deck
            const idx = library.findIndex(d => d.id === editingDeckId);
            if (idx !== -1) {
                library[idx].name = name;
                library[idx].cards = entries.map(([code, qty]) => ({ code, qty }));
                library[idx].totalCards = total;
                library[idx].uniqueCards = entries.length;
                library[idx].leaderCode = leaderCode;
                library[idx].savedAt = new Date().toISOString();
                localStorage.setItem(STORAGE_KEY, JSON.stringify(library));
                showFeedback(`"${name}" updated in Library!`);
                return;
            }
        }

        // New deck
        const savedDeck = {
            id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
            name,
            cards: entries.map(([code, qty]) => ({ code, qty })),
            totalCards: total,
            uniqueCards: entries.length,
            leaderCode,
            savedAt: new Date().toISOString(),
        };

        library.unshift(savedDeck);
        editingDeckId = savedDeck.id;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(library));

        showFeedback(`"${name}" saved to Library!`);
    });

    function showFeedback(msg) {
        saveFeedback.textContent = msg;
        saveFeedback.classList.add('visible');
        setTimeout(() => saveFeedback.classList.remove('visible'), 2500);
    }

    // -----------------------------------------------------------------
    // Load deck from URL params (used by Library "Edit" button)
    // -----------------------------------------------------------------

    function loadFromParams() {
        const params = new URLSearchParams(window.location.search);
        const loadId = params.get('load');
        if (!loadId) return;

        const library = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        const saved   = library.find(d => d.id === loadId);
        if (!saved) return;

        editingDeckId = loadId;
        Object.keys(deck).forEach(k => delete deck[k]);
        saved.cards.forEach(c => { deck[c.code] = c.qty; });
        deckNameInput.value = saved.name;
        updateDeck();
    }

    // Auto-load cards on page open, then restore deck from URL params (library edit)
    loadCards(setFilter.value).then(() => loadFromParams());

    // -----------------------------------------------------------------
    // Matchup Panel
    // -----------------------------------------------------------------

    function updateMatchupPanel() {
        if (!metaData || !metaData.archetypes || !metaData.archetypes.length) {
            builderMatchupEmpty.style.display = '';
            builderMatchupCols.style.display  = 'none';
            builderMatchupEmpty.textContent   = 'No meta data available for matchup estimates';
            return;
        }

        const entries = Object.entries(deck);
        if (!entries.length) {
            builderMatchupEmpty.style.display = '';
            builderMatchupCols.style.display  = 'none';
            builderMatchupEmpty.textContent   = 'Build a deck to see matchup estimates';
            return;
        }

        // Try to guess which archetype this deck matches by checking card codes
        // against leader codes in each archetype
        const deckCodes = new Set(entries.map(([code]) => code));
        let bestArch    = null;
        let bestOverlap = 0;

        for (const arch of metaData.archetypes) {
            // Check if any deck in meta shares cards with the builder deck
            let overlap = 0;
            if (arch.leader_code && deckCodes.has(arch.leader_code)) {
                overlap += 10; // Strong signal: leader card match
            }
            if (overlap > bestOverlap) {
                bestOverlap = overlap;
                bestArch    = arch;
            }
        }

        // If no strong match, fall back to the top archetype as reference
        if (!bestArch) {
            bestArch = metaData.archetypes[0];
        }

        // Compute matchup using the same logic as the server
        const currentScore = bestArch.avg_placement;
        const others = metaData.archetypes.filter(a =>
            a.name !== bestArch.name && a.count >= 2
        );

        const threats   = others
            .filter(a => a.avg_placement < currentScore)
            .sort((a, b) => a.avg_placement - b.avg_placement)
            .slice(0, 5);

        const favorable = others
            .filter(a => a.avg_placement > currentScore)
            .sort((a, b) => b.avg_placement - a.avg_placement)
            .slice(0, 5);

        if (!threats.length && !favorable.length) {
            builderMatchupEmpty.style.display = '';
            builderMatchupCols.style.display  = 'none';
            builderMatchupEmpty.textContent   = 'Not enough meta data for matchup estimates';
            return;
        }

        builderMatchupEmpty.style.display = 'none';
        builderMatchupCols.style.display  = '';

        function renderRows(list, cls) {
            if (!list.length) return `<div class="builder-matchup-row" style="font-size:0.7rem;color:var(--text-secondary)">None</div>`;
            return list.map(a => `
                <div class="builder-matchup-row">
                    <div class="builder-matchup-thumb">
                        ${a.leader_code
                            ? `<img src="/card-image/${a.leader_code}" alt="${a.name}" loading="lazy">`
                            : ''}
                    </div>
                    <span class="builder-matchup-name" title="${a.name}">${a.name}</span>
                    <span class="builder-matchup-badge">${a.share}%</span>
                </div>
            `).join('');
        }

        builderMatchupCols.innerHTML = `
            <div class="builder-matchup-col threats">
                <h4>\u26a0 Threats</h4>
                ${renderRows(threats, 'threats')}
            </div>
            <div class="builder-matchup-col favorable">
                <h4>\u2714 Favorable</h4>
                ${renderRows(favorable, 'favorable')}
            </div>
        `;
    }

    // -----------------------------------------------------------------
    // PDF Download
    // -----------------------------------------------------------------

    downloadBtn.addEventListener('click', async function () {
        const cards = Object.entries(deck).map(([code, qty]) => ({ code, qty }));
        const name  = deckNameInput.value.trim() || 'Custom Deck';

        downloadBtn.textContent = 'Generating PDF\u2026';
        downloadBtn.disabled    = true;

        try {
            const resp = await fetch('/build-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cards, name }),
            });

            if (!resp.ok) throw new Error('PDF generation failed');

            const blob = await resp.blob();
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href     = url;
            a.download = `OPTCG_${name.replace(/[^a-zA-Z0-9 _-]/g, '')}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (e) {
            alert('Failed to generate PDF. Check that card images exist.');
        }

        downloadBtn.textContent = 'Download PDF';
        downloadBtn.disabled    = Object.keys(deck).length === 0;
    });

    // -----------------------------------------------------------------
    // Lightbox
    // -----------------------------------------------------------------

    function openLightbox(src) {
        lightboxImg.src = src;
        lightbox.classList.add('active');
    }

    lightbox.addEventListener('click', () => {
        lightbox.classList.remove('active');
        lightboxImg.src = '';
    });

    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && lightbox.classList.contains('active')) {
            lightbox.classList.remove('active');
            lightboxImg.src = '';
        }
    });
})();
