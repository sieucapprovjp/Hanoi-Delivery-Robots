// Globals
let weatherMode = 'rain';
let rainCircles = [];
let trafficPolylines = [];
let obstacleCircles = [];
let weatherModeEnabled = false;

function logEvent(message) {
    const el = document.getElementById('event-log');
    if (!el) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="timestamp">[${new Date().toLocaleTimeString()}]</span>${message}`;
    el.insertBefore(entry, el.firstChild);
    while (el.children.length > 100) el.removeChild(el.lastChild);
}

function addDispatchInsight(message, tone = 'neutral') {
    const el = document.getElementById('dispatch-insights');
    if (!el) return;
    const entry = document.createElement('div');
    entry.className = `dispatch-entry ${tone}`;
    entry.innerHTML = `<span class="dispatch-time">${new Date().toLocaleTimeString()}</span><span class="dispatch-text">${message}</span>`;
    el.insertBefore(entry, el.firstChild);
    while (el.children.length > 20) el.removeChild(el.lastChild);
}

function togglePanel(btnId, panelSelector, onOpen, onClose) {
    const btn = document.getElementById(btnId);
    if (!btn) { console.error('Missing button:', btnId); return; }
    btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        const panel = document.querySelector(panelSelector);
        if (!panel) { console.error('Missing panel:', panelSelector); return; }
        const hidden = panel.style.display === 'none' || panel.style.display === '';
        panel.style.display = hidden ? 'block' : 'none';
        console.log('Toggled', btnId, hidden ? 'open' : 'closed');
        if (hidden && onOpen) onOpen();
        if (!hidden && onClose) onClose();
    });
    console.log('OK:', btnId);
}

async function init() {
    try {
        simulation = new Simulation();
        window.simulation = simulation;
        await simulation.initialize();
        setupControls();
        setupWeather();
        updateClock();
        setInterval(updateClock, 1000);
        logEvent('✅ Ready');
    } catch (error) {
        console.error('Init error:', error);
        logEvent('❌ ' + error.message);
    }
}

function setupControls() {
    document.getElementById('start-btn')?.addEventListener('click', () => simulation?.start());
    document.getElementById('pause-btn')?.addEventListener('click', () => simulation?.pause());
    document.getElementById('reset-btn')?.addEventListener('click', () => simulation?.reset());
    
    const slider = document.getElementById('speed-slider');
    const speedVal = document.getElementById('speed-value');
    slider?.addEventListener('input', (e) => {
        if (simulation) simulation.speed = +e.target.value;
        speedVal.textContent = e.target.value + 'x';
    });

    // All panel toggles
    togglePanel('toggle-robots', '.robot-panel');
    togglePanel('toggle-deliveries', '.delivery-panel');
    togglePanel('toggle-log', '.log-panel');
    togglePanel('toggle-dispatch', '.dispatch-panel');
    togglePanel('toggle-analytics', '.analytics-panel');
    togglePanel('toggle-computing', '.computing-panel', () => {
        const content = document.getElementById('computing-content');
        if (content && content.dataset.robotId && simulation?.robots) {
            const robot = simulation.robots.find(r => r.id == content.dataset.robotId);
            if (robot) content.innerHTML = robot.getComputingDetails();
        }
    });
    togglePanel('toggle-decision', '.decision-panel', fetchMetrics);
    togglePanel('toggle-weather', '.weather-panel', () => { weatherModeEnabled = true; }, () => { weatherModeEnabled = false; });

    // Close buttons
    document.getElementById('close-dispatch-panel')?.addEventListener('click', () => document.querySelector('.dispatch-panel').style.display = 'none');
    document.getElementById('close-analytics-panel')?.addEventListener('click', () => document.querySelector('.analytics-panel').style.display = 'none');
    document.getElementById('close-decision-panel')?.addEventListener('click', () => document.querySelector('.decision-panel').style.display = 'none');
    document.getElementById('close-weather-panel')?.addEventListener('click', () => { document.querySelector('.weather-panel').style.display = 'none'; weatherModeEnabled = false; });
    document.getElementById('close-computing-panel')?.addEventListener('click', () => document.querySelector('.computing-panel').style.display = 'none');
}

function setupWeather() {
    // Mode tabs
    document.querySelectorAll('.weather-panel .mode-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.weather-panel .mode-tab').forEach(t => { t.style.background = '#e8eaed'; t.style.color = '#3c4043'; });
            this.style.background = '#1a73e8'; this.style.color = 'white';
            weatherMode = this.dataset.mode;
            document.getElementById('rain-controls').style.display = weatherMode === 'rain' ? 'block' : 'none';
            document.getElementById('traffic-controls').style.display = weatherMode === 'traffic' ? 'block' : 'none';
            document.getElementById('obstacle-controls').style.display = weatherMode === 'obstacle' ? 'block' : 'none';
        });
    });

    // Sliders
    ['rain-radius', 'traffic-severity', 'obstacle-radius', 'obstacle-severity'].forEach(id => {
        const sl = document.getElementById(id);
        const vl = document.getElementById(id + '-value');
        if (sl && vl) sl.oninput = () => vl.textContent = sl.value;
    });

    // Algo buttons
    document.querySelectorAll('.algo-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.algo-btn').forEach(b => { b.style.background = '#e8eaed'; b.style.color = '#3c4043'; });
            this.style.background = '#1a73e8'; this.style.color = 'white';
            if (window.simulation) window.simulation.schedulingAlgorithm = this.dataset.algo;
        });
    });

    // Actions
    document.getElementById('randomize-rain-btn')?.addEventListener('click', randomizeRain);
    document.getElementById('clear-rain-btn')?.addEventListener('click', clearRain);
    document.getElementById('randomize-traffic-btn')?.addEventListener('click', randomizeTraffic);
    document.getElementById('clear-traffic-btn')?.addEventListener('click', clearTraffic);
    document.getElementById('randomize-obstacle-btn')?.addEventListener('click', randomizeObstacles);
    document.getElementById('clear-obstacle-btn')?.addEventListener('click', clearObstacles);

    // Map click
    const setupMapClick = () => {
        const map = window.map;
        if (map && typeof map.on === 'function') {
            map.on('click', function(e) {
                if (!weatherModeEnabled) return;
                if (weatherMode === 'rain') addRainZone(e.latlng.lat, e.latlng.lng, +document.getElementById('rain-radius').value);
                else if (weatherMode === 'obstacle') addObstacle(e.latlng.lat, e.latlng.lng, +document.getElementById('obstacle-radius').value, +document.getElementById('obstacle-severity').value);
            });
            console.log('Map click listener ready');
        } else {
            console.warn('Map not ready, retrying in 500ms...');
            setTimeout(setupMapClick, 500);
        }
    };
    setTimeout(setupMapClick, 500);

    updateRainList().catch(()=>{});
    updateTrafficList().catch(()=>{});
    updateObstacleList().catch(()=>{});
}

// ===== WEATHER ACTIONS =====
async function addRainZone(lat, lon, radius) {
    const res = await fetch('/api/rain/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lat, lon, radius}) });
    const d = await res.json();
    if (res.ok) { displayRainZone(d.rainZone); updateRainList(); logEvent('🌧️ ' + d.rainZone.name); }
}

function displayRainZone(z) {
    if (!window.map) return;
    const c = L.circle([z.center.lat, z.center.lon], { color: '#4285f4', fillColor: '#4285f4', fillOpacity: 0.2, radius: z.radius }).addTo(window.map);
    c.bindPopup(`<strong>${z.name}</strong><br>Radius: ${Math.round(z.radius)}m`);
    rainCircles.push(c);
}

async function updateRainList() {
    const d = await (await fetch('/api/rain/list')).json();
    const el = document.getElementById('rain-list');
    if (!el) return;
    el.innerHTML = d.rainZones.length ? d.rainZones.map((z, i) => `<div style="padding:4px 0;border-bottom:1px solid #e0e0e0;"><strong>${i+1}. ${z.name}</strong><br>${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m</div>`).join('') : 'No rain zones';
}

async function randomizeRain() {
    const d = await (await fetch('/api/rain/randomize', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({count:3,minRadius:100,maxRadius:200}) })).json();
    rainCircles.forEach(c => window.map.removeLayer(c)); rainCircles = [];
    d.rainZones.forEach(z => displayRainZone(z)); updateRainList(); logEvent('🎲 Rain');
}

async function clearRain() {
    await fetch('/api/rain/clear', {method:'POST'});
    rainCircles.forEach(c => window.map.removeLayer(c)); rainCircles = []; updateRainList(); logEvent('🗑️ Rain');
}

async function randomizeTraffic() {
    const d = await (await fetch('/api/traffic/randomize', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({count:3}) })).json();
    trafficPolylines.forEach(p => window.map.removeLayer(p)); trafficPolylines = [];
    d.routes.forEach(r => {
        trafficPolylines.push(L.polyline(r.path.map(p=>[p.lat,p.lon]), {color:'#ea4335',weight:5,opacity:0.7}).addTo(window.map));
    });
    updateTrafficList(); logEvent('🎲 Traffic');
}

async function clearTraffic() {
    await fetch('/api/traffic/clear', {method:'POST'});
    trafficPolylines.forEach(p => window.map.removeLayer(p)); trafficPolylines = []; updateTrafficList(); logEvent('🗑️ Traffic');
}

async function updateTrafficList() {
    const d = await (await fetch('/api/traffic/list')).json();
    const el = document.getElementById('traffic-list');
    if (!el) return;
    el.innerHTML = d.routes.length ? d.routes.map((r,i)=>`<div style="padding:4px 0;border-bottom:1px solid #e0e0e0;"><strong>${i+1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('') : 'No traffic routes';
}

async function addObstacle(lat, lon, radius, severity) {
    const res = await fetch('/api/obstacle/add', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({lat,lon,radius,severity,type:'roadblock'}) });
    const d = await res.json();
    if (res.ok) { displayObstacle(d.obstacle); updateObstacleList(); logEvent('🚧 ' + d.obstacle.name); }
}

function displayObstacle(o) {
    if (!window.map) return;
    const colors = {roadblock:'#ff6b6b',construction:'#ffa94d',accident:'#ffd43b'};
    const c = L.circle([o.center.lat, o.center.lon], { color: colors[o.type]||'#ff6b6b', fillColor: colors[o.type]||'#ff6b6b', fillOpacity: 0.3, radius: o.radius }).addTo(window.map);
    c.bindPopup(`<strong>${o.name}</strong><br>Severity: ${o.severity.toFixed(1)}`);
    obstacleCircles.push(c);
}

async function updateObstacleList() {
    const d = await (await fetch('/api/obstacle/list')).json();
    const el = document.getElementById('obstacle-list');
    if (!el) return;
    el.innerHTML = d.obstacles.length ? d.obstacles.map((o,i)=>`<div style="padding:4px 0;border-bottom:1px solid #e0e0e0;"><strong>${i+1}. ${o.name}</strong><br>${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}</div>`).join('') : 'No obstacles';
}

async function randomizeObstacles() {
    const d = await (await fetch('/api/obstacle/randomize', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({count:4}) })).json();
    obstacleCircles.forEach(c => window.map.removeLayer(c)); obstacleCircles = [];
    d.obstacles.forEach(o => displayObstacle(o)); updateObstacleList(); logEvent('🎲 Obstacles');
}

async function clearObstacles() {
    await fetch('/api/obstacle/clear', {method:'POST'});
    obstacleCircles.forEach(c => window.map.removeLayer(c)); obstacleCircles = []; updateObstacleList(); logEvent('🗑️ Obstacles');
}

// ===== METRICS =====
async function fetchMetrics() {
    try {
        const d = await (await fetch('/api/metrics')).json();
        const el = id => document.getElementById(id);
        if(el('metric-total-calc')) el('metric-total-calc').textContent = d.pathfinding.totalCalculations;
        if(el('metric-avg-time')) el('metric-avg-time').textContent = d.pathfinding.avgCalculationTime + 'ms';
        if(el('metric-last-time')) el('metric-last-time').textContent = d.pathfinding.lastCalculationTime + 'ms';
        if(el('metric-nodes')) el('metric-nodes').textContent = d.pathfinding.avgNodesExplored.toFixed(0);
        if(el('metric-min-time')) el('metric-min-time').textContent = d.pathfinding.minCalculationTime + 'ms';
        if(el('metric-max-time')) el('metric-max-time').textContent = d.pathfinding.maxCalculationTime + 'ms';
        if(el('metric-path-length')) el('metric-path-length').textContent = d.pathfinding.avgPathLength;
        if(el('metric-graph-nodes')) el('metric-graph-nodes').textContent = d.graph.totalNodes;
        if(el('metric-graph-edges')) el('metric-graph-edges').textContent = d.graph.totalEdges;
        if(el('metric-rain-count')) el('metric-rain-count').textContent = d.activeFactors.rainZones;
        if(el('metric-traffic-count')) el('metric-traffic-count').textContent = d.activeFactors.trafficRoutes;
        if(el('metric-obstacle-count')) el('metric-obstacle-count').textContent = d.activeFactors.obstacles;
    } catch(e) { console.error('Metrics:', e); }
}

setInterval(() => {
    const p = document.querySelector('.decision-panel');
    if (p && p.style.display === 'block') fetchMetrics();
}, 3000);

// Auto-refresh computing panel every 2s
setInterval(() => {
    const compPanel = document.querySelector('.computing-panel');
    if (compPanel && compPanel.style.display === 'block' && simulation?.robots) {
        // Update with last clicked robot's data
        const content = document.getElementById('computing-content');
        if (content && content.dataset.robotId) {
            const robot = simulation.robots.find(r => r.id == content.dataset.robotId);
            if (robot) content.innerHTML = robot.getComputingDetails();
        }
    }
}, 2000);

// ===== A* Visualization =====
async function showAStarProcess(robotId) {
    const el = document.getElementById(`astep-visual-${robotId}`);
    if (!el || !simulation?.robots) return;
    
    const robot = simulation.robots.find(r => r.id === robotId);
    if (!robot || !robot.routeTarget) {
        el.style.display = 'block';
        el.innerHTML = '<div style="padding:10px;text-align:center;color:#5f6368;">Robot has no active route. Wait for it to accept a delivery.</div>';
        return;
    }
    
    el.style.display = 'block';
    el.innerHTML = '<div style="padding:10px;text-align:center;">⏳ Computing A*...</div>';
    
    try {
        const d = await (await fetch(`/api/astep?fromLat=${robot.lat}&fromLon=${robot.lon}&toLat=${robot.routeTarget.lat}&toLon=${robot.routeTarget.lon}`)).json();
        
        if (!d.steps || d.steps.length === 0) {
            el.innerHTML = '<div style="padding:10px;text-align:center;color:#ea4335;">No steps recorded</div>';
            return;
        }
        
        // Build step-by-step visualization
        let html = `
            <div style="margin:8px 0;background:linear-gradient(135deg,#e3f2fd,#bbdefb);border-radius:10px;padding:12px;">
                <div style="font-size:13px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;gap:6px;">
                    🔬 A* Step-by-Step Calculation
                    <span style="font-size:10px;color:#5f6368;font-weight:400;">(${d.calcTime}ms, ${d.totalSteps} steps)</span>
                </div>
                
                <div style="background:white;border-radius:8px;padding:8px;margin:6px 0;">
                    <div style="font-size:10px;color:#5f6368;margin-bottom:4px;"><strong>Start:</strong> Node ${d.startNode} → <strong>Goal:</strong> Node ${d.endNode}</div>
                    <div style="display:flex;gap:8px;font-size:9px;color:#5f6368;">
                        <span>Open Set: <strong>${d.openSetSize}</strong></span>
                        <span>Closed Set: <strong>${d.closedSetSize}</strong></span>
                        <span>Path: <strong style="color:#1a73e8;">${d.pathLength} nodes</strong></span>
                    </div>
                </div>
        `;
        
        // Show first 3 steps in detail, then summary
        d.steps.slice(0, 3).forEach(s => {
            const color = s.step === 1 ? '#34a853' : s.step === 2 ? '#1a73e8' : '#ff9800';
            html += `
                <div style="background:white;border-radius:8px;padding:8px;margin:6px 0;border-left:4px solid ${color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                        <span style="font-size:11px;font-weight:700;color:${color};">Step ${s.step}</span>
                        <span style="font-size:9px;color:#5f6368;">Node ${s.currentNode}</span>
                    </div>
                    <div style="font-size:10px;font-family:monospace;background:#f8f9fa;padding:4px 6px;border-radius:4px;margin:3px 0;">
                        ${s.formula}
                    </div>
                    <div style="display:flex;gap:12px;font-size:9px;color:#5f6368;">
                        <span>g=${s.g}</span><span>h=${s.h}</span><span>f=${s.f}</span>
                        <span>Open:${s.openSetSize}</span><span>Closed:${s.closedSetSize}</span>
                    </div>
                </div>
            `;
        });
        
        if (d.steps.length > 3) {
            html += `
                <div style="text-align:center;padding:6px;font-size:10px;color:#5f6368;background:white;border-radius:6px;margin:4px 0;">
                    ... ${d.steps.length - 3} more steps ...
                </div>
                <div style="background:white;border-radius:8px;padding:8px;margin:6px 0;border-left:4px solid #34a853;">
                    <div style="font-size:11px;font-weight:700;color:#34a853;">✅ Goal Reached! (Step ${d.totalSteps})</div>
                    <div style="font-size:10px;color:#5f6368;">Path reconstructed: ${d.pathLength} nodes</div>
                </div>
            `;
        }
        
        // Show penalties applied
        const hasRain = RAIN_ZONES && RAIN_ZONES.length > 0;
        const hasTraffic = true; // Always has traffic simulation
        const hasObstacles = typeof _obstacles !== 'undefined' && _obstacles && _obstacles.length > 0;
        
        html += `
                <div style="background:white;border-radius:8px;padding:8px;margin:6px 0;">
                    <div style="font-size:10px;font-weight:700;margin-bottom:4px;">⚙️ Penalties Applied:</div>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;font-size:9px;">
                        ${hasRain ? '<span style="background:#e3f2fd;padding:3px 6px;border-radius:4px;">🌧️ Rain: 2×</span>' : ''}
                        <span style="background:#fce4ec;padding:3px 6px;border-radius:4px;">🚗 Traffic: 1.5-4×</span>
                        ${hasObstacles ? '<span style="background:#fff3e0;padding:3px 6px;border-radius:4px;">🚧 Obstacles: 5-50×</span>' : ''}
                    </div>
                </div>
            </div>
        `;
        
        el.innerHTML = html;
    } catch(e) {
        el.innerHTML = `<div style="padding:10px;text-align:center;color:#ea4335;">Error: ${e.message}</div>`;
    }
}

// Make it global
window.showAStarProcess = showAStarProcess;

// ===== CLOCK =====
async function updateClock() {
    try {
        const d = await (await fetch('/api/clock')).json();
        const cl = document.getElementById('clock-time');
        if (cl) cl.textContent = d.time.display;
        const rh = document.getElementById('rush-hour-display');
        const rm = document.getElementById('rush-multiplier');
        if (d.rushHour.isActive) {
            if (rh) { rh.style.display = 'inline-block'; if (rm) rm.textContent = d.rushHour.multiplier.toFixed(1); }
        } else { if (rh) rh.style.display = 'none'; }
    } catch(e) {}
}

window.addEventListener('load', () => {
    init().catch(e => { console.error(e); logEvent('❌ Init failed'); });
});
