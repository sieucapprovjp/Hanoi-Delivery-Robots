function getRobotBatteryClass(robot) {
    return robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ?
        'battery-good' :
        robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ?
            'battery-warn' :
            'battery-error';
}

function getRobotDecisionState(robot, options = {}) {
    let decisionState = CONFIG.UI.STATE_LABELS.IDLE;

    if (robot.status === CONFIG.ROBOT.STATUSES.MOVING) {
        if (robot.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING) {
            decisionState = CONFIG.UI.STATE_LABELS.CHARGING;
        } else if (robot.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) {
            decisionState = options.useRouteLabels ? CONFIG.UI.STATE_LABELS.ROUTING_PICKUP : CONFIG.UI.STATE_LABELS.PICKUP;
        } else if (robot.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) {
            decisionState = options.useRouteLabels ? CONFIG.UI.STATE_LABELS.ROUTING_DROPOFF : CONFIG.UI.STATE_LABELS.DROPOFF;
        } else {
            decisionState = CONFIG.UI.STATE_LABELS.MOVING;
        }
    }

    if (robot.isRouting) decisionState = CONFIG.UI.STATE_LABELS.REROUTING;
    if (robot.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD && (options.lowBatteryWhileCharging || robot.status !== CONFIG.ROBOT.STATUSES.CHARGING)) {
        decisionState = CONFIG.UI.STATE_LABELS.LOW_BATTERY;
    }

    return decisionState;
}

function getRobotStatusBadgeClass(robot) {
    if (robot.isRouting) return 'status-warn';
    if (robot.status === CONFIG.ROBOT.STATUSES.MOVING) return 'status-success';
    return 'status-neutral';
}

function renderRobotPopup(robot) {
    const batteryClass = getRobotBatteryClass(robot);
    const decisionState = getRobotDecisionState(robot, { useRouteLabels: true });
    const text = CONFIG.UI.TEXT.ROBOT;

    return `
        <div class="robot-popup">
            <div class="popup-title" style="--robot-color: ${robot.color}">🤖 ${robot.name}</div>

            <div class="popup-status-badge ${getRobotStatusBadgeClass(robot)}">
                ${decisionState}
            </div>

            <div class="popup-grid-3">
                <div class="grid-item"><div class="item-label">${text.SPEED}</div><div class="item-value">${(robot.speedMultiplier * 100).toFixed(0)}%</div></div>
                <div class="grid-item"><div class="item-label">${text.BATTERY}</div><div class="item-value ${batteryClass}">${robot.battery.toFixed(1)}%</div></div>
                <div class="grid-item"><div class="item-label">${text.DRAIN}</div><div class="item-value">${robot.batteryDrain.toFixed(3)}/s</div></div>
            </div>

            <div class="popup-grid-2">
                <div class="grid-item"><div class="item-label">${text.COMPLETED}</div><div class="item-value color-success">${robot.totalDeliveries}</div></div>
                <div class="grid-item"><div class="item-label">${text.DISTANCE}</div><div class="item-value color-primary">${robot.totalDistance.toFixed(0)}m</div></div>
            </div>

            ${robot.routeTarget ? `<div class="popup-info-box status-success">🎯 ${robot.routeTarget.lat.toFixed(4)}, ${robot.routeTarget.lon.toFixed(4)}<br>${robot.currentPath.length - robot.pathIndex} ${text.WAYPOINTS_LEFT}<br>⏱ ETA ${robot.getEtaText()}</div>` : ''}

            ${robot.currentDelivery ? `<div class="popup-info-box status-neutral"><div class="item-label">📦 Order #${robot.currentDelivery.id}</div><div class="item-value">${robot.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP ? text.GOING_PICKUP : text.GOING_DELIVER}</div></div>` : `<div class="popup-info-box status-neutral">${CONFIG.UI.TEXT.EMPTY.NO_DELIVERY}</div>`}
        </div>
    `;
}

function renderRobotCalculationHistory(robot) {
    if (!robot._calcHistory || robot._calcHistory.length === 0) {
        return `<tr><td colspan="3" class="p-8 text-center">${CONFIG.UI.STATE_LABELS.WAITING}</td></tr>`;
    }

    return robot._calcHistory.slice(-8).reverse().map(c => {
        const ago = ((Date.now() - c.timestamp) / 1000).toFixed(1);
        const colorClass = c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.GOOD ?
            'color-success' :
            c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.WARN ?
                'color-warning' :
                'color-error';

        return `<tr><td>${ago}s</td><td class="text-center">${c.nodes}</td><td class="text-right fw-600 ${colorClass}">${c.time.toFixed(1)}ms</td></tr>`;
    }).join('');
}

function renderRobotRouteInfo(robot) {
    if (!robot.lastRouteBreakdown) {
        return `<div class="insight-box text-center">${CONFIG.UI.TEXT.EMPTY.ROUTE_PENDING}</div>`;
    }
    const text = CONFIG.UI.TEXT.ROBOT;

    return `
        <div class="insight-box">
            <div class="insight-title">${text.ROUTE_BREAKDOWN_TITLE}</div>
            <div class="breakdown-container">
                <div class="breakdown-row"><span>${text.BASE_DISTANCE}</span><strong>${robot.lastRouteBreakdown.baseDistance.toFixed(0)}m</strong></div>
                <div class="breakdown-row"><span>${text.TRAFFIC_PENALTY}</span><span class="color-error">+${robot.lastRouteBreakdown.trafficPenalty.toFixed(0)}m</span></div>
                <div class="breakdown-row"><span>${text.RAIN_PENALTY}</span><span class="color-primary">+${robot.lastRouteBreakdown.rainPenalty.toFixed(0)}m</span></div>
                <div class="breakdown-row"><span>${text.OBSTACLE_PENALTY}</span><span class="color-warning">+${robot.lastRouteBreakdown.obstaclePenalty.toFixed(0)}m</span></div>
                <div class="breakdown-total"><span>${text.TOTAL_COST}</span><strong>${robot.lastRouteBreakdown.totalCost.toFixed(0)}m</strong></div>
                <div class="breakdown-row"><span>${text.SIM_ETA}</span><strong class="color-success">${robot.getEtaText()}</strong></div>
            </div>
        </div>
    `;
}

function getRobotCalculationStats(robot) {
    const history = robot._calcHistory || [];

    if (!history.length) {
        return { avgTime: '0', fastest: '0', slowest: '0' };
    }

    return {
        avgTime: (history.reduce((a, b) => a + b.time, 0) / history.length).toFixed(1),
        fastest: Math.min(...history.map(c => c.time)).toFixed(1),
        slowest: Math.max(...history.map(c => c.time)).toFixed(1),
    };
}

function renderRobotComputingDetails(robot) {
    const batteryClass = getRobotBatteryClass(robot);
    const decisionState = getRobotDecisionState(robot, { lowBatteryWhileCharging: true });
    const { avgTime, fastest, slowest } = getRobotCalculationStats(robot);
    const text = CONFIG.UI.TEXT.ROBOT;

    return `
        <div class="computing-details">
            <div class="details-header">
                🤖 ${robot.name} <span>| ${text.COMPUTING_ENGINE}</span>
            </div>

            <div class="status-badge ${getRobotStatusBadgeClass(robot)}">
                ${text.STATE} ${decisionState}
            </div>

            <div class="stats-grid-3">
                <div class="stat-card"><div class="stat-label">${text.SPEED}</div><div class="stat-value">${(robot.speedMultiplier * 100).toFixed(0)}%</div></div>
                <div class="stat-card"><div class="stat-label">${text.BATTERY}</div><div class="stat-value ${batteryClass}">${robot.battery.toFixed(1)}%</div></div>
                <div class="stat-card"><div class="stat-label">Drain/s</div><div class="stat-value">${robot.batteryDrain.toFixed(3)}</div></div>
            </div>

            ${renderRobotRouteInfo(robot)}

            <div class="history-container">
                <div class="history-title">${text.CALC_HISTORY}</div>
                <table class="history-table">
                    <thead><tr><th>⏱ When</th><th>🔢 Nodes</th><th>⚡ Time</th></tr></thead>
                    <tbody>${renderRobotCalculationHistory(robot)}</tbody>
                </table>
            </div>

            <div class="performance-container">
                <div class="perf-title">${text.LIFETIME_PERFORMANCE}</div>
                <div class="perf-grid">
                    <div class="perf-card"><div class="stat-label">${text.DELIVERIES}</div><div class="stat-value text-success">${robot.totalDeliveries}</div></div>
                    <div class="perf-card"><div class="stat-label">${text.DISTANCE}</div><div class="stat-value text-info">${robot.totalDistance.toFixed(0)}m</div></div>
                    <div class="perf-card"><div class="stat-label">${text.CALCULATIONS}</div><div class="stat-value text-highlight">${robot._calcHistory?.length || 0}</div></div>
                </div>
                <div class="perf-summary">
                    <div>⚡ Fast: <strong class="text-success">${fastest}ms</strong></div>
                    <div>🐌 Slow: <strong class="text-error">${slowest}ms</strong></div>
                    <div>📊 Avg: <strong>${avgTime}ms</strong></div>
                </div>
            </div>

            <div class="action-container">
                <button @click="$store.sim.panels.insider = true; showAStarProcess(${robot.id})" class="btn-primary-small">
                    ${text.SHOW_ASTAR_PROCESS}
                </button>
            </div>
        </div>
    `;
}
