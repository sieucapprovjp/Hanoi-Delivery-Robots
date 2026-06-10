function xaiEscapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function xaiFormatNumber(value, digits = 1) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return 'n/a';
    return Number(value).toFixed(digits);
}

function xaiFormatMeters(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return 'n/a';
    return `${Number(value).toFixed(0)}m`;
}

function xaiFormatStatus(status) {
    return String(status || 'candidate').replace(/_/g, ' ');
}

function renderXaiConstraintBadges(constraints = {}) {
    const labels = [
        ['idle', 'Idle'],
        ['batteryOk', 'Battery'],
        ['capacityOk', 'Capacity'],
        ['pickupDistanceOk', 'Pickup'],
        ['batteryReserveOk', 'Reserve'],
    ].filter(([key]) => Object.prototype.hasOwnProperty.call(constraints, key));

    return `
        <div class="xai-constraints">
            ${labels.map(([key, label]) => `
                <span class="xai-constraint ${constraints[key] ? 'ok' : 'fail'}">
                    ${xaiEscapeHtml(label)}
                </span>
            `).join('')}
        </div>
    `;
}

function renderXaiScoreRows(candidate) {
    const scores = candidate.scores || {};
    const hasFinalScore = scores.totalScore !== undefined || candidate.totalScore !== undefined;

    if (!hasFinalScore) {
        return `
            <div class="xai-score-grid compact">
                <div><span>Pre-score</span><strong>${xaiFormatNumber(scores.approximateScore ?? candidate.approximateScore)}</strong></div>
                <div><span>Pickup</span><strong>${xaiFormatMeters(candidate.pickupDistance)}</strong></div>
            </div>
        `;
    }

    return `
        <div class="xai-score-grid">
            <div><span>Route</span><strong>${xaiFormatMeters(scores.routeCost ?? candidate.routeCost)}</strong></div>
            <div><span>Battery risk</span><strong>${xaiFormatNumber(scores.batteryRisk ?? candidate.batteryRisk, 2)}</strong></div>
            <div><span>Priority</span><strong>${xaiFormatNumber(scores.priorityScore, 1)}</strong></div>
            <div><span>Total</span><strong>${xaiFormatNumber(scores.totalScore ?? candidate.totalScore, 1)}</strong></div>
        </div>
    `;
}

function renderXaiRouteSummary(candidate) {
    const route = candidate.route;
    if (!route) return '';

    const parts = [
        route.algorithm ? `${route.algorithm.toUpperCase()}` : null,
        route.distance !== undefined ? xaiFormatMeters(route.distance) : null,
        route.etaMinutes !== undefined ? `${xaiFormatNumber(route.etaMinutes, 1)}m ETA` : null,
        route.nodesExplored !== undefined ? `${route.nodesExplored} nodes` : null,
        route.timeMs !== undefined ? `${xaiFormatNumber(route.timeMs, 1)}ms` : null,
    ].filter(Boolean);

    if (!parts.length) return '';
    return `<div class="xai-route-summary">${parts.map(xaiEscapeHtml).join(' · ')}</div>`;
}

function renderXaiReasons(candidate) {
    const reasons = candidate.rejectReasons?.length ? candidate.rejectReasons : candidate.reasons || [];
    if (!reasons.length) return '';

    return `
        <div class="xai-reason-list">
            ${reasons.map(reason => `
                <span title="${xaiEscapeHtml(reason.message || reason.code)}">${xaiEscapeHtml(reason.code)}</span>
            `).join('')}
        </div>
    `;
}

function renderXaiCandidate(candidate) {
    const status = candidate.status || 'candidate';
    const isAccepted = candidate.accepted !== false;

    return `
        <div class="xai-candidate xai-${xaiEscapeHtml(status)}">
            <div class="xai-candidate-head">
                <strong>${xaiEscapeHtml(candidate.robotName || candidate.robotId)}</strong>
                <span class="${isAccepted ? 'xai-accepted' : 'xai-denied'}">${xaiEscapeHtml(xaiFormatStatus(status))}</span>
            </div>
            <div class="xai-candidate-meta">
                <span>Battery ${xaiEscapeHtml(candidate.battery)}%</span>
                <span>Load ${xaiEscapeHtml(candidate.currentLoad ?? 0)}/${xaiEscapeHtml(candidate.capacity ?? '-')}</span>
                <span>Pickup ${xaiFormatMeters(candidate.pickupDistance)}</span>
            </div>
            ${renderXaiConstraintBadges(candidate.constraints)}
            ${renderXaiScoreRows(candidate)}
            ${renderXaiRouteSummary(candidate)}
            ${candidate.formula ? `<div class="xai-formula">${xaiEscapeHtml(candidate.formula)}</div>` : ''}
            ${renderXaiReasons(candidate)}
        </div>
    `;
}

function renderXaiTimelineSteps(explanation) {
    return (explanation.timeline || []).map(step => `
        <div class="xai-step xai-${xaiEscapeHtml(step.status)}">
            <div class="xai-step-stage">${xaiEscapeHtml(step.stage)}</div>
            <div class="xai-step-message">${xaiEscapeHtml(step.message)}</div>
        </div>
    `).join('');
}

function renderDispatchTimeline(explanations) {
    if (!explanations || explanations.length === 0) {
        return '<div class="xai-empty">No dispatch decision yet.</div>';
    }

    return explanations.slice(-3).reverse().map(explanation => {
        const selected = explanation.selectedRobotName || explanation.selectedRobotId || 'None';
        const candidates = (explanation.candidates || []).map(renderXaiCandidate).join('');
        const timeline = renderXaiTimelineSteps(explanation);

        return `
            <div class="xai-decision">
                <div class="xai-title">
                    <strong>Order #${xaiEscapeHtml(explanation.orderId ?? explanation.deliveryId)}</strong>
                    <span>priority ${xaiEscapeHtml(explanation.priorityScore)}</span>
                </div>
                <div class="xai-route">${xaiEscapeHtml(explanation.pickupName)} -> ${xaiEscapeHtml(explanation.destinationName)}</div>
                <div class="xai-selected-summary">
                    <span>Selected</span>
                    <strong>${xaiEscapeHtml(selected)}</strong>
                </div>
                <div class="xai-objective">${xaiEscapeHtml(explanation.objective)}</div>
                ${explanation.finalExplanation ? `<div class="xai-final">${xaiEscapeHtml(explanation.finalExplanation)}</div>` : ''}
                <div class="xai-grid">${candidates}</div>
                <div class="xai-timeline">${timeline}</div>
            </div>
        `;
    }).join('');
}
