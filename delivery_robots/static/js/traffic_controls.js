let trafficPolylines = [];
let trafficPointA = null;
let trafficPointMarkerA = null;

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

async function updateTrafficList() {
    const d = await getJson(CONFIG.API.TRAFFIC_LIST, null, 'Traffic list request failed');
    const html = d.routes.length
        ? d.routes.map((r, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('')
        : 'No traffic routes';
    Alpine.store('sim').weather.trafficRoutesHtml = html;
    return d;
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
