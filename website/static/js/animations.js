/* OPDex — Scroll reveal, stagger, and bar animations */

(function () {
    'use strict';

    // -----------------------------------------------------------------
    // Intersection Observer — reveal sections on scroll
    // -----------------------------------------------------------------
    const revealObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.08 }
    );

    document.querySelectorAll('.reveal').forEach((el) => {
        revealObserver.observe(el);
    });

    // -----------------------------------------------------------------
    // Stagger children — assign --i custom property + trigger play
    // -----------------------------------------------------------------
    function initStagger(parent) {
        const children = parent.tagName === 'TBODY'
            ? parent.querySelectorAll('tr')
            : parent.children;

        Array.from(children).forEach((child, i) => {
            child.style.setProperty('--i', i);
        });
    }

    const staggerObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    initStagger(entry.target);
                    entry.target.classList.add('animated');
                    staggerObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.05 }
    );

    document.querySelectorAll('.stagger, .stagger-rows').forEach((el) => {
        staggerObserver.observe(el);
    });

    // -----------------------------------------------------------------
    // Archetype progress bars — animate width on scroll
    // -----------------------------------------------------------------
    const barObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const bars = entry.target.querySelectorAll('.arch-bar-fill[data-width]');
                    bars.forEach((bar) => {
                        const w = bar.getAttribute('data-width');
                        // Small delay so the card entrance finishes first
                        requestAnimationFrame(() => {
                            setTimeout(() => {
                                bar.style.width = w + '%';
                                bar.classList.add('grown');
                            }, 300);
                        });
                    });
                    barObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1 }
    );

    document.querySelectorAll('.archetype-grid').forEach((el) => {
        barObserver.observe(el);
    });

    // -----------------------------------------------------------------
    // Archetype card color tinting — based on leader card color from DB
    // -----------------------------------------------------------------
    const OPTCG_COLORS = {
        Red:    { bg: 'rgba(248, 81, 73, 0.18)',  accent: '#f85149' },
        Green:  { bg: 'rgba(63, 185, 80, 0.18)',  accent: '#3fb950' },
        Blue:   { bg: 'rgba(88, 166, 255, 0.18)', accent: '#58a6ff' },
        Purple: { bg: 'rgba(188, 140, 255, 0.18)',accent: '#bc8cff' },
        Black:  { bg: 'rgba(110, 118, 129, 0.22)',accent: '#6e7681' },
        Yellow: { bg: 'rgba(227, 179, 65, 0.18)', accent: '#e3b341' },
    };

    document.querySelectorAll('.archetype-card').forEach((card) => {
        const raw = (card.dataset.leaderColor || '').trim();
        if (!raw) return;

        // Split "Red/Blue" into ["Red", "Blue"] — order from DB is preserved
        const colors = raw.split('/').map(s => s.trim()).filter(s => OPTCG_COLORS[s]);
        if (!colors.length) return;

        const barFill = card.querySelector('.arch-bar-fill');

        if (colors.length === 1) {
            const c = OPTCG_COLORS[colors[0]];
            card.style.background = c.bg;
            card.style.borderColor = c.accent + '33';
            if (barFill) barFill.style.background = c.accent;
        } else {
            // Dual color gradient — left to right, preserving card color order
            const stops = colors.map((c, i) => {
                return OPTCG_COLORS[c].bg + ' ' + Math.round(i / (colors.length - 1) * 100) + '%';
            });
            card.style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
            card.style.borderColor = OPTCG_COLORS[colors[0]].accent + '33';

            if (barFill) {
                const barStops = colors.map((c, i) => {
                    return OPTCG_COLORS[c].accent + ' ' + Math.round(i / (colors.length - 1) * 100) + '%';
                });
                barFill.style.background = 'linear-gradient(90deg, ' + barStops.join(', ') + ')';
            }
        }

        const hoverAccent = OPTCG_COLORS[colors[0]].accent;
        card.addEventListener('mouseenter', () => { card.style.borderColor = hoverAccent; });
        card.addEventListener('mouseleave', () => { card.style.borderColor = OPTCG_COLORS[colors[0]].accent + '33'; });
    });
})();
