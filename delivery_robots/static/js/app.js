// Globals
let weatherMode = CONFIG.UI.INITIAL_WEATHER;
let rainCircles = [];
let trafficPolylines = [];
let obstacleCircles = [];
let weatherModeEnabled = false;
let insiderLayers = [];
let trafficPointA = null;
let trafficPointMarkerA = null;

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

function togglePanel(panelKey) {
    const store = Alpine.store('sim');
    store.panels[panelKey] = !store.panels[panelKey];
}

async function init() {
    try {
        simulation = new Simulation();
        window.simulation = simulation;
        await simulation.initialize();
        setupControls();
        setupWeather();
        updateClock();
        setInterval(updateClock, 1000);
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

function setupWeather() {
    // Actions
    document.getElementById('randomize-rain-btn')?.addEventListener('click', randomizeRain);
    document.getElementById('clear-rain-btn')?.addEventListener('click', clearRain);
    document.getElementById('reset-traffic-points-btn')?.addEventListener('click', resetTrafficPoints);
    document.getElementById('randomize-traffic-btn')?.addEventListener('click', randomizeTraffic);
    document.getElementById('clear-traffic-btn')?.addEventListener('click', clearTraffic);
    document.getElementById('randomize-obstacle-btn')?.addEventListener('click', randomizeObstacles);
    document.getElementById('clear-obstacle-btn')?.addEventListener('click', clearObstacles);

    // Map click
    const setupMapClick = () => {
        const map = window.map;
        if (map && typeof map.on === 'function') {
            map.on('click', function (e) {
                const store = Alpine.store('sim');
                if (!store.panels.weather) return;
                if (store.weather.mode === CONFIG.UI.WEATHER_MODES.RAIN) addRainZone(e.latlng.lat, e.latlng.lng, +store.weather.rainRadius);
                else if (store.weather.mode === CONFIG.UI.WEATHER_MODES.TRAFFIC) handleTrafficClick(e.latlng.lat, e.latlng.lng);
            });
            console.log('Map click listener ready');
        } else {
            console.warn('Map not ready, retrying in 500ms...');
            setTimeout(setupMapClick, 500);
        }
    };
    setTimeout(setupMapClick, 500);

    updateRainList().catch(() => { });
    updateTrafficList().catch(() => { });
    updateObstacleList().catch(() => { });
}

function resetTrafficPoints() {
    trafficPointA = null;
    if (trafficPointMarkerA && window.map) window.map.removeLayer(trafficPointMarkerA);
    trafficPointMarkerA = null;
    logEvent('🔄 Traffic points reset');
}

function handleTrafficClick(lat, lon) {
    if (!window.map) return;

    const severity = +document.getElementById('traffic-severity')?.value || CONFIG.SIMULATION.DEFAULT_TRAFFIC_SEVERITY;

    if (!trafficPointA) {
        trafficPointA = { lat, lon };
        if (trafficPointMarkerA) window.map.removeLayer(trafficPointMarkerA);
        trafficPointMarkerA = L.circleMarker([lat, lon], {
            radius: CONFIG.UI.RADII.markerLarge,
            color: CONFIG.ROBOT.COLORS.error,
            fillColor: CONFIG.ROBOT.COLORS.error,
            fillOpacity: 1
        }).addTo(window.map);
        trafficPointMarkerA.bindPopup('<strong>Traffic start</strong><br>Click another point to set the end.');
        logEvent('🚗 Traffic start set');
        return;
    }

    const trafficPointB = { lat, lon };
    addTrafficRoute(trafficPointA, trafficPointB, severity).finally(() => resetTrafficPoints());
}

async function addTrafficRoute(start, end, severity) {
    const res = await fetch(CONFIG.API.TRAFFIC_ADD, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            startLat: start.lat,
            startLon: start.lon,
            endLat: end.lat,
            endLon: end.lon,
            severity
        })
    });
    const d = await res.json();
    if (!res.ok) {
        logEvent('❌ Traffic: ' + (d.error || res.status));
        return;
    }

    const route = d.route;
    if (route?.path?.length) {
        trafficPolylines.push(
            L.polyline(route.path.map(p => [p.lat, p.lon]), { color: CONFIG.ROBOT.COLORS.error, weight: CONFIG.UI.WEIGHTS.thick, opacity: CONFIG.UI.OPACITY.high })
                .addTo(window.map)
                .bindPopup(`<strong>${route.name}</strong><br>Severity: ${route.severity.toFixed(2)}`)
        );
    }
    updateTrafficList().catch(() => { });
    logEvent('🚗 ' + route.name);
}

function clearInsiderLayers() {
    insiderLayers.forEach(layer => {
        if (window.map && layer) {
            window.map.removeLayer(layer);
        }
    });
    insiderLayers = [];
}

function renderAStarOverlay(data) {
    if (!window.map) return;
    clearInsiderLayers();

    const exploredPath = data.exploredPath || [];
    exploredPath.forEach((point, index) => {
        const marker = L.circleMarker([point.lat, point.lon], {
            radius: index === exploredPath.length - 1 ? CONFIG.UI.RADII.markerMedium : CONFIG.UI.RADII.markerSmall,
            color: index === exploredPath.length - 1 ? CONFIG.ROBOT.COLORS.highlight : CONFIG.ROBOT.COLORS.info,
            fillColor: index === exploredPath.length - 1 ? CONFIG.ROBOT.COLORS.highlight : CONFIG.UI.COLORS.highlight,
            fillOpacity: 0.75,
            weight: 1
        }).addTo(window.map);
        insiderLayers.push(marker);
    });

    if (data.path?.length) {
        const pathLine = L.polyline(data.path.map(p => [p.lat, p.lon]),
            { color: CONFIG.UI.COLORS.secondary, weight: CONFIG.UI.WEIGHTS.thick, opacity: CONFIG.UI.OPACITY.overlay }
        ).addTo(window.map);
        insiderLayers.push(pathLine);

        const start = data.path[0];
        const end = data.path[data.path.length - 1];
        insiderLayers.push(
            L.circleMarker([start.lat, start.lon], {
                radius: CONFIG.UI.RADII.markerLarge, color: CONFIG.UI.COLORS.success, fillColor: CONFIG.UI.COLORS.success, fillOpacity: CONFIG.UI.OPACITY.full
            }).addTo(window.map)
        );
        insiderLayers.push(
            L.circleMarker([end.lat, end.lon], {
                radius: CONFIG.UI.RADII.markerLarge, color: CONFIG.ROBOT.COLORS.error, fillColor: CONFIG.ROBOT.COLORS.error, fillOpacity: 1
            }).addTo(window.map)
        );
    }
}

// ===== WEATHER ACTIONS =====
async function addRainZone(lat, lon, radius) {
    const res = await fetch(CONFIG.API.RAIN_ADD, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat, lon, radius }) });
    const d = await res.json();
    if (res.ok) { displayRainZone(d.rainZone); updateRainList(); logEvent('🌧️ ' + d.rainZone.name); }
}

function displayRainZone(z) {
    if (!window.map) return;
    const c = L.circle([z.center.lat, z.center.lon], { color: CONFIG.ROBOT.COLORS.info, fillColor: CONFIG.ROBOT.COLORS.info, fillOpacity: 0.2, radius: z.radius }).addTo(window.map);
    c.bindPopup(`<strong>${z.name}</strong><br>Radius: ${Math.round(z.radius)}m`);
    rainCircles.push(c);
}

async function updateRainList() {
    const d = await (await fetch(CONFIG.API.RAIN_LIST)).json();
    const html = d.rainZones.length ? d.rainZones.map((z, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${z.name}</strong><br>${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m</div>`).join('') : 'No rain zones';
    Alpine.store('sim').weather.rainZonesHtml = html;
}

async function randomizeRain() {
    const d = await (await fetch(CONFIG.API.RAIN_RANDOMIZE, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count: CONFIG.SIMULATION.RANDOM_RAIN_COUNT, minRadius: CONFIG.SIMULATION.RANDOM_RAIN_MIN_RADIUS, maxRadius: CONFIG.SIMULATION.RANDOM_RAIN_MAX_RADIUS }) })).json();
    rainCircles.forEach(c => window.map.removeLayer(c)); rainCircles = [];
    d.rainZones.forEach(z => displayRainZone(z)); updateRainList(); logEvent('🎲 Rain');
}

async function clearRain() {
    await fetch(CONFIG.API.RAIN_CLEAR, { method: 'POST' });
    rainCircles.forEach(c => window.map.removeLayer(c)); rainCircles = []; updateRainList(); logEvent('🗑️ Rain');
}

async function randomizeTraffic() {
    const d = await (await fetch(CONFIG.API.TRAFFIC_RANDOMIZE, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count: CONFIG.SIMULATION.RANDOM_TRAFFIC_COUNT }) })).json();
    trafficPolylines.forEach(p => window.map.removeLayer(p)); trafficPolylines = [];
    d.routes.forEach(r => {
        trafficPolylines.push(L.polyline(r.path.map(p => [p.lat, p.lon]), { color: CONFIG.ROBOT.COLORS.error, weight: CONFIG.UI.WEIGHTS.thick, opacity: CONFIG.UI.OPACITY.high }).addTo(window.map));
    });
    updateTrafficList(); logEvent('🎲 Traffic');
}

async function clearTraffic() {
    await fetch(CONFIG.API.TRAFFIC_CLEAR, { method: 'POST' });
    trafficPolylines.forEach(p => window.map.removeLayer(p)); trafficPolylines = []; updateTrafficList(); logEvent('🗑️ Traffic');
}

async function updateTrafficList() {
    const d = await (await fetch(CONFIG.API.TRAFFIC_LIST)).json();
    const html = d.routes.length ? d.routes.map((r, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('') : 'No traffic routes';
    Alpine.store('sim').weather.trafficRoutesHtml = html;
}

async function addObstacle(lat, lon, radius, severity) {
    const res = await fetch(CONFIG.API.OBSTACLE_ADD, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lat, lon, radius, severity, type: CONFIG.SIMULATION.DEFAULT_OBSTACLE_TYPE }) });
    const d = await res.json();
    if (res.ok) { displayObstacle(d.obstacle); updateObstacleList(); logEvent('🚧 ' + d.obstacle.name); }
}

function displayObstacle(o) {
    if (!window.map) return;
    const colors = CONFIG.DATA.OBSTACLE_COLORS;
    const c = L.circle([o.center.lat, o.center.lon], { color: colors[o.type] || CONFIG.ROBOT.COLORS.error, fillColor: colors[o.type] || CONFIG.ROBOT.COLORS.error, fillOpacity: CONFIG.UI.OPACITY.medium, radius: o.radius }).addTo(window.map);
    c.bindPopup(`<strong>${o.name}</strong><br>Severity: ${o.severity.toFixed(1)}`);
    obstacleCircles.push(c);
}

async function updateObstacleList() {
    const d = await (await fetch(CONFIG.API.OBSTACLE_LIST)).json();
    const html = d.obstacles.length ? d.obstacles.map((o, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${o.name}</strong><br>${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}</div>`).join('') : 'No obstacles';
    Alpine.store('sim').weather.obstaclesHtml = html;
}

async function randomizeObstacles() {
    const d = await (await fetch(CONFIG.API.OBSTACLE_RANDOMIZE, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count: CONFIG.SIMULATION.RANDOM_OBSTACLE_COUNT }) })).json();
    obstacleCircles.forEach(c => window.map.removeLayer(c)); obstacleCircles = [];
    d.obstacles.forEach(o => displayObstacle(o)); updateObstacleList(); logEvent('🎲 Obstacles');
}

async function clearObstacles() {
    await fetch(CONFIG.API.OBSTACLE_CLEAR, { method: 'POST' });
    obstacleCircles.forEach(c => window.map.removeLayer(c)); obstacleCircles = []; updateObstacleList(); logEvent('🗑️ Obstacles');
}

// ===== METRICS =====
async function fetchMetrics() {
    try {
        const d = await (await fetch(CONFIG.API.METRICS)).json();
        Alpine.store('sim').updateMetrics(d);
    } catch (e) { console.error('Metrics:', e); }
}

setInterval(() => {
    fetchMetrics();
}, CONFIG.UI.METRICS_REFRESH_INTERVAL_MS);

// Auto-refresh computing panel every 2s
setInterval(() => {
    const store = Alpine.store('sim');
    if (store.panels.computing && simulation?.robots) {
        const content = store.computing;
        if (content.robotId) {
            const robot = simulation.robots.find(r => r.id == content.robotId);
            if (robot) store.computing.details = robot.getComputingDetails();
        }
    }
}, CONFIG.UI.COMPUTING_PANEL_REFRESH_INTERVAL_MS);

// ===== A* Visualization =====
async function showAStarProcess(robotId) {
    const store = Alpine.store('sim');
    if (!simulation?.robots) return;

    const robot = simulation.robots.find(r => r.id === robotId);
    if (!robot || !robot.routeTarget) {
        store.insider.astarSteps = '<div class="p-10 text-center color-secondary-text">Robot has no active route. Wait for it to accept a delivery.</div>';
        return;
    }

    store.insider.astarSteps = '<div class="p-10 text-center">⏳ Computing A*...</div>';

    try {
        const d = await (await fetch(`${CONFIG.API.ASTEP}?fromLat=${robot.lat}&fromLon=${robot.lon}&toLat=${robot.routeTarget.lat}&toLon=${robot.routeTarget.lon}`)).json();

        if (!d.steps || d.steps.length === 0) {
            store.insider.astarSteps = '<div class="p-10 text-center color-error">No steps recorded</div>';
            return;
        }

        // Build step-by-step visualization using CSS classes
        let html = `
            <div class="astar-viz-container">
                <div class="astar-viz-header">
                    🔬 A* Step-by-Step Calculation
                    <span class="fs-10 color-secondary-text fw-400">(${d.calcTime}ms, ${d.totalSteps} steps)</span>
                </div>
                
                <div class="astar-viz-summary">
                    <div class="fs-10 color-secondary-text mb-4"><strong>Start:</strong> Node ${d.startNode} → <strong>Goal:</strong> Node ${d.endNode}</div>
                    <div class="d-flex gap-8 fs-9 color-secondary-text">
                        <span>Open Set: <strong>${d.openSetSize}</strong></span>
                        <span>Closed Set: <strong>${d.closedSetSize}</strong></span>
                        <span>Path: <strong class="color-primary">${d.pathLength} nodes</strong></span>
                    </div>
                </div>
        `;

        d.steps.slice(0, 3).forEach(s => {
            const color = s.step === 1 ? CONFIG.ROBOT.COLORS.good : s.step === 2 ? CONFIG.ROBOT.COLORS.info : CONFIG.ROBOT.COLORS.highlight;
            html += `
                <div class="astar-viz-step" style="--step-color: ${color}">
                    <div class="d-flex justify-between align-center mb-4">
                        <span class="fs-11 fw-700 step-color-text">Step ${s.step}</span>
                        <span class="fs-9" style="color:${CONFIG.UI.COLORS.textLight};">Node ${s.currentNode}</span>
                    </div>
                    <div class="astar-viz-formula">${s.formula}</div>
                    <div class="d-flex gap-12 fs-9" style="color:${CONFIG.UI.COLORS.textLight};">
                        <span>g=${s.g}</span><span>h=${s.h}</span><span>f=${s.f}</span>
                        <span>Open:${s.openSetSize}</span><span>Closed:${s.closedSetSize}</span>
                    </div>
                </div>
            `;
        });

        if (d.steps.length > 3) {
            html += `
                <div class="text-center p-8 fs-10 bg-surface br-6 mb-4" style="color:${CONFIG.UI.COLORS.textLight};">
                    ... ${d.steps.length - 3} more steps ...
                </div>
                <div class="astar-viz-step" style="border-left-color: ${CONFIG.ROBOT.COLORS.good}">
                    <div class="fs-11 fw-700" style="color:${CONFIG.ROBOT.COLORS.good};">✅ Goal Reached! (Step ${d.totalSteps})</div>
                    <div class="fs-10" style="color:${CONFIG.UI.COLORS.textLight};">Path reconstructed: ${d.pathLength} nodes</div>
                </div>
            `;
        }

        const hasRain = rainCircles.length > 0;
        const hasTraffic = trafficPolylines.length > 0;
        const hasObstacles = obstacleCircles.length > 0;

        html += `
                <div class="bg-surface br-8 p-8 mt-6">
                    <div class="fs-10 fw-700 mb-4">⚙️ Penalties Applied:</div>
                    <div class="d-flex gap-6 flex-wrap fs-9">
                        ${hasRain ? `<span class="penalty-badge bg-rain-penalty">🌧️ Rain: ${CONFIG.ROBOT.RAIN_REROUTE_THRESHOLD}×</span>` : ''}
                        ${hasTraffic ? `<span class="penalty-badge bg-traffic-penalty">🚗 Traffic: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 2.5}×</span>` : ''}
                        ${hasObstacles ? `<span class="penalty-badge bg-obstacle-penalty">🚧 Obstacles: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 3}×</span>` : ''}
                    </div>
                </div>
            </div>
        `;

        store.insider.astarSteps = html;
        renderAStarOverlay(d);
    } catch (e) {
        store.insider.astarSteps = `<div class="p-10 text-center color-error">Error: ${e.message}</div>`;
    }
}

// Make it global
window.showAStarProcess = showAStarProcess;

// ===== Insider Panel =====
async function runInsiderComparison() {
    const store = Alpine.store('sim');
    store.insider.comparison = '<div class="p-10 text-center">⏳ Running 4 algorithms...</div>';

    try {
        const from = CONFIG.DATA.LOCATIONS[0];
        const to = CONFIG.DATA.LOCATIONS[1];
        const d = await (await fetch(`${CONFIG.API.INSIDER}?fromLat=${from.lat}&fromLon=${from.lon}&toLat=${to.lat}&toLon=${to.lon}`)).json();

        const algos = d.algorithms;
        const best = d.best_path_length;

        const rows = [
            { name: "A* (Informed)", ...algos["A*"], icon: "⭐" },
            { name: "Dijkstra (Uninformed)", ...algos["Dijkstra"], icon: "🔵" },
            { name: "Greedy Best-First", ...algos["Greedy Best-First"], icon: "🟡" },
            { name: "BFS (Blind)", ...algos["BFS"], icon: "🟢" },
        ];

        const bestTime = Math.min(...rows.map(r => r.time_ms));

        let html = `
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>Algorithm</th>
                        <th class="text-center">Nodes</th>
                        <th class="text-center">Path</th>
                        <th class="text-center">Time</th>
                        <th class="text-center">Optimal?</th>
                        <th class="text-center">Efficiency</th>
                    </tr>
                </thead>
                <tbody>
        `;

        rows.forEach(r => {
            const isAStar = r.name.startsWith("A*");
            const optimal = r.optimal ? `<span style="color:${CONFIG.UI.COLORS.success};">✅ Yes</span>` : `<span style="color:${CONFIG.UI.COLORS.error};">❌ No</span>`;
            const eff = best > 0 ? ((r.path_length / best) * 100).toFixed(0) + '%' : 'N/A';
            const effColor = eff === '100%' ? CONFIG.UI.COLORS.success : CONFIG.UI.COLORS.error;
            const timeBadge = r.time_ms === bestTime ? '⚡ ' : '';
            const timeColor = r.time_ms === bestTime ? CONFIG.UI.COLORS.success : CONFIG.UI.COLORS.textLight;

            html += `
                <tr class="${isAStar ? 'best-row' : ''}">
                    <td>${r.icon} ${r.name}</td>
                    <td class="text-center">${r.nodes_explored}</td>
                    <td class="text-center">${r.path_length} nodes</td>
                    <td class="text-center" style="color:${timeColor};">${timeBadge}${r.time_ms}ms</td>
                    <td class="text-center">${optimal}</td>
                    <td class="text-center" style="color:${effColor};">${eff}</td>
                </tr>
            `;
        });

        html += `</tbody></table>`;

        const astarNodes = algos["A*"].nodes_explored;
        const dijkstraNodes = algos["Dijkstra"].nodes_explored;
        const speedup = dijkstraNodes > 0 ? ((1 - astarNodes / dijkstraNodes) * 100).toFixed(0) : 0;

        html += `
            <div class="insight-box">
                <strong>💡 Key Insight:</strong> A* explored <strong>${astarNodes}</strong> nodes vs Dijkstra's <strong>${dijkstraNodes}</strong> — that's <strong class="color-success">${speedup}% fewer nodes</strong> while finding the same optimal path!
            </div>
        `;

        store.insider.comparison = html;
    } catch (e) {
        store.insider.comparison = `<div class="p-10 text-center color-error">Error: ${e.message}</div>`;
    }
}

async function runAStarVisualization() {
    const store = Alpine.store('sim');
    store.insider.astarSteps = '<div class="p-10 text-center">⏳ Running A* step-by-step...</div>';

    try {
        const from = CONFIG.DATA.LOCATIONS[0];
        const to = CONFIG.DATA.LOCATIONS[1];
        const d = await (await fetch(`${CONFIG.API.ASTEP}?fromLat=${from.lat}&fromLon=${from.lon}&toLat=${to.lat}&toLon=${to.lon}`)).json();

        if (!d.steps || d.steps.length === 0) {
            store.insider.astarSteps = '<div class="p-10 text-center color-error">No steps to visualize</div>';
            return;
        }

        renderAStarOverlay(d);

        let html = `
            <div class="astar-viz-header">
                🔬 A* Expansion (${d.totalSteps} steps, ${d.calcTime}ms)
            </div>
            
            <div class="d-flex gap-6 mb-8 fs-9 color-secondary-text">
                <span>Start: Node ${d.startNode}</span>
                <span>→ Goal: Node ${d.endNode}</span>
                <span>→ Path: ${d.pathLength} nodes</span>
            </div>
        `;

        d.steps.forEach((s, i) => {
            const color = i === 0 ? CONFIG.UI.COLORS.success : i === d.steps.length - 1 ? CONFIG.UI.COLORS.error : CONFIG.ROBOT.COLORS.info;
            const bg = i === 0 ? CONFIG.UI.COLORS.successLight : i === d.steps.length - 1 ? CONFIG.UI.COLORS.errorLight : CONFIG.UI.COLORS.background;

            html += `
                <div class="astar-viz-step" style="background:${bg};--step-color:${color};">
                    <div class="d-flex justify-between align-center">
                        <span class="fw-700 step-color-text">Step ${s.step}</span>
                        <span class="mono fs-9">Node ${s.currentNode}</span>
                    </div>
                    <div class="astar-viz-formula">${s.formula}</div>
                    <div class="d-flex gap-12 fs-9 color-secondary-text">
                        <span>g=${s.g}</span><span>h=${s.h}</span><span>f=${s.f}</span>
                        <span>Open: ${s.openSetSize}</span><span>Closed: ${s.closedSetSize}</span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-fill" style="width:${Math.min(100, (s.closedSetSize / d.closedSetSize) * 100)}%;background:${CONFIG.UI.GRADIENTS.expansion};"></div>
                    </div>
                </div>
            `;
        });

        if (d.success) {
            html += `
                <div class="mt-8 p-8 bg-success-light br-6 text-center fs-11 fw-700 color-success">
                    ✅ Goal reached! Optimal path found with ${d.pathLength} nodes
                </div>
            `;
        }
        html += `
            <div class="mt-8 p-8 bg-warn-light br-6 fs-10 color-secondary-text">
                Blue markers show exploration order on the map, orange shows the latest expanded node, green is the start, red is the goal, and purple is the final chosen path.
            </div>
        `;

        store.insider.astarSteps = html;
    } catch (e) {
        store.insider.astarSteps = `<div class="p-10 text-center color-error">Error: ${e.message}</div>`;
    }
}

// Attach button handlers
document.getElementById('run-comparison-btn')?.addEventListener('click', runInsiderComparison);
document.getElementById('run-astar-viz-btn')?.addEventListener('click', runAStarVisualization);

async function updateClock() {
    try {
        const d = await (await fetch(CONFIG.API.CLOCK)).json();
        const store = Alpine.store('sim');
        store.clock = d.time.display;
        store.rushHour.active = d.rushHour.isActive;
        store.rushHour.multiplier = d.rushHour.multiplier;
    } catch (e) { }
}

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});
