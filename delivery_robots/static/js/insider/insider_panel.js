let insiderLayers = [];

function clearInsiderLayers() {
    insiderLayers = clearMapLayers(insiderLayers);
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
        const pathLine = L.polyline(data.path.map(p => [p.lat, p.lon]), {
            color: CONFIG.UI.COLORS.secondary,
            weight: CONFIG.UI.WEIGHTS.thick,
            opacity: CONFIG.UI.OPACITY.overlay
        }).addTo(window.map);
        insiderLayers.push(pathLine);

        const start = data.path[0];
        const end = data.path[data.path.length - 1];
        insiderLayers.push(
            L.circleMarker([start.lat, start.lon], {
                radius: CONFIG.UI.RADII.markerLarge,
                color: CONFIG.UI.COLORS.success,
                fillColor: CONFIG.UI.COLORS.success,
                fillOpacity: CONFIG.UI.OPACITY.full
            }).addTo(window.map)
        );
        insiderLayers.push(
            L.circleMarker([end.lat, end.lon], {
                radius: CONFIG.UI.RADII.markerLarge,
                color: CONFIG.ROBOT.COLORS.error,
                fillColor: CONFIG.ROBOT.COLORS.error,
                fillOpacity: 1
            }).addTo(window.map)
        );
    }
}

async function showAStarProcess(robotId) {
    const store = Alpine.store('sim');
    if (!simulation?.robots) return;

    const robot = simulation.robots.find(r => r.id === robotId);
    if (!robot || !robot.routeTarget) {
        store.insider.astarSteps = `<div class="p-10 text-center color-secondary-text">${CONFIG.UI.TEXT.EMPTY.NO_ACTIVE_ROUTE}</div>`;
        return;
    }

    store.insider.astarSteps = `<div class="p-10 text-center">${CONFIG.UI.TEXT.LOADING.ASTAR_COMPUTING}</div>`;

    try {
        const d = await getJson(CONFIG.API.ASTEP, {
            fromLat: robot.lat,
            fromLon: robot.lon,
            toLat: robot.routeTarget.lat,
            toLon: robot.routeTarget.lon
        }, CONFIG.UI.TEXT.API_ERRORS.ASTAR_PROCESS);

        if (!d.steps || d.steps.length === 0) {
            store.insider.astarSteps = `<div class="p-10 text-center color-error">${CONFIG.UI.TEXT.EMPTY.NO_ASTAR_STEPS}</div>`;
            return;
        }
        const insiderText = CONFIG.UI.TEXT.INSIDER;

        let html = `
            <div class="astar-viz-container">
                <div class="astar-viz-header">
                    ${insiderText.ASTAR_STEP_TITLE}
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
                    <div class="fs-11 fw-700" style="color:${CONFIG.ROBOT.COLORS.good};">${insiderText.GOAL_REACHED} (Step ${d.totalSteps})</div>
                    <div class="fs-10" style="color:${CONFIG.UI.COLORS.textLight};">${insiderText.PATH_RECONSTRUCTED} ${d.pathLength} nodes</div>
                </div>
            `;
        }

        const environment = getEnvironmentLayerState();
        html += `
                <div class="bg-surface br-8 p-8 mt-6">
                    <div class="fs-10 fw-700 mb-4">${insiderText.PENALTIES_APPLIED}</div>
                    <div class="d-flex gap-6 flex-wrap fs-9">
                        ${environment.hasRain ? `<span class="penalty-badge bg-rain-penalty">🌧️ Rain: ${CONFIG.ROBOT.RAIN_REROUTE_THRESHOLD}×</span>` : ''}
                        ${environment.hasTraffic ? `<span class="penalty-badge bg-traffic-penalty">🚗 Traffic: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 2.5}×</span>` : ''}
                        ${environment.hasObstacles ? `<span class="penalty-badge bg-obstacle-penalty">🚧 Obstacles: ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 3}×</span>` : ''}
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

async function runInsiderComparison() {
    const store = Alpine.store('sim');
    store.insider.comparison = `<div class="p-10 text-center">${CONFIG.UI.TEXT.LOADING.INSIDER_COMPARISON_RUNNING}</div>`;

    try {
        const from = CONFIG.DATA.LOCATIONS[0];
        const to = CONFIG.DATA.LOCATIONS[1];
        const d = await getJson(CONFIG.API.INSIDER, {
            fromLat: from.lat,
            fromLon: from.lon,
            toLat: to.lat,
            toLon: to.lon
        }, CONFIG.UI.TEXT.API_ERRORS.INSIDER_COMPARISON);

        const algos = d.algorithms;
        const best = d.best_path_length;
        const rows = [
            { name: "A* (Informed)", ...algos["A*"], icon: "⭐" },
            { name: "Dijkstra (Optimal)", ...algos["Dijkstra"], icon: "🔵" },
            { name: "GBFS (Heuristic)", ...algos["GBFS"] || algos["Greedy Best-First"], icon: "🟡" },
            { name: "BFS (Blind)", ...algos["BFS"], icon: "🟢" },
        ];
        const bestTime = Math.min(...rows.map(r => r.time_ms));
        const table = CONFIG.UI.TEXT.TABLE;

        let html = `
            <table class="comparison-table">
                <thead>
                    <tr>
                        <th>${table.ALGORITHM}</th>
                        <th class="text-center">${table.NODES}</th>
                        <th class="text-center">${table.PATH}</th>
                        <th class="text-center">${table.TIME}</th>
                        <th class="text-center">${table.OPTIMAL}</th>
                        <th class="text-center">${table.EFFICIENCY}</th>
                    </tr>
                </thead>
                <tbody>
        `;

        rows.forEach(r => {
            const isAStar = r.name.startsWith("A*");
            const optimal = (r.expectedOptimal || r.optimal)
                ? `<span style="color:${CONFIG.UI.COLORS.success};">✅ Yes</span>`
                : `<span style="color:${CONFIG.UI.COLORS.error};">❌ No</span>`;
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
        const gbfsNodes = (algos["GBFS"] || algos["Greedy Best-First"]).nodes_explored;
        const speedup = dijkstraNodes > 0 ? ((1 - astarNodes / dijkstraNodes) * 100).toFixed(0) : 0;

        html += `
            <div class="insight-box">
                <strong>${CONFIG.UI.TEXT.INSIDER.KEY_INSIGHT}</strong> A* explored <strong>${astarNodes}</strong> nodes vs Dijkstra's <strong>${dijkstraNodes}</strong> — that's <strong class="color-success">${speedup}% fewer nodes</strong> while finding the same optimal path. GBFS used <strong>${gbfsNodes}</strong> nodes with a heuristic-first strategy.
            </div>
        `;

        store.insider.comparison = html;
    } catch (e) {
        store.insider.comparison = `<div class="p-10 text-center color-error">Error: ${e.message}</div>`;
    }
}

async function runAStarVisualization() {
    const store = Alpine.store('sim');
    store.insider.astarSteps = `<div class="p-10 text-center">${CONFIG.UI.TEXT.LOADING.ASTAR_STEP_RUNNING}</div>`;

    try {
        const from = CONFIG.DATA.LOCATIONS[0];
        const to = CONFIG.DATA.LOCATIONS[1];
        const d = await getJson(CONFIG.API.ASTEP, {
            fromLat: from.lat,
            fromLon: from.lon,
            toLat: to.lat,
            toLon: to.lon
        }, CONFIG.UI.TEXT.API_ERRORS.ASTAR_VISUALIZATION);

        if (!d.steps || d.steps.length === 0) {
            store.insider.astarSteps = `<div class="p-10 text-center color-error">${CONFIG.UI.TEXT.EMPTY.NO_ASTAR_VISUALIZATION_STEPS}</div>`;
            return;
        }

        renderAStarOverlay(d);

        let html = `
            <div class="astar-viz-header">
                ${CONFIG.UI.TEXT.INSIDER.ASTAR_EXPANSION_TITLE} (${d.totalSteps} steps, ${d.calcTime}ms)
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
                ${CONFIG.UI.TEXT.INSIDER.MAP_LEGEND}
            </div>
        `;

        store.insider.astarSteps = html;
    } catch (e) {
        store.insider.astarSteps = `<div class="p-10 text-center color-error">Error: ${e.message}</div>`;
    }
}

function setupInsiderControls() {
    document.getElementById('run-comparison-btn')?.addEventListener('click', runInsiderComparison);
    document.getElementById('run-astar-viz-btn')?.addEventListener('click', runAStarVisualization);
}

window.showAStarProcess = showAStarProcess;
