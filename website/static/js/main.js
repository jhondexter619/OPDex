/* OPDex — Chart + Search (Dark Mode, scroll-triggered) */

// ---------------------------------------------------------------------------
// Top 5 Bar Chart — deferred until visible
// ---------------------------------------------------------------------------

(function () {
    const canvas = document.getElementById('top5Chart');
    if (!canvas || typeof top5Data === 'undefined') return;

    let chartCreated = false;

    function createChart() {
        if (chartCreated) return;
        chartCreated = true;

        const labels = top5Data.map(d => d.name);
        const values = top5Data.map(d => d.count);
        const shares = top5Data.map(d => d.share);

        const colors = [
            '#f85149', // red
            '#58a6ff', // blue
            '#3fb950', // green
            '#d29922', // amber
            '#bc8cff', // violet
        ];

        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Deck Count',
                    data: values,
                    backgroundColor: colors.slice(0, values.length),
                    borderRadius: 4,
                    maxBarThickness: 60,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 900,
                    easing: 'easeOutQuart',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1c2128',
                        borderColor: '#30363d',
                        borderWidth: 1,
                        titleColor: '#e6edf3',
                        bodyColor: '#e6edf3',
                        callbacks: {
                            label: function (ctx) {
                                const i = ctx.dataIndex;
                                return `${values[i]} decks (${shares[i]}% of meta)`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0, color: '#8b949e' },
                        grid: { color: '#21262d' },
                    },
                    y: {
                        grid: { display: false },
                        ticks: {
                            color: '#e6edf3',
                            font: { weight: '600', size: 13 },
                        },
                    },
                },
            },
        });
    }

    // Defer chart creation until the section scrolls into view
    const section = document.getElementById('chartSection');
    if (section) {
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) {
                    createChart();
                    observer.disconnect();
                }
            },
            { threshold: 0.15 }
        );
        observer.observe(section);
    } else {
        createChart();
    }
})();


// ---------------------------------------------------------------------------
// Deck Table Search
// ---------------------------------------------------------------------------

(function () {
    const input = document.getElementById('deckSearch');
    const table = document.getElementById('deckTable');
    if (!input || !table) return;

    const rows = Array.from(table.querySelectorAll('tbody tr'));

    input.addEventListener('input', function () {
        const q = this.value.toLowerCase();
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(q) ? '' : 'none';
        });
    });
})();
