function postLogEntry(message, level, source) {
    fetch(CONFIG.API.LOGS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message,
            level,
            source,
            ts: Date.now()
        })
    }).catch(() => { });
}

function logEvent(message) {
    postLogEntry(
        message,
        CONFIG.UI.LOG_LEVELS.INFO,
        CONFIG.UI.LOG_SOURCES.UI
    );
}

function addDispatchInsight(message, tone = CONFIG.UI.LOG_LEVELS.NEUTRAL) {
    postLogEntry(message, tone, CONFIG.UI.LOG_SOURCES.DISPATCH);
}

function togglePanel(panelKey) {
    const store = Alpine.store('sim');
    store.panels[panelKey] = !store.panels[panelKey];
}

function clearMapLayers(layers) {
    layers.forEach(layer => {
        if (window.map && layer) {
            window.map.removeLayer(layer);
        }
    });
    return [];
}
