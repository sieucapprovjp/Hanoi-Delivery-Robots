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

// ========== Weather & Traffic Controls ==========
let weatherMode = 'rain';
let rainCircles = [];
let trafficPolylines = [];
let obstacleCircles = [];
let trafficClickPoints = [];
let weatherModeEnabled = false;

function setupWeatherControls() {
    document.getElementById('toggle-weather')?.addEventListener('click', () => {
        const p = document.querySelector('.weather-panel');
        const isHidden = p.style.display === 'none';
        p.style.display = isHidden ? 'block' : 'none';
        weatherModeEnabled = isHidden;
    });

    document.getElementById('close-weather-panel')?.addEventListener('click', () => {
        document.querySelector('.weather-panel').style.display = 'none';
        weatherModeEnabled = false;
    });

    document.querySelectorAll('.weather-panel .mode-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.weather-panel .mode-tab').forEach(t => {
                t.style.background = '#e8eaed';
                t.style.color = '#3c4043';
            });
            tab.style.background = '#1a73e8';
            tab.style.color = 'white';
            weatherMode = tab.dataset.mode;
            
            document.getElementById('rain-controls').style.display = weatherMode === 'rain' ? 'block' : 'none';
            document.getElementById('traffic-controls').style.display = weatherMode === 'traffic' ? 'block' : 'none';
            document.getElementById('obstacle-controls').style.display = weatherMode === 'obstacle' ? 'block' : 'none';
        });
    });

    const rainRadius = document.getElementById('rain-radius');
    rainRadius?.addEventListener('input', (e) => {
        document.getElementById('rain-radius-value').textContent = e.target.value;
    });

    const trafficSeverity = document.getElementById('traffic-severity');
    trafficSeverity?.addEventListener('input', (e) => {
        document.getElementById('traffic-severity-value').textContent = e.target.value;
    });

    const obstacleRadius = document.getElementById('obstacle-radius');
    obstacleRadius?.addEventListener('input', (e) => {
        document.getElementById('obstacle-radius-value').textContent = e.target.value;
    });

    const obstacleSeverity = document.getElementById('obstacle-severity');
    obstacleSeverity?.addEventListener('input', (e) => {
        document.getElementById('obstacle-severity-value').textContent = e.target.value;
    });

    document.querySelectorAll('.algo-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.algo-btn').forEach(b => {
                b.style.background = '#e8eaed';
                b.style.color = '#3c4043';
            });
            btn.style.background = '#1a73e8';
            btn.style.color = 'white';
            if (window.simulation) {
                window.simulation.schedulingAlgorithm = btn.dataset.algo;
                logEvent(`🧠 Algorithm switched to: ${btn.dataset.algo.toUpperCase()}`);
            }
        });
    });

    document.getElementById('randomize-rain-btn')?.addEventListener('click', randomizeRain);
    document.getElementById('clear-rain-btn')?.addEventListener('click', clearRain);
    document.getElementById('reset-traffic-points-btn')?.addEventListener('click', () => { trafficClickPoints = []; });
    document.getElementById('randomize-traffic-btn')?.addEventListener('click', randomizeTraffic);
    document.getElementById('clear-traffic-btn')?.addEventListener('click', clearTraffic);
    document.getElementById('randomize-obstacle-btn')?.addEventListener('click', randomizeObstacles);
    document.getElementById('clear-obstacle-btn')?.addEventListener('click', clearObstacles);

    updateRainList();
    updateTrafficList();
    updateObstacleList();
}

async function addRainZone(lat, lon, radius) {
    try {
        const response = await fetch('/api/rain/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lat, lon, radius})
        });
        const data = await response.json();
        if (response.ok) {
            displayRainZone(data.rainZone);
            updateRainList();
            logEvent(`🌧️ Rain zone added: ${data.rainZone.name}`);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

function displayRainZone(zone) {
    if (!window.map) return;
    const circle = L.circle([zone.center.lat, zone.center.lon], {
        color: '#4285f4',
        fillColor: '#4285f4',
        fillOpacity: 0.2,
        radius: zone.radius
    }).addTo(window.map);
    circle.bindPopup(`<strong>${zone.name}</strong><br>Radius: ${Math.round(zone.radius)}m`);
    rainCircles.push(circle);
}

async function updateRainList() {
    try {
        const response = await fetch('/api/rain/list');
        const data = await response.json();
        const el = document.getElementById('rain-list');
        if (!el) return;
        
        if (data.rainZones.length === 0) {
            el.innerHTML = '<div style="padding: 5px 0;">No rain zones</div>';
        } else {
            el.innerHTML = data.rainZones.map((z, i) => 
                `<div style="padding: 4px 0; border-bottom: 1px solid #e0e0e0;">
                    <strong>${i+1}. ${z.name}</strong><br>
                    ${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m
                </div>`
            ).join('');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function randomizeRain() {
    try {
        const response = await fetch('/api/rain/randomize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({count: 3, minRadius: 100, maxRadius: 200})
        });
        const data = await response.json();
        if (response.ok) {
            rainCircles.forEach(c => window.map.removeLayer(c));
            rainCircles = [];
            data.rainZones.forEach(z => displayRainZone(z));
            updateRainList();
            logEvent('🎲 Rain zones randomized');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function clearRain() {
    try {
        await fetch('/api/rain/clear', {method: 'POST'});
        rainCircles.forEach(c => window.map.removeLayer(c));
        rainCircles = [];
        updateRainList();
        logEvent('🗑️ All rain zones cleared');
    } catch (error) {
        console.error('Error:', error);
    }
}

function addTrafficPoint(lat, lon) {
    trafficClickPoints.push([lat, lon]);
    if (!window.map) return;
    
    L.circleMarker([lat, lon], {
        color: '#ea4335',
        fillColor: '#ea4335',
        fillOpacity: 0.8,
        radius: 6
    }).addTo(window.map);

    if (trafficClickPoints.length === 2) {
        createTrafficRoute();
    }
}

async function createTrafficRoute() {
    const [start, end] = trafficClickPoints;
    const severity = parseFloat(document.getElementById('traffic-severity').value);

    try {
        const response = await fetch('/api/traffic/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                startLat: start[0], startLon: start[1],
                endLat: end[0], endLon: end[1],
                severity: severity,
                name: 'Custom Traffic'
            })
        });
        const data = await response.json();
        if (response.ok) {
            const route = data.route;
            const coords = route.path.map(p => [p.lat, p.lon]);
            const polyline = L.polyline(coords, {
                color: '#ea4335', weight: 5, opacity: 0.7
            }).addTo(window.map);
            polyline.bindPopup(`<strong>${route.name}</strong><br>Severity: ${route.severity.toFixed(2)}`);
            trafficPolylines.push(polyline);
            trafficClickPoints = [];
            updateTrafficList();
            logEvent(`🚗 Traffic route added: ${route.name}`);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function updateTrafficList() {
    try {
        const response = await fetch('/api/traffic/list');
        const data = await response.json();
        const el = document.getElementById('traffic-list');
        if (!el) return;
        
        if (data.routes.length === 0) {
            el.innerHTML = '<div style="padding: 5px 0;">No traffic routes</div>';
        } else {
            el.innerHTML = data.routes.map((r, i) => 
                `<div style="padding: 4px 0; border-bottom: 1px solid #e0e0e0;">
                    <strong>${i+1}. ${r.name}</strong><br>
                    Severity: ${r.severity.toFixed(2)}
                </div>`
            ).join('');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function randomizeTraffic() {
    try {
        const response = await fetch('/api/traffic/randomize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({count: 3, minSeverity: 0.4, maxSeverity: 0.9})
        });
        const data = await response.json();
        if (response.ok) {
            trafficPolylines.forEach(p => window.map.removeLayer(p));
            trafficPolylines = [];
            data.routes.forEach(route => {
                const coords = route.path.map(p => [p.lat, p.lon]);
                const polyline = L.polyline(coords, {
                    color: '#ea4335', weight: 5, opacity: 0.7
                }).addTo(window.map);
                trafficPolylines.push(polyline);
            });
            updateTrafficList();
            logEvent('🎲 Traffic routes randomized');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function clearTraffic() {
    try {
        await fetch('/api/traffic/clear', {method: 'POST'});
        trafficPolylines.forEach(p => window.map.removeLayer(p));
        trafficPolylines = [];
        updateTrafficList();
        logEvent('🗑️ All traffic routes cleared');
    } catch (error) {
        console.error('Error:', error);
    }
}

// ========== Obstacle Functions ==========
async function addObstacle(lat, lon, radius, severity) {
    try {
        const response = await fetch('/api/obstacle/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lat, lon, radius, severity, type: 'roadblock'})
        });
        const data = await response.json();
        if (response.ok) {
            displayObstacle(data.obstacle);
            updateObstacleList();
            logEvent(`🚧 Obstacle added: ${data.obstacle.name}`);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

function displayObstacle(obstacle) {
    if (!window.map) return;
    const colors = {roadblock: '#ff6b6b', construction: '#ffa94d', accident: '#ffd43b'};
    const color = colors[obstacle.type] || '#ff6b6b';
    
    const circle = L.circle([obstacle.center.lat, obstacle.center.lon], {
        color: color,
        fillColor: color,
        fillOpacity: 0.3,
        radius: obstacle.radius
    }).addTo(window.map);
    circle.bindPopup(`<strong>${obstacle.name}</strong><br>Severity: ${obstacle.severity.toFixed(1)}`);
    obstacleCircles.push(circle);
}

async function updateObstacleList() {
    try {
        const response = await fetch('/api/obstacle/list');
        const data = await response.json();
        const el = document.getElementById('obstacle-list');
        if (!el) return;
        
        if (data.obstacles.length === 0) {
            el.innerHTML = '<div style="padding: 5px 0;">No obstacles</div>';
        } else {
            el.innerHTML = data.obstacles.map((o, i) => 
                `<div style="padding: 4px 0; border-bottom: 1px solid #e0e0e0;">
                    <strong>${i+1}. ${o.name}</strong><br>
                    ${o.center.lat.toFixed(4)}, ${o.center.lon.toFixed(4)} | ${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}
                </div>`
            ).join('');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function randomizeObstacles() {
    try {
        const response = await fetch('/api/obstacle/randomize', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({count: 4})
        });
        const data = await response.json();
        if (response.ok) {
            obstacleCircles.forEach(c => window.map.removeLayer(c));
            obstacleCircles = [];
            data.obstacles.forEach(o => displayObstacle(o));
            updateObstacleList();
            logEvent('🎲 Obstacles randomized');
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function clearObstacles() {
    try {
        await fetch('/api/obstacle/clear', {method: 'POST'});
        obstacleCircles.forEach(c => window.map.removeLayer(c));
        obstacleCircles = [];
        updateObstacleList();
        logEvent('🗑️ All obstacles cleared');
    } catch (error) {
        console.error('Error:', error);
    }
}

// ========== Metrics & Decision Making ==========
async function fetchMetrics() {
    try {
        const response = await fetch('/api/metrics');
        const data = await response.json();
        
        const el = id => document.getElementById(id);
        
        // A* metrics
        if (el('metric-total-calc')) el('metric-total-calc').textContent = data.pathfinding.totalCalculations;
        if (el('metric-avg-time')) el('metric-avg-time').textContent = `${data.pathfinding.avgCalculationTime}ms`;
        if (el('metric-last-time')) el('metric-last-time').textContent = `${data.pathfinding.lastCalculationTime}ms`;
        if (el('metric-nodes')) el('metric-nodes').textContent = data.pathfinding.avgNodesExplored.toFixed(0);
        if (el('metric-min-time')) el('metric-min-time').textContent = `${data.pathfinding.minCalculationTime}ms`;
        if (el('metric-max-time')) el('metric-max-time').textContent = `${data.pathfinding.maxCalculationTime}ms`;
        if (el('metric-path-length')) el('metric-path-length').textContent = data.pathfinding.avgPathLength;
        
        // Graph info
        if (el('metric-graph-nodes')) el('metric-graph-nodes').textContent = data.graph.totalNodes;
        if (el('metric-graph-edges')) el('metric-graph-edges').textContent = data.graph.totalEdges;
        
        // Active factors
        if (el('metric-rain-count')) el('metric-rain-count').textContent = data.activeFactors.rainZones;
        if (el('metric-traffic-count')) el('metric-traffic-count').textContent = data.activeFactors.trafficRoutes;
        if (el('metric-obstacle-count')) el('metric-obstacle-count').textContent = data.activeFactors.obstacles;
    } catch (error) {
        console.error('Error fetching metrics:', error);
    }
}

// Auto-refresh metrics every 3 seconds if panel is visible
setInterval(() => {
    const panel = document.querySelector('.decision-panel');
    if (panel && panel.style.display === 'block') {
        fetchMetrics();
    }
}, 3000);

async function init() {
    simulation = new Simulation();
    window.simulation = simulation;
    await simulation.initialize();
    setupControls();
    setupWeatherControls();
}

function setupControls() {
    document.getElementById('start-btn')?.addEventListener('click', () => simulation?.start());
    document.getElementById('pause-btn')?.addEventListener('click', () => simulation?.pause());
    document.getElementById('reset-btn')?.addEventListener('click', () => simulation?.reset());

    const slider = document.getElementById('speed-slider');
    const value = document.getElementById('speed-value');
    slider?.addEventListener('input', (e) => {
        const speed = parseInt(e.target.value);
        if (simulation) simulation.speed = speed;
        value.textContent = `${speed}x`;
    });

    document.getElementById('toggle-robots')?.addEventListener('click', () => {
        const p = document.querySelector('.robot-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-deliveries')?.addEventListener('click', () => {
        const p = document.querySelector('.delivery-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-log')?.addEventListener('click', () => {
        const p = document.querySelector('.log-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-dispatch')?.addEventListener('click', () => {
        const p = document.querySelector('.dispatch-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });
    document.getElementById('toggle-analytics')?.addEventListener('click', () => {
        const p = document.querySelector('.analytics-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
    });

    document.getElementById('toggle-decision')?.addEventListener('click', () => {
        const p = document.querySelector('.decision-panel');
        p.style.display = p.style.display === 'none' ? 'block' : 'none';
        if (p.style.display === 'block') {
            fetchMetrics();
        }
    });

    document.getElementById('close-decision-panel')?.addEventListener('click', () => {
        document.querySelector('.decision-panel').style.display = 'none';
    });

    document.getElementById('close-dispatch-panel')?.addEventListener('click', () => {
        const p = document.querySelector('.dispatch-panel');
        p.style.display = 'none';
    });
    document.getElementById('close-analytics-panel')?.addEventListener('click', () => {
        const p = document.querySelector('.analytics-panel');
        p.style.display = 'none';
    });

    // Weather panel map click integration (deferred)
    setTimeout(() => {
        if (window.map) {
            window.map.on('click', function(e) {
                if (!weatherModeEnabled) return;
                
                const lat = e.latlng.lat;
                const lon = e.latlng.lng;

                if (weatherMode === 'rain') {
                    addRainZone(lat, lon, parseInt(document.getElementById('rain-radius').value));
                } else if (weatherMode === 'traffic') {
                    addTrafficPoint(lat, lon);
                } else if (weatherMode === 'obstacle') {
                    addObstacle(lat, lon, parseInt(document.getElementById('obstacle-radius').value), parseInt(document.getElementById('obstacle-severity').value));
                }
            });
        }
    }, 1000);
}

window.addEventListener('load', () => {
    init().catch(error => {
        console.error(error);
        logEvent('❌ Failed to initialize simulation');
    });
});
