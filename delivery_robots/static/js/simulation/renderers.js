function renderRobotStatusCards(robots) {
    return robots.map(robot => `
        <div class="robot-card" style="border-left-color:${robot.color}">
            <div class="robot-name" style="color:${robot.color}">${robot.name}</div>
            <div class="robot-detail">${robot.getStatusText()}</div>
            <div class="robot-detail">📦 ${robot.totalDeliveries} | ${robot.totalDistance.toFixed(0)}m | ⏱ ${robot.getEtaText()}</div>
            <div class="robot-detail">🎯 ${robot.routeMode || CONFIG.UI.STATE_LABELS.STANDBY} | 🔋 ${robot.battery.toFixed(0)}%</div>
            <div class="robot-detail">🧠 <strong>${robot.routeAlgorithm.toUpperCase()}</strong></div>
            <div class="battery-bar">
                <div class="battery-fill" style="width:${robot.battery}%;background:${robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? CONFIG.ROBOT.COLORS.good : robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? CONFIG.ROBOT.COLORS.warn : CONFIG.ROBOT.COLORS.error}"></div>
            </div>
        </div>
    `).join('');
}

function renderDeliveryQueue(deliveries) {
    if (!deliveries.length) {
        return `<div style="padding:15px;text-align:center;color:#5f6368;font-size:12px;">${CONFIG.UI.TEXT.EMPTY.ORDERS_DISPATCHED}</div>`;
    }

    return deliveries.map(delivery => `
        <div class="delivery-item" style="padding:10px;background:#f8f9fa;border-radius:8px;margin-bottom:8px;border-left:4px solid #1a73e8;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-weight:700;font-size:12px;">Order #${delivery.id}</span>
                <span style="font-size:10px;color:#5f6368;">${delivery.pickup.icon} → ${delivery.destination.icon}</span>
            </div>
            <div style="font-size:11px;color:#3c4043;">From: ${delivery.pickup.name}</div>
            <div style="font-size:11px;color:#3c4043;">To: ${delivery.destination.name}</div>
        </div>
    `).join('');
}

function calculateAlgorithmEfficiency(stats) {
    const totalPathCostKm = stats.totalPathCost / 1000;
    const avgTimeMs = stats.routeCount > 0 ? stats.totalRouteTimeMs / stats.routeCount : 0;
    const avgNodes = stats.routeCount > 0 ? stats.totalNodesExplored / stats.routeCount : 0;
    const weights = CONFIG.SIMULATION.EFFICIENCY_WEIGHTS;
    const denominator = totalPathCostKm + (weights.TIME * avgTimeMs) + (weights.NODES * avgNodes) + (weights.REROUTE * stats.rerouteCount) + 1;
    return stats.deliveriesCompleted / denominator;
}

function renderAlgorithmComparison(algorithmStats, fleetAlgorithm) {
    const table = CONFIG.UI.TEXT.TABLE;
    const labelMap = {
        astar: 'A*',
        dijkstra: 'Dijkstra',
        gbfs: 'GBFS'
    };

    const rows = CONFIG.SIMULATION.ALGORITHMS.map(algo => {
        const stats = algorithmStats[algo];
        const avgTimeMs = stats.routeCount > 0 ? stats.totalRouteTimeMs / stats.routeCount : 0;
        const avgNodes = stats.routeCount > 0 ? stats.totalNodesExplored / stats.routeCount : 0;
        const avgPathCost = stats.routeCount > 0 ? stats.totalPathCost / stats.routeCount : 0;
        const efficiency = calculateAlgorithmEfficiency(stats);
        const isActive = algo === fleetAlgorithm;

        return `
            <tr class="${isActive ? 'best-row' : ''}">
                <td><strong>${labelMap[algo]}</strong></td>
                <td style="text-align:center;">${stats.deliveriesCompleted}</td>
                <td style="text-align:center;">${avgTimeMs.toFixed(1)}ms</td>
                <td style="text-align:center;">${avgNodes.toFixed(0)}</td>
                <td style="text-align:center;">${avgPathCost.toFixed(0)}m</td>
                <td style="text-align:center;">${stats.rerouteCount}</td>
                <td style="text-align:center;"><strong>${efficiency.toFixed(3)}</strong></td>
            </tr>
        `;
    }).join('');

    return `
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>${table.ALGORITHM}</th>
                    <th style="text-align:center;">${table.DONE}</th>
                    <th style="text-align:center;">${table.TIME}</th>
                    <th style="text-align:center;">${table.NODES}</th>
                    <th style="text-align:center;">${table.COST}</th>
                    <th style="text-align:center;">${table.REROUTES}</th>
                    <th style="text-align:center;">${table.EFFICIENCY}</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}
