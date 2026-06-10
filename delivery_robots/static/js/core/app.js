async function init() {
    try {
        simulation = new Simulation();
        window.simulation = simulation;
        await simulation.initialize();
        setupControls();
        setupWeather();
        setupInsiderControls();
        startPolling();
        updateClock();
        logEvent('✅ Ready');
    } catch (error) {
        console.error('Init error:', error);
        logEvent('❌ ' + error.message);
    }
}

function setupControls() {
    document.getElementById('start-btn')?.addEventListener('click', () => simulation?.start());
    document.getElementById('pause-btn')?.addEventListener('click', () => simulation?.pause());
    document.getElementById('reset-btn')?.addEventListener('click', () => simulation?.reset());
    document.getElementById('optimize-hubs-btn')?.addEventListener('click', () => simulation?.optimizeHubs());
    document.getElementById('apply-fleet-algo-btn')?.addEventListener('click', () => {
        const selected = document.getElementById('fleet-algo-select')?.value || CONFIG.SIMULATION.DEFAULT_ALGORITHM;
        simulation?.setFleetAlgorithm(selected);
        Alpine.store('sim').metrics.fleetAlgo = selected.toUpperCase();
    });

    const slider = document.getElementById('speed-slider');
    slider?.addEventListener('input', (e) => {
        if (simulation) simulation.speed = +e.target.value;
        Alpine.store('sim').metrics.speed = e.target.value + 'x';
    });
}

function startPolling() {
    fetchMetrics();
    setInterval(fetchMetrics, CONFIG.UI.METRICS_REFRESH_INTERVAL_MS);
    setInterval(refreshComputingPanel, CONFIG.UI.COMPUTING_PANEL_REFRESH_INTERVAL_MS);
    setInterval(updateClock, 1000);
}

async function fetchMetrics() {
    try {
        const d = await getJson(CONFIG.API.METRICS, null, 'Metrics request failed');
        Alpine.store('sim').updateMetrics(d);
    } catch (e) {
        console.error('Metrics:', e);
    }
}

function refreshComputingPanel() {
    const store = Alpine.store('sim');
    if (!store.panels.computing || !simulation?.robots) return;

    const content = store.computing;
    if (!content.robotId) return;

    const robot = simulation.robots.find(r => r.id == content.robotId);
    if (robot) store.computing.details = robot.getComputingDetails();
}

async function updateClock() {
    try {
        const d = await getJson(CONFIG.API.CLOCK, null, 'Clock request failed');
        const store = Alpine.store('sim');
        store.clock = d.time.display;
        store.rushHour.active = d.rushHour.isActive;
        store.rushHour.multiplier = d.rushHour.multiplier;
    } catch (e) { }
}

window.addEventListener('load', () => {
    init().catch(e => {
        console.error(e);
        logEvent('❌ Init failed');
    });
});
