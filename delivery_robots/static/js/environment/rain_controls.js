let rainCircles = [];

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
