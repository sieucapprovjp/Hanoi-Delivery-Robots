class ObstacleManager {
    constructor() {
        this.obstacleCircles = [];
    }

    async addObstacle(lat, lon, radius, severity) {
        const res = await fetch(CONFIG.API.OBSTACLE_ADD, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lat,
                lon,
                radius,
                severity,
                type: CONFIG.SIMULATION.DEFAULT_OBSTACLE_TYPE
            })
        });
        const d = await res.json();
        if (res.ok) {
            this.displayObstacle(d.obstacle);
            this.updateObstacleList();
            logEvent('🚧 ' + d.obstacle.name);
        }
    }

    displayObstacle(o) {
        if (!window.map) return;
        const colors = CONFIG.OBSTACLE_COLORS;
        const c = L.circle([o.center.lat, o.center.lon], {
            color: colors[o.type] || CONFIG.ROBOT.COLORS.error,
            fillColor: colors[o.type] || CONFIG.ROBOT.COLORS.error,
            fillOpacity: CONFIG.UI.OPACITY.medium,
            radius: o.radius
        }).addTo(window.map);
        
        c.bindPopup(`<strong>${o.name}</strong><br>Severity: ${o.severity.toFixed(1)}`);
        this.obstacleCircles.push(c);
    }

    async updateObstacleList() {
        try {
            const res = await fetch(CONFIG.API.OBSTACLE_LIST);
            const d = await res.json();
            const html = d.obstacles.length 
                ? d.obstacles.map((o, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${o.name}</strong><br>${Math.round(o.radius)}m | Sev: ${o.severity.toFixed(1)}</div>`).join('') 
                : 'No obstacles';
            
            const store = Alpine.store('sim');
            if (store) store.weather.obstaclesHtml = html;
        } catch (error) {
            console.error('Failed to update obstacle list:', error);
        }
    }

    async randomizeObstacles() {
        const res = await fetch(CONFIG.API.OBSTACLE_RANDOMIZE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: CONFIG.SIMULATION.RANDOM_OBSTACLE_COUNT })
        });
        const d = await res.json();
        
        this.clearObstacleLayers();
        d.obstacles.forEach(o => this.displayObstacle(o));
        this.updateObstacleList();
        logEvent('🎲 Obstacles');
    }

    async clearObstacles() {
        await fetch(CONFIG.API.OBSTACLE_CLEAR, { method: 'POST' });
        this.clearObstacleLayers();
        this.updateObstacleList();
        logEvent('🗑️ Obstacles');
    }

    clearObstacleLayers() {
        if (window.map) {
            this.obstacleCircles.forEach(c => window.map.removeLayer(c));
        }
        this.obstacleCircles = [];
    }
}
