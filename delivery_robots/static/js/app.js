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

function togglePanel(btnId, panelSelector, onOpen, onClose) {
    const btn = document.getElementById(btnId);
    if (!btn) { console.error('Missing button:', btnId); return; }
    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        const panel = document.querySelector(panelSelector);
        if (!panel) { console.error('Missing panel:', panelSelector); return; }
        const hidden = panel.style.display === 'none' || panel.style.display === '';
        panel.style.display = hidden ? 'block' : 'none';
        console.log('Toggled', btnId, hidden ? 'open' : 'closed');
        if (hidden && onOpen) onOpen();
        if (!hidden && onClose) onClose();
    });
    console.log('OK:', btnId);
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
    });

    const slider = document.getElementById('speed-slider');
    const speedVal = document.getElementById('speed-value');
    slider?.addEventListener('input', (e) => {
        if (simulation) simulation.speed = +e.target.value;
        speedVal.textContent = e.target.value + 'x';
    });

    // All panel toggles
    togglePanel('toggle-robots', '.robot-panel');
    // Hidden for simplified exam mode
    // togglePanel('toggle-dispatch', '.dispatch-panel');
    togglePanel('toggle-computing', '.computing-panel', () => {
        const content = document.getElementById('computing-content');
        if (content && content.dataset.robotId && simulation?.robots) {
            const robot = simulation.robots.find(r => r.id == content.dataset.robotId);
            if (robot) content.innerHTML = robot.getComputingDetails();
        }
    });
    togglePanel('toggle-decision', '.decision-panel', fetchMetrics);
    togglePanel('toggle-weather', '.weather-panel', () => { weatherModeEnabled = true; }, () => { weatherModeEnabled = false; });
    // togglePanel('toggle-insider', '.insider-panel', null, clearInsiderLayers);

    // Close buttons
    document.getElementById('close-panel')?.addEventListener('click', () => {
        const panel = document.querySelector('.control-panel');
        if (panel) panel.style.display = 'none';
    });
    document.getElementById('close-robot-panel')?.addEventListener('click', () => {
        const panel = document.querySelector('.robot-panel');
        if (panel) panel.style.display = 'none';
    });
    // document.getElementById('close-dispatch-panel')?.addEventListener('click', () => document.querySelector('.dispatch-panel').style.display = 'none');
    document.getElementById('close-decision-panel')?.addEventListener('click', () => document.querySelector('.decision-panel').style.display = 'none');
    document.getElementById('close-weather-panel')?.addEventListener('click', () => { document.querySelector('.weather-panel').style.display = 'none'; weatherModeEnabled = false; });
    document.getElementById('close-computing-panel')?.addEventListener('click', () => document.querySelector('.computing-panel').style.display = 'none');
    // document.getElementById('close-insider-panel')?.addEventListener('click', () => {
    //     document.querySelector('.insider-panel').style.display = 'none';
    //     clearInsiderLayers();
    // });
}

function setupWeather() {
    // Mode tabs
    document.querySelectorAll('.weather-panel .mode-tab').forEach(tab => {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.weather-panel .mode-tab').forEach(t => { t.style.background = CONFIG.UI.COLORS.background; t.style.color = CONFIG.UI.COLORS.text; });
            this.style.background = CONFIG.ROBOT.COLORS.info; this.style.color = CONFIG.UI.COLORS.surface;
            weatherMode = this.dataset.mode;
            document.getElementById('rain-controls').style.display = weatherMode === CONFIG.UI.WEATHER_MODES.RAIN ? 'block' : 'none';
            document.getElementById('traffic-controls').style.display = weatherMode === CONFIG.UI.WEATHER_MODES.TRAFFIC ? 'block' : 'none';
            document.getElementById('obstacle-controls').style.display = 'none';
        });
    });

    // Sliders
    ['rain-radius', 'traffic-severity', 'obstacle-radius', 'obstacle-severity'].forEach(id => {
        const sl = document.getElementById(id);
        const vl = document.getElementById(id + '-value');
        if (sl && vl) sl.oninput = () => vl.textContent = sl.value;
    });

    // Algo buttons
    document.querySelectorAll('.algo-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            document.querySelectorAll('.algo-btn').forEach(b => { b.style.background = CONFIG.UI.COLORS.background; b.style.color = CONFIG.UI.COLORS.text; });
            this.style.background = CONFIG.ROBOT.COLORS.info; this.style.color = CONFIG.UI.COLORS.surface;
            if (window.simulation) window.simulation.schedulingAlgorithm = this.dataset.algo;
        });
    });

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
                if (!weatherModeEnabled) return;
                if (weatherMode === CONFIG.UI.WEATHER_MODES.RAIN) addRainZone(e.latlng.lat, e.latlng.lng, +document.getElementById('rain-radius').value);
                else if (weatherMode === CONFIG.UI.WEATHER_MODES.TRAFFIC) handleTrafficClick(e.latlng.lat, e.latlng.lng);
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
    const el = document.getElementById('rain-list');
    if (!el) return;
    el.innerHTML = d.rainZones.length ? d.rainZones.map((z, i) => `<div style="padding:4px 0;border-bottom:1px solid ${CONFIG.UI.COLORS.border};"><strong>${i + 1}. ${z.name}</strong><br>${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m</div>`).join('') : 'No rain zones';
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
    const el = document.getElementById('traffic-list');
    if (!el) return;
    el.innerHTML = d.routes.length ? d.routes.map((r, i) => `<div style="padding:4px 0;border-bottom:1px solid ${CONFIG.UI.COLORS.border};"><strong>${i + 1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('') : 'No traffic routes';
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
    const el = document.getElementById('obstacle-list');
    if (!el) return;
    el.innerHTML = d.obstacles.length ? d.obstacles.map((o, i) => `<div style="padding:4px 0;border-bottom:1px solid ${CONFIG.UI.COLORS.border};"><strong>${i + 1}. ${o.name}</strong><br>${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}</div>`).join('') : 'No obstacles';
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
        const el = id => document.getElementById(id);
        if (el('metric-total-calc')) el('metric-total-calc').textContent = d.pathfinding.totalCalculations;
        if (el('metric-avg-time')) el('metric-avg-time').textContent = d.pathfinding.avgCalculationTime + 'ms';
        if (el('metric-last-time')) el('metric-last-time').textContent = d.pathfinding.lastCalculationTime + 'ms';
        if (el('metric-nodes')) el('metric-nodes').textContent = d.pathfinding.avgNodesExplored.toFixed(0);
        if (el('metric-min-time')) el('metric-min-time').textContent = d.pathfinding.minCalculationTime + 'ms';
        if (el('metric-max-time')) el('metric-max-time').textContent = d.pathfinding.maxCalculationTime + 'ms';
        if (el('metric-path-length')) el('metric-path-length').textContent = d.pathfinding.avgPathLength;
        if (el('metric-graph-nodes')) el('metric-graph-nodes').textContent = d.graph.totalNodes;
        if (el('metric-graph-edges')) el('metric-graph-edges').textContent = d.graph.totalEdges;
        if (el('metric-rain-count')) el('metric-rain-count').textContent = d.activeFactors.rainZones;
        if (el('metric-traffic-count')) el('metric-traffic-count').textContent = d.activeFactors.trafficRoutes;
        if (el('metric-obstacle-count')) el('metric-obstacle-count').textContent = d.activeFactors.obstacles;
    } catch (e) { console.error('Metrics:', e); }
}

setInterval(() => {
    const p = document.querySelector('.decision-panel');
    if (p && p.style.display === 'block') fetchMetrics();
}, CONFIG.UI.METRICS_REFRESH_INTERVAL_MS);

// Auto-refresh computing panel every 2s
setInterval(() => {
    const compPanel = document.querySelector('.computing-panel');
    if (compPanel && compPanel.style.display === 'block' && simulation?.robots) {
        // Update with last clicked robot's data
        const content = document.getElementById('computing-content');
        if (content && content.dataset.robotId) {
            const robot = simulation.robots.find(r => r.id == content.dataset.robotId);
            if (robot) content.innerHTML = robot.getComputingDetails();
        }
    }
}, CONFIG.UI.COMPUTING_PANEL_REFRESH_INTERVAL_MS);

// ===== A* Visualization =====
async function showAStarProcess(robotId) {
    const el = document.getElementById(`astep-visual-${robotId}`);
    if (!el || !simulation?.robots) return;

    const robot = simulation.robots.find(r => r.id === robotId);
    if (!robot || !robot.routeTarget) {
        el.style.display = 'block';
        el.innerHTML = '<div style="padding:10px;text-align:center;color:#5f6368;">Robot has no active route. Wait for it to accept a delivery.</div>';
        return;
    }

    el.style.display = 'block';
    el.innerHTML = '<div style="padding:10px;text-align:center;">⏳ Computing A*...</div>';

    try {
        const d = await (await fetch(`${CONFIG.API.ASTEP}?fromLat=${robot.lat}&fromLon=${robot.lon}&toLat=${robot.routeTarget.lat}&toLon=${robot.routeTarget.lon}`)).json();

        if (!d.steps || d.steps.length === 0) {
            el.innerHTML = '<div style="padding:10px;text-align:center;color:#ea4335;">No steps recorded</div>';
            return;
        }

        // Build step-by-step visualization
        let html = `
            <div style="background:${CONFIG.UI.GRADIENTS.info};padding:12px;border-radius:10px;margin-bottom:12px;border:1px solid ${CONFIG.UI.COLORS.infoBorder};box-shadow:0 2px 8px rgba(26,115,232,${CONFIG.UI.OPACITY.low});">
                <div style="font-size:13px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                    🔬 A* Step-by-Step Calculation
                    <span style="font-size:10px;color:#5f6368;font-weight:400;">(${d.calcTime}ms, ${d.totalSteps} steps)</span>
                </div>
                
                <div style="background:white;border-radius:8px;padding:8px;margin:6px 0;">
                    <div style="font-size:10px;color:#5f6368;margin-bottom:4px;"><strong>Start:</strong> Node ${d.startNode} → <strong>Goal:</strong> Node ${d.endNode}</div>
                    <div style="display:flex;gap:8px;font-size:9px;color:#5f6368;">
                        <span>Open Set: <strong>${d.openSetSize}</strong></span>
                        <span>Closed Set: <strong>${d.closedSetSize}</strong></span>
                        <span>Path: <strong style="color:${CONFIG.UI.COLORS.primary};">${d.pathLength} nodes</strong></span>
                    </div>
                </div>
        `;

        // Show first 3 steps in detail, then summary
        d.steps.slice(0, 3).forEach(s => {
            const color = s.step === 1 ? CONFIG.ROBOT.COLORS.good : s.step === 2 ? CONFIG.ROBOT.COLORS.info : CONFIG.ROBOT.COLORS.highlight;
            html += `
                <div style="background:${CONFIG.UI.COLORS.surface};border-radius:8px;padding:8px;margin:6px 0;border-left:4px solid ${color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                        <span style="font-size:11px;font-weight:700;color:${color};">Step ${s.step}</span>
                        <span style="font-size:9px;color:${CONFIG.UI.COLORS.textLight};">Node ${s.currentNode}</span>
                    </div>
                    <div style="font-size:10px;font-family:monospace;background:${CONFIG.UI.COLORS.background};padding:4px 6px;border-radius:4px;margin:3px 0;">
                        ${s.formula}
                    </div>
                    <div style="display:flex;gap:12px;font-size:9px;color:${CONFIG.UI.COLORS.textLight};">
                        <span>g=${s.g}</span><span>h=${s.h}</span><span>f=${s.f}</span>
                        <span>Open:${s.openSetSize}</span><span>Closed:${s.closedSetSize}</span>
                    </div>
                </div>
            `;
        });

        if (d.steps.length > 3) {
            html += `
                <div style="text-align:center;padding:6px;font-size:10px;color:${CONFIG.UI.COLORS.textLight};background:${CONFIG.UI.COLORS.surface};border-radius:6px;margin:4px 0;">
                    ... ${d.steps.length - 3} more steps ...
                </div>
                <div style="background:${CONFIG.UI.COLORS.surface};border-radius:8px;padding:8px;margin:6px 0;border-left:4px solid ${CONFIG.ROBOT.COLORS.good};">
                    <div style="font-size:11px;font-weight:700;color:${CONFIG.ROBOT.COLORS.good};">✅ Goal Reached! (Step ${d.totalSteps})</div>
                    <div style="font-size:10px;color:${CONFIG.UI.COLORS.textLight};">Path reconstructed: ${d.pathLength} nodes</div>
                </div>
            `;
        }

        // Show penalties applied
        const hasRain = rainCircles.length > 0;
        const hasTraffic = trafficPolylines.length > 0;
        const hasObstacles = obstacleCircles.length > 0;

        html += `
                <div style="background:${CONFIG.UI.COLORS.surface};border-radius:8px;padding:8px;margin:6px 0;">
                    <div style="font-size:10px;font-weight:700;margin-bottom:4px;">⚙️ Penalties Applied:</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;font-size:9px;">
                        ${hasRain ? `<span style="background:${CONFIG.UI.COLORS.rainBg};padding:3px 6px;border-radius:4px;">🌧️ Rain: ${CONFIG.ROBOT.RAIN_REROUTE_THRESHOLD}×</span>` : ''}
                        ${hasTraffic ? `<span style="background:${CONFIG.UI.COLORS.trafficBg};padding:3px 6px;border-radius:4px;">🚗 Traffic: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 2.5}×</span>` : ''}
                        ${hasObstacles ? `<span style="background:${CONFIG.UI.COLORS.obstacleBg};padding:3px 6px;border-radius:4px;">🚧 Obstacles: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 3}×</span>` : ''}
                    </div>
                </div>
            </div>
        `;

        el.innerHTML = html;
        renderAStarOverlay(d);
    } catch (e) {
        el.innerHTML = `<div style="padding:10px;text-align:center;color:#ea4335;">Error: ${e.message}</div>`;
    }
}

// Make it global
window.showAStarProcess = showAStarProcess;

// ===== Insider Panel =====
async function runInsiderComparison() {
    const el = document.getElementById('comparison-table');
    if (!el) return;
    el.innerHTML = '<div style="padding:10px;text-align:center;">⏳ Running 4 algorithms...</div>';

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

        // Find the best time
        const bestTime = Math.min(...rows.map(r => r.time_ms));

        let html = `
            <table style="width:100%;border-collapse:collapse;font-size:10px;">
                <thead>
                    <tr style="background:${CONFIG.UI.GRADIENTS.purple};color:${CONFIG.UI.COLORS.surface};">
                        <th style="padding:6px;text-align:left;">Algorithm</th>
                        <th style="padding:6px;text-align:center;">Nodes</th>
                        <th style="padding:6px;text-align:center;">Path</th>
                        <th style="padding:6px;text-align:center;">Time</th>
                        <th style="padding:6px;text-align:center;">Optimal?</th>
                        <th style="padding:6px;text-align:center;">Efficiency</th>
                    </tr>
                </thead>
                <tbody>
        `;

        rows.forEach(r => {
            const bg = r.name.startsWith("A*") ? '#ede7f6' : CONFIG.UI.COLORS.background;
            const bold = r.name.startsWith("A*") ? 'font-weight:700;' : '';
            const optimal = r.optimal ? `<span style="color:${CONFIG.UI.COLORS.success};">✅ Yes</span>` : `<span style="color:${CONFIG.UI.COLORS.error};">❌ No</span>`;
            const eff = best > 0 ? ((r.path_length / best) * 100).toFixed(0) + '%' : 'N/A';
            const effColor = eff === '100%' ? CONFIG.UI.COLORS.success : CONFIG.UI.COLORS.error;
            const timeBadge = r.time_ms === bestTime ? '⚡ ' : '';
            const timeColor = r.time_ms === bestTime ? CONFIG.UI.COLORS.success : CONFIG.UI.COLORS.textLight;

            html += `
                <tr style="background:${bg};border-bottom:1px solid ${CONFIG.UI.COLORS.border};">
                    <td style="padding:6px;${bold}">${r.icon} ${r.name}</td>
                    <td style="padding:6px;text-align:center;${bold}">${r.nodes_explored}</td>
                    <td style="padding:6px;text-align:center;${bold}">${r.path_length} nodes</td>
                    <td style="padding:6px;text-align:center;color:${timeColor};font-weight:600;">${timeBadge}${r.time_ms}ms</td>
                    <td style="padding:6px;text-align:center;">${optimal}</td>
                    <td style="padding:6px;text-align:center;color:${effColor};font-weight:600;">${eff}</td>
                </tr>
            `;
        });

        html += `</tbody></table>`;

        // Key insight
        const astarNodes = algos["A*"].nodes_explored;
        const dijkstraNodes = algos["Dijkstra"].nodes_explored;
        const speedup = dijkstraNodes > 0 ? ((1 - astarNodes / dijkstraNodes) * 100).toFixed(0) : 0;

        html += `
            <div style="margin-top:8px;padding:8px;background:${CONFIG.UI.GRADIENTS.success};border-radius:6px;font-size:10px;">
                <strong>💡 Key Insight:</strong> A* explored <strong>${astarNodes}</strong> nodes vs Dijkstra's <strong>${dijkstraNodes}</strong> — that's <strong style="color:${CONFIG.UI.COLORS.success};">${speedup}% fewer nodes</strong> while finding the same optimal path!
            </div>
        `;

        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div style="padding:10px;text-align:center;color:#ea4335;">Error: ${e.message}</div>`;
    }
}

async function runAStarVisualization() {
    const el = document.getElementById('astep-visualizer');
    if (!el) return;
    el.innerHTML = '<div style="padding:10px;text-align:center;">⏳ Running A* step-by-step...</div>';

    try {
        const from = CONFIG.DATA.LOCATIONS[0];
        const to = CONFIG.DATA.LOCATIONS[1];
        const d = await (await fetch(`${CONFIG.API.ASTEP}?fromLat=${from.lat}&fromLon=${from.lon}&toLat=${to.lat}&toLon=${to.lon}`)).json();

        if (!d.steps || d.steps.length === 0) {
            el.innerHTML = '<div style="padding:10px;text-align:center;color:#ea4335;">No steps to visualize</div>';
            return;
        }

        renderAStarOverlay(d);

        let html = `
            <div style="font-size:11px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                🔬 A* Expansion (${d.totalSteps} steps, ${d.calcTime}ms)
            </div>
            
            <div style="display:flex;gap:6px;margin-bottom:8px;font-size:9px;color:#5f6368;">
                <span>Start: Node ${d.startNode}</span>
                <span>→ Goal: Node ${d.endNode}</span>
                <span>→ Path: ${d.pathLength} nodes</span>
            </div>
        `;

        // Show steps with node visualization
        d.steps.forEach((s, i) => {
            const color = i === 0 ? CONFIG.UI.COLORS.success : i === d.steps.length - 1 ? CONFIG.UI.COLORS.error : CONFIG.ROBOT.COLORS.info;
            const bg = i === 0 ? CONFIG.UI.COLORS.successLight : i === d.steps.length - 1 ? CONFIG.UI.COLORS.errorLight : CONFIG.UI.COLORS.background;

            html += `
                <div style="background:${bg};border-radius:6px;padding:6px 8px;margin:4px 0;border-left:3px solid ${color};font-size:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-weight:700;color:${color};">Step ${s.step}</span>
                        <span style="font-family:monospace;font-size:9px;">Node ${s.currentNode}</span>
                    </div>
                    <div style="font-family:monospace;font-size:9px;background:${CONFIG.UI.COLORS.surface};padding:3px 6px;border-radius:3px;margin:3px 0;">
                        ${s.formula}
                    </div>
                    <div style="display:flex;gap:12px;font-size:9px;color:${CONFIG.UI.COLORS.textLight};">
                        <span>g=${s.g}</span><span>h=${s.h}</span><span>f=${s.f}</span>
                        <span>Open: ${s.openSetSize}</span><span>Closed: ${s.closedSetSize}</span>
                    </div>
                    <!-- Node bar visualization -->
                    <div style="margin-top:4px;height:6px;background:${CONFIG.UI.COLORS.border};border-radius:3px;overflow:hidden;">
                        <div style="width:${Math.min(100, (s.closedSetSize / d.closedSetSize) * 100)}%;height:100%;background:${CONFIG.UI.GRADIENTS.expansion};border-radius:3px;transition:width 0.3s;"></div>
                    </div>
                </div>
            `;
        });

        if (d.success) {
            html += `
                <div style="margin-top:8px;padding:8px;background:${CONFIG.UI.COLORS.successLight};border-radius:6px;text-align:center;font-size:11px;font-weight:700;color:${CONFIG.UI.COLORS.success};">
                    ✅ Goal reached! Optimal path found with ${d.pathLength} nodes
                </div>
            `;
        }
        html += `
            <div style="margin-top:8px;padding:8px;background:${CONFIG.UI.COLORS.warnLight};border-radius:6px;font-size:10px;color:${CONFIG.UI.COLORS.textLight};">
                Blue markers show exploration order on the map, orange shows the latest expanded node, green is the start, red is the goal, and purple is the final chosen path.
            </div>
        `;

        el.innerHTML = html;
    } catch (e) {
        el.innerHTML = `<div style="padding:10px;text-align:center;color:${CONFIG.UI.COLORS.error};">Error: ${e.message}</div>`;
    }
}

// Attach button handlers
document.getElementById('run-comparison-btn')?.addEventListener('click', runInsiderComparison);
document.getElementById('run-astar-viz-btn')?.addEventListener('click', runAStarVisualization);

// ===== CLOCK =====
async function updateClock() {
    try {
        const d = await (await fetch(CONFIG.API.CLOCK)).json();
        const cl = document.getElementById('clock-time');
        if (cl) cl.textContent = d.time.display;
        const rh = document.getElementById('rush-hour-display');
        const rm = document.getElementById('rush-multiplier');
        if (d.rushHour.isActive) {
            if (rh) { rh.style.display = 'inline-block'; if (rm) rm.textContent = d.rushHour.multiplier.toFixed(1); }
        } else { if (rh) rh.style.display = 'none'; }
    } catch (e) { }
}

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});
