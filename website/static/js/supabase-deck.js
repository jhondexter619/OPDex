/* OPDex — Supabase deck store (CRUD via Flask API with auth) */

(function () {
    'use strict';

    window.deckStore = {
        async list() {
            const resp = await opdexAuth.fetchWithAuth('/api/decks');
            if (!resp.ok) return [];
            return resp.json();
        },

        async save(deck) {
            const resp = await opdexAuth.fetchWithAuth('/api/decks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(deck),
            });
            if (!resp.ok) throw new Error('Failed to save deck');
            return resp.json();
        },

        async update(id, deck) {
            const resp = await opdexAuth.fetchWithAuth('/api/decks/' + id, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(deck),
            });
            if (!resp.ok) throw new Error('Failed to update deck');
            return resp.json();
        },

        async remove(id) {
            const resp = await opdexAuth.fetchWithAuth('/api/decks/' + id, {
                method: 'DELETE',
            });
            if (!resp.ok) throw new Error('Failed to delete deck');
            return true;
        },

        async togglePublic(id, isPublic) {
            return this.update(id, { is_public: isPublic });
        },
    };
})();
