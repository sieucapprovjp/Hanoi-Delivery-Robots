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
    const text = CONFIG.UI.TEXT.XAI.CONSTRAINTS;
    const labels = [
        ['idle', text.idle],
        ['batteryOk', text.batteryOk],
        ['capacityOk', text.capacityOk],
        ['pickupDistanceOk', text.pickupDistanceOk],
        ['batteryReserveOk', text.batteryReserveOk],
        ['routeEtaOk', text.routeEtaOk],
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
    const labels = CONFIG.UI.TEXT.XAI.SCORE_LABELS;

    if (!hasFinalScore) {
        return `
            <div class="xai-score-grid compact">
                <div><span>${labels.preScore}</span><strong>${xaiFormatNumber(scores.approximateScore ?? candidate.approximateScore)}</strong></div>
                <div><span>${labels.pickup}</span><strong>${xaiFormatMeters(candidate.pickupDistance)}</strong></div>
            </div>
        `;
    }

    return `
        <div class="xai-score-grid">
            <div><span>${labels.route}</span><strong>${xaiFormatMeters(scores.routeCost ?? candidate.routeCost)}</strong></div>
            <div><span>${labels.batteryRisk}</span><strong>${xaiFormatNumber(scores.batteryRisk ?? candidate.batteryRisk, 2)}</strong></div>
            <div><span>${labels.priority}</span><strong>${xaiFormatNumber(scores.priorityScore, 1)}</strong></div>
            <div><span>${labels.total}</span><strong>${xaiFormatNumber(scores.totalScore ?? candidate.totalScore, 1)}</strong></div>
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
    const labels = CONFIG.UI.TEXT.XAI.META_LABELS;

    return `
        <div class="xai-candidate xai-${xaiEscapeHtml(status)}">
            <div class="xai-candidate-head">
                <strong>${xaiEscapeHtml(candidate.robotName || candidate.robotId)}</strong>
                <span class="${isAccepted ? 'xai-accepted' : 'xai-denied'}">${xaiEscapeHtml(xaiFormatStatus(status))}</span>
            </div>
            <div class="xai-candidate-meta">
                <span>${labels.battery} ${xaiEscapeHtml(candidate.battery)}%</span>
                <span>${labels.load} ${xaiEscapeHtml(candidate.currentLoad ?? 0)}/${xaiEscapeHtml(candidate.capacity ?? '-')}</span>
                <span>${labels.pickup} ${xaiFormatMeters(candidate.pickupDistance)}</span>
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

function renderXaiVrpSummary(explanation) {
    const vrp = explanation.vrp;
    if (!vrp) return '';

    const labels = CONFIG.UI.TEXT.XAI.VRP_LABELS;
    const stats = vrp.stats || {};
    const improvementPct = xaiFormatNumber((vrp.improvementRatio || 0) * 100, 1);
    const sequence = (vrp.sequence || []).join(' -> ');

    return `
        <div class="xai-route-summary">
            ${xaiEscapeHtml(labels.title)} · ${xaiEscapeHtml(vrp.orderCount)} ${xaiEscapeHtml(labels.orders)}
        </div>
        <div class="xai-score-grid">
            <div><span>${labels.initialCost}</span><strong>${xaiFormatMeters(vrp.initialCost)}</strong></div>
            <div><span>${labels.finalCost}</span><strong>${xaiFormatMeters(vrp.finalCost)}</strong></div>
            <div><span>${labels.improvement}</span><strong>${improvementPct}%</strong></div>
            <div><span>${labels.iterations}</span><strong>${xaiEscapeHtml(stats.iterations ?? 0)}</strong></div>
            <div><span>${labels.acceptedMoves}</span><strong>${xaiEscapeHtml(stats.acceptedMoves ?? 0)}</strong></div>
        </div>
        ${sequence ? `<div class="xai-formula">${labels.sequence}: ${xaiEscapeHtml(sequence)}</div>` : ''}
    `;
}

function xaiHasVrpStep(explanation) {
    return (explanation.timeline || []).some(step => (
        step.stage === 'vrp_sequence' || step.stage === 'vrp_batch'
    ));
}

function selectVisibleDispatchExplanations(explanations) {
    const recent = explanations.slice(-3);
    const latestVrp = [...explanations].reverse().find(xaiHasVrpStep);
    if (!latestVrp || recent.includes(latestVrp)) {
        return recent.reverse();
    }

    return [latestVrp, ...recent.slice(-2).reverse()];
}

function renderDispatchTimeline(explanations) {
    if (!explanations || explanations.length === 0) {
        return `<div class="xai-empty">${CONFIG.UI.TEXT.EMPTY.NO_DISPATCH_DECISION}</div>`;
    }
    const labels = CONFIG.UI.TEXT.XAI.META_LABELS;

    return selectVisibleDispatchExplanations(explanations).map(explanation => {
        const selected = explanation.selectedRobotName || explanation.selectedRobotId || 'None';
        const candidates = (explanation.candidates || []).map(renderXaiCandidate).join('');
        const timeline = renderXaiTimelineSteps(explanation);
        const vrpSummary = renderXaiVrpSummary(explanation);

        return `
            <div class="xai-decision">
                <div class="xai-title">
                    <strong>Order #${xaiEscapeHtml(explanation.orderId ?? explanation.deliveryId)}</strong>
                    <span>${labels.priority} ${xaiEscapeHtml(explanation.priorityScore)}</span>
                </div>
                <div class="xai-route">${xaiEscapeHtml(explanation.pickupName)} -> ${xaiEscapeHtml(explanation.destinationName)}</div>
                <div class="xai-selected-summary">
                    <span>${labels.selected}</span>
                    <strong>${xaiEscapeHtml(selected)}</strong>
                </div>
                <div class="xai-objective">${xaiEscapeHtml(explanation.objective)}</div>
                ${explanation.finalExplanation ? `<div class="xai-final">${xaiEscapeHtml(explanation.finalExplanation)}</div>` : ''}
                ${vrpSummary}
                <div class="xai-grid">${candidates}</div>
                <div class="xai-timeline">${timeline}</div>
            </div>
        `;
    }).join('');
}
