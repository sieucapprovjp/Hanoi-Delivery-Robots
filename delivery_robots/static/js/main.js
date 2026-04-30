let displayEngine;
let mapManager;
let pathfindingManager;

let rainCircles = [];
let trafficPolylines = [];
let obstacleCircles = [];
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


async function init() {
    try {
        displayEngine = new DisplayEngine();
        window.displayEngine = displayEngine;
        await displayEngine.initialize();
        setupControls();
        setupWeather();
        await fetchMetrics(true);
        await updateClock(true);
        setInterval(updateClock, 1000);
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
                else if (store.weather.mode === 'obstacle') addObstacle(e.latlng.lat, e.latlng.lng, +store.weather.obstacleRadius, +store.weather.obstacleSeverity);
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
    const colors = CONFIG.OBSTACLE_COLORS;
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
        store.clock = d.time.display;
        store.rushHour.active = d.rushHour.isActive;
        store.rushHour.multiplier = d.rushHour.multiplier;
    } catch (e) { }
}

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});
