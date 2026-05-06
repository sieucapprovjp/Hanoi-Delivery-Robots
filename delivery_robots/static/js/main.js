let displayEngine;
let mapManager;
let pathfindingManager;
let environmentManager;

function logEvent(message) {
    fetch(CONFIG.API.LOGS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            level: CONFIG.UI.LOG_LEVELS.INFO,
            source: CONFIG.UI.LOG_SOURCES.UI,
            ts: Date.now()
        })
    }).catch(() => { });
}

function addDispatchInsight(message, tone = CONFIG.UI.LOG_LEVELS.NEUTRAL) {
    fetch(CONFIG.API.LOGS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            level: tone,
            source: CONFIG.UI.LOG_SOURCES.DISPATCH,
            ts: Date.now()
        })
    }).catch(() => { });
}


async function init() {
    try {
        displayEngine = new DisplayEngine();
        window.displayEngine = displayEngine;
        await displayEngine.initialize();

        // Initialize Environment Features
        environmentManager = new EnvironmentManager();
        window.environmentManager = environmentManager;
        environmentManager.initialize();

        setupControls();
        await fetchMetrics(true);
        await updateClock(true);
        logEvent('✅ Display Ready');
    } catch (error) {
        console.error('Init error:', error);
        logEvent('❌ ' + error.message);
    }
}

function setupControls() {
    document.getElementById('start-btn')?.addEventListener('click', () => displayEngine?.start());
    document.getElementById('pause-btn')?.addEventListener('click', () => displayEngine?.pause());
    document.getElementById('reset-btn')?.addEventListener('click', () => displayEngine?.reset());

    const slider = document.getElementById('speed-slider');
    slider?.addEventListener('input', (e) => {
        if (displayEngine) displayEngine.speed = +e.target.value;
        Alpine.store('sim').metrics.speed = e.target.value + 'x';
    });
}

// ===== METRICS =====
async function fetchMetrics(isFull = false) {
    try {
        const url = isFull ? `${CONFIG.API.METRICS}?static=true` : CONFIG.API.METRICS;
        const d = await (await fetch(url)).json();
        Alpine.store('sim').updateMetrics(d);
    } catch (e) { console.error('Metrics:', e); }
}

setInterval(() => {
    fetchMetrics();
}, CONFIG.UI.METRICS_REFRESH_INTERVAL_MS);

async function updateClock(isFull = false) {
    try {
        const url = isFull ? `${CONFIG.API.CLOCK}?full=true` : CONFIG.API.CLOCK;
        const d = await (await fetch(url)).json();
        const store = Alpine.store('sim');
        if (store) {
            store.clock = d.time.display;
            store.rushHour.active = d.rushHour.isActive;
            store.rushHour.multiplier = d.rushHour.multiplier;
        }
    } catch (e) { }
}

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});

