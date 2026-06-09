let rainCircles = [];
let trafficPolylines = [];
let obstacleCircles = [];
let trafficPointA = null;
let trafficPointMarkerA = null;

async function refreshMapWeather() {
    if (window.mapManager && typeof window.mapManager.loadWeather === 'function') {
        await window.mapManager.loadWeather();
    }
}

async function refreshMapTraffic() {
    if (window.mapManager && typeof window.mapManager.refreshTraffic === 'function') {
        await window.mapManager.refreshTraffic();
    }
}

function setupWeather() {
    document.getElementById('randomize-rain-btn')?.addEventListener('click', randomizeRain);
    document.getElementById('clear-rain-btn')?.addEventListener('click', clearRain);
    document.getElementById('reset-traffic-points-btn')?.addEventListener('click', resetTrafficPoints);
    document.getElementById('randomize-traffic-btn')?.addEventListener('click', randomizeTraffic);
    document.getElementById('clear-traffic-btn')?.addEventListener('click', clearTraffic);
    document.getElementById('randomize-obstacle-btn')?.addEventListener('click', randomizeObstacles);
    document.getElementById('clear-obstacle-btn')?.addEventListener('click', clearObstacles);

    const setupMapClick = () => {
        const map = window.map;
        if (map && typeof map.on === 'function') {
            map.on('click', function (e) {
                const store = Alpine.store('sim');
                if (!store.panels.weather) return;

                if (store.weather.mode === CONFIG.UI.WEATHER_MODES.RAIN) {
                    addRainZone(e.latlng.lat, e.latlng.lng, +store.weather.rainRadius);
                } else if (store.weather.mode === CONFIG.UI.WEATHER_MODES.TRAFFIC) {
                    handleTrafficClick(e.latlng.lat, e.latlng.lng);
                } else if (store.weather.mode === CONFIG.UI.WEATHER_MODES.OBSTACLE) {
                    addObstacle(
                        e.latlng.lat,
                        e.latlng.lng,
                        +store.weather.obstacleRadius,
                        +store.weather.obstacleSeverity
                    );
                }
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
    let d;
    try {
        d = await postJson(CONFIG.API.TRAFFIC_ADD, {
            startLat: start.lat,
            startLon: start.lon,
            endLat: end.lat,
            endLon: end.lon,
            severity
        }, 'Traffic add failed');
    } catch (error) {
        logEvent('❌ Traffic: ' + error.message);
        return;
    }

    const route = d.route;
    if (route?.path?.length) {
        trafficPolylines.push(
            L.polyline(route.path.map(p => [p.lat, p.lon]), {
                color: CONFIG.ROBOT.COLORS.error,
                weight: CONFIG.UI.WEIGHTS.thick,
                opacity: CONFIG.UI.OPACITY.high
            })
                .addTo(window.map)
                .bindPopup(`<strong>${route.name}</strong><br>Severity: ${route.severity.toFixed(2)}`)
        );
    }
    updateTrafficList().catch(() => { });
    refreshMapTraffic().catch(() => { });
    logEvent('🚗 ' + route.name);
}

async function addRainZone(lat, lon, radius) {
    try {
        const d = await postJson(CONFIG.API.RAIN_ADD, { lat, lon, radius }, 'Rain add failed');
        updateRainList();
        refreshMapWeather().catch(() => { });
        logEvent('🌧️ ' + d.rainZone.name);
    } catch (error) {
        logEvent('❌ Rain: ' + error.message);
    }
}

function displayRainZone(z) {
    if (!window.map) return;
    const c = L.circle([z.center.lat, z.center.lon], {
        color: CONFIG.ROBOT.COLORS.info,
        fillColor: CONFIG.ROBOT.COLORS.info,
        fillOpacity: 0.2,
        radius: z.radius
    }).addTo(window.map);
    c.bindPopup(`<strong>${z.name}</strong><br>Radius: ${Math.round(z.radius)}m`);
    rainCircles.push(c);
}

async function updateRainList() {
    const d = await getJson(CONFIG.API.RAIN_LIST, null, 'Rain list request failed');
    const html = d.rainZones.length
        ? d.rainZones.map((z, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${z.name}</strong><br>${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m</div>`).join('')
        : 'No rain zones';
    Alpine.store('sim').weather.rainZonesHtml = html;
    return d;
}

async function randomizeRain() {
    await postJson(CONFIG.API.RAIN_RANDOMIZE, {
        count: CONFIG.SIMULATION.RANDOM_RAIN_COUNT,
        minRadius: CONFIG.SIMULATION.RANDOM_RAIN_MIN_RADIUS,
        maxRadius: CONFIG.SIMULATION.RANDOM_RAIN_MAX_RADIUS
    });
    rainCircles = clearMapLayers(rainCircles);
    updateRainList();
    refreshMapWeather().catch(() => { });
    logEvent('🎲 Rain');
}

async function clearRain() {
    await postJson(CONFIG.API.RAIN_CLEAR);
    rainCircles = clearMapLayers(rainCircles);
    updateRainList();
    refreshMapWeather().catch(() => { });
    logEvent('🗑️ Rain');
}

async function randomizeTraffic() {
    const d = await postJson(CONFIG.API.TRAFFIC_RANDOMIZE, {
        count: CONFIG.SIMULATION.RANDOM_TRAFFIC_COUNT
    }, 'Traffic randomize failed');
    trafficPolylines = clearMapLayers(trafficPolylines);
    d.routes.forEach(r => {
        trafficPolylines.push(
            L.polyline(r.path.map(p => [p.lat, p.lon]), {
                color: CONFIG.ROBOT.COLORS.error,
                weight: CONFIG.UI.WEIGHTS.thick,
                opacity: CONFIG.UI.OPACITY.high
            }).addTo(window.map)
        );
    });
    updateTrafficList();
    refreshMapTraffic().catch(() => { });
    logEvent('🎲 Traffic');
}

async function clearTraffic() {
    await postJson(CONFIG.API.TRAFFIC_CLEAR);
    trafficPolylines = clearMapLayers(trafficPolylines);
    updateTrafficList();
    refreshMapTraffic().catch(() => { });
    logEvent('🗑️ Traffic');
}

async function updateTrafficList() {
    const d = await getJson(CONFIG.API.TRAFFIC_LIST, null, 'Traffic list request failed');
    const html = d.routes.length
        ? d.routes.map((r, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('')
        : 'No traffic routes';
    Alpine.store('sim').weather.trafficRoutesHtml = html;
    return d;
}

async function addObstacle(lat, lon, radius, severity) {
    try {
        const d = await postJson(CONFIG.API.OBSTACLE_ADD, {
            lat,
            lon,
            radius,
            severity,
            type: CONFIG.SIMULATION.DEFAULT_OBSTACLE_TYPE
        }, 'Obstacle add failed');
        displayObstacle(d.obstacle);
        updateObstacleList();
        logEvent('🚧 ' + d.obstacle.name);
    } catch (error) {
        logEvent('❌ Obstacle: ' + error.message);
    }
}

function displayObstacle(o) {
    if (!window.map) return;
    const colors = CONFIG.DATA.OBSTACLE_COLORS;
    const c = L.circle([o.center.lat, o.center.lon], {
        color: colors[o.type] || CONFIG.ROBOT.COLORS.error,
        fillColor: colors[o.type] || CONFIG.ROBOT.COLORS.error,
        fillOpacity: CONFIG.UI.OPACITY.medium,
        radius: o.radius
    }).addTo(window.map);
    c.bindPopup(`<strong>${o.name}</strong><br>Severity: ${o.severity.toFixed(1)}`);
    obstacleCircles.push(c);
}

async function updateObstacleList() {
    const d = await getJson(CONFIG.API.OBSTACLE_LIST, null, 'Obstacle list request failed');
    const html = d.obstacles.length
        ? d.obstacles.map((o, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${o.name}</strong><br>${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}</div>`).join('')
        : 'No obstacles';
    Alpine.store('sim').weather.obstaclesHtml = html;
    return d;
}

async function randomizeObstacles() {
    const d = await postJson(CONFIG.API.OBSTACLE_RANDOMIZE, {
        count: CONFIG.SIMULATION.RANDOM_OBSTACLE_COUNT
    }, 'Obstacle randomize failed');
    obstacleCircles = clearMapLayers(obstacleCircles);
    d.obstacles.forEach(o => displayObstacle(o));
    updateObstacleList();
    logEvent('🎲 Obstacles');
}

async function clearObstacles() {
    await postJson(CONFIG.API.OBSTACLE_CLEAR);
    obstacleCircles = clearMapLayers(obstacleCircles);
    updateObstacleList();
    logEvent('🗑️ Obstacles');
}

function getEnvironmentLayerState() {
    return {
        hasRain: rainCircles.length > 0 || (window.mapManager?.rainZones?.length || 0) > 0,
        hasTraffic: trafficPolylines.length > 0 || (window.mapManager?.trafficJams?.length || 0) > 0,
        hasObstacles: obstacleCircles.length > 0
    };
}
