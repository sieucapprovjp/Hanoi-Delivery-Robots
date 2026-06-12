let obstacleCircles = [];

async function addObstacle(lat, lon, radius, severity) {
    try {
        const d = await postJson(CONFIG.API.OBSTACLE_ADD, {
            lat,
            lon,
            radius,
            severity,
            type: CONFIG.SIMULATION.DEFAULT_OBSTACLE_TYPE
        }, CONFIG.UI.TEXT.ENVIRONMENT.ERROR_OBSTACLE_ADD);
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
    c.bindPopup(`<strong>${o.name}</strong><br>${CONFIG.UI.TEXT.ENVIRONMENT.SEVERITY} ${o.severity.toFixed(1)}`);
    obstacleCircles.push(c);
}

async function updateObstacleList() {
    const d = await getJson(CONFIG.API.OBSTACLE_LIST, null, CONFIG.UI.TEXT.ENVIRONMENT.ERROR_OBSTACLE_LIST);
    const html = d.obstacles.length
        ? d.obstacles.map((o, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${o.name}</strong><br>${Math.round(o.radius)}m | ${CONFIG.UI.TEXT.ENVIRONMENT.SEVERITY_SHORT} ${o.severity.toFixed(1)}</div>`).join('')
        : CONFIG.UI.TEXT.ENVIRONMENT.NO_OBSTACLES;
    Alpine.store('sim').weather.obstaclesHtml = html;
    return d;
}

async function randomizeObstacles() {
    const d = await postJson(CONFIG.API.OBSTACLE_RANDOMIZE, {
        count: CONFIG.SIMULATION.RANDOM_OBSTACLE_COUNT
    }, CONFIG.UI.TEXT.ENVIRONMENT.ERROR_OBSTACLE_RANDOMIZE);
    obstacleCircles = clearMapLayers(obstacleCircles);
    d.obstacles.forEach(o => displayObstacle(o));
    updateObstacleList();
    logEvent(CONFIG.UI.TEXT.ENVIRONMENT.LOG_RANDOM_OBSTACLES);
}

async function clearObstacles() {
    await postJson(CONFIG.API.OBSTACLE_CLEAR);
    obstacleCircles = clearMapLayers(obstacleCircles);
    updateObstacleList();
    logEvent(CONFIG.UI.TEXT.ENVIRONMENT.LOG_CLEAR_OBSTACLES);
}
