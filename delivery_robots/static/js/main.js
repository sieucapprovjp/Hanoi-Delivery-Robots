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
        await setupDispatchControls();
        await fetchMetrics(true);
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

async function setupDispatchControls() {
    const select = document.getElementById('dispatch-model-select');
    if (!select) return;

    try {
        const api = new BackendAPI();
        const res = await api.getDispatchModel();
        select.value = res.model;
    } catch (e) {
        console.error('Failed to load initial dispatch model:', e);
    }

    select.addEventListener('change', async (e) => {
        const model = e.target.value;
        try {
            const api = new BackendAPI();
            await api.setDispatchModel(model);
            logEvent(`🔄 Dispatch model updated to: ${model}`);
        } catch (err) {
            console.error('Failed to set dispatch model:', err);
            logEvent(`❌ Failed to update dispatch model`);
        }
    });
}

window.appendDispatchInsight = function (message) {
    const container = document.getElementById('dispatch-insights');
    if (!container) return;

    const placeholder = container.querySelector('.info-text');
    if (placeholder) {
        container.innerHTML = '';
    }

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const entry = document.createElement('div');

    let toneClass = '';
    const lowerMsg = message.toLowerCase();
    if (lowerMsg.includes('failed') || lowerMsg.includes('expired') || lowerMsg.includes('routing failed')) {
        toneClass = 'warn';
    } else if (lowerMsg.includes('assigned') || lowerMsg.includes('delivered')) {
        toneClass = 'good';
    }

    entry.className = `dispatch-entry ${toneClass}`;
    entry.innerHTML = `
        <div class="dispatch-time">${timeStr}</div>
        <div class="dispatch-text">${message}</div>
    `;

    container.insertBefore(entry, container.firstChild);
};

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

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});