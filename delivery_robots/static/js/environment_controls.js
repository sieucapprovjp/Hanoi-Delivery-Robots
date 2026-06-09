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

function getEnvironmentLayerState() {
    return {
        hasRain: rainCircles.length > 0 || (window.mapManager?.rainZones?.length || 0) > 0,
        hasTraffic: trafficPolylines.length > 0 || (window.mapManager?.trafficJams?.length || 0) > 0,
        hasObstacles: obstacleCircles.length > 0
    };
}
