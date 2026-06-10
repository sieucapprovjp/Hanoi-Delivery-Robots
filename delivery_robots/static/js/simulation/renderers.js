function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function formatCandidateReason(candidate) {
    const reasons = candidate.reasons || [];
    if (reasons.length === 0) return '';
    return reasons.map(reason => escapeHtml(reason.code)).join(', ');
}

function renderDispatchTimeline(explanations) {
    if (!explanations || explanations.length === 0) {
        return '<div class="xai-empty">No dispatch decision yet.</div>';
    }

    return explanations.slice(-3).reverse().map(explanation => {
        const candidates = (explanation.candidates || []).map(candidate => {
            const score = candidate.totalScore !== undefined
                ? `<span>score <strong>${candidate.totalScore.toFixed ? candidate.totalScore.toFixed(1) : candidate.totalScore}</strong></span>`
                : `<span>pre-score <strong>${candidate.approximateScore}</strong></span>`;
            const routeCost = candidate.routeCost !== undefined
                ? `<span>${candidate.routeCost}m</span>`
                : `<span>${candidate.pickupDistance}m pickup</span>`;
            const reason = formatCandidateReason(candidate);

            return `
                <div class="xai-candidate xai-${escapeHtml(candidate.status)}">
                    <div class="xai-candidate-head">
                        <strong>${escapeHtml(candidate.robotName || candidate.robotId)}</strong>
                        <span>${escapeHtml(candidate.status)}</span>
                    </div>
                    <div class="xai-candidate-meta">
                        <span>Battery ${escapeHtml(candidate.battery)}%</span>
                        ${routeCost}
                        ${score}
                    </div>
                    ${candidate.formula ? `<div class="xai-formula">${escapeHtml(candidate.formula)}</div>` : ''}
                    ${reason ? `<div class="xai-reason">${reason}</div>` : ''}
                </div>
            `;
        }).join('');

        const timeline = (explanation.timeline || []).map(step => `
            <div class="xai-step xai-${escapeHtml(step.status)}">
                <div class="xai-step-stage">${escapeHtml(step.stage)}</div>
                <div class="xai-step-message">${escapeHtml(step.message)}</div>
            </div>
        `).join('');

        return `
            <div class="xai-decision">
                <div class="xai-title">
                    Order #${escapeHtml(explanation.deliveryId)}
                    <span>priority ${escapeHtml(explanation.priorityScore)}</span>
                </div>
                <div class="xai-route">${escapeHtml(explanation.pickupName)} -> ${escapeHtml(explanation.destinationName)}</div>
                <div class="xai-objective">${escapeHtml(explanation.objective)}</div>
                <div class="xai-grid">${candidates}</div>
                <div class="xai-timeline">${timeline}</div>
            </div>
        `;
    }).join('');
}

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
        return '<div style="padding:15px;text-align:center;color:#5f6368;font-size:12px;">All orders dispatched. Waiting for new orders...</div>';
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
                    <th>Algorithm</th>
                    <th style="text-align:center;">Done</th>
                    <th style="text-align:center;">Time</th>
                    <th style="text-align:center;">Nodes</th>
                    <th style="text-align:center;">Cost</th>
                    <th style="text-align:center;">Reroutes</th>
                    <th style="text-align:center;">Eff.</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}
