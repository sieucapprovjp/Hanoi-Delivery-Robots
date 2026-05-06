class TrafficManager {
    constructor() {
        this.trafficPolylines = [];
        this.trafficPointA = null;
        this.trafficPointMarkerA = null;
    }

    resetTrafficPoints() {
        this.trafficPointA = null;
        if (this.trafficPointMarkerA && window.map) {
            window.map.removeLayer(this.trafficPointMarkerA);
        }
        this.trafficPointMarkerA = null;
        logEvent('🔄 Traffic points reset');
    }

    handleTrafficClick(lat, lon) {
        if (!window.map) return;

        const severity = +document.getElementById('traffic-severity')?.value || CONFIG.SIMULATION.DEFAULT_TRAFFIC_SEVERITY;

        if (!this.trafficPointA) {
            this.trafficPointA = { lat, lon };
            if (this.trafficPointMarkerA) window.map.removeLayer(this.trafficPointMarkerA);
            
            this.trafficPointMarkerA = L.circleMarker([lat, lon], {
                radius: CONFIG.UI.RADII.markerLarge,
                color: CONFIG.ROBOT.COLORS.error,
                fillColor: CONFIG.ROBOT.COLORS.error,
                fillOpacity: 1
            }).addTo(window.map);
            
            this.trafficPointMarkerA.bindPopup('<strong>Traffic start</strong><br>Click another point to set the end.');
            logEvent('🚗 Traffic start set');
            return;
        }

        const trafficPointB = { lat, lon };
        this.addTrafficRoute(this.trafficPointA, trafficPointB, severity)
            .finally(() => this.resetTrafficPoints());
    }

    async addTrafficRoute(start, end, severity) {
        const res = await fetch(CONFIG.API.TRAFFIC_ADD, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                startLat: start.lat,
                startLon: start.lon,
                endLat: end.lat,
                endLon: end.lon,
                severity
            })
        });
        
        const d = await res.json();
        if (!res.ok) {
            logEvent('❌ Traffic: ' + (d.error || res.status));
            return;
        }

        const route = d.route;
        if (route?.path?.length) {
            const polyline = L.polyline(route.path.map(p => [p.lat, p.lon]), {
                color: CONFIG.ROBOT.COLORS.error,
                weight: CONFIG.UI.WEIGHTS.thick,
                opacity: CONFIG.UI.OPACITY.high
            })
            .addTo(window.map)
            .bindPopup(`<strong>${route.name}</strong><br>Severity: ${route.severity.toFixed(2)}`);
            
            this.trafficPolylines.push(polyline);
        }
        
        this.updateTrafficList();
        logEvent('🚗 ' + route.name);
    }

    async updateTrafficList() {
        try {
            const res = await fetch(CONFIG.API.TRAFFIC_LIST);
            const d = await res.json();
            const html = d.routes.length 
                ? d.routes.map((r, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${r.name}</strong><br>Severity: ${r.severity.toFixed(2)}</div>`).join('') 
                : 'No traffic routes';
            
            const store = Alpine.store('sim');
            if (store) store.weather.trafficRoutesHtml = html;
        } catch (error) {
            console.error('Failed to update traffic list:', error);
        }
    }

    async randomizeTraffic() {
        const res = await fetch(CONFIG.API.TRAFFIC_RANDOMIZE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count: CONFIG.SIMULATION.RANDOM_TRAFFIC_COUNT })
        });
        const d = await res.json();
        
        this.clearTrafficLayers();
        d.routes.forEach(r => {
            const polyline = L.polyline(r.path.map(p => [p.lat, p.lon]), {
                color: CONFIG.ROBOT.COLORS.error,
                weight: CONFIG.UI.WEIGHTS.thick,
                opacity: CONFIG.UI.OPACITY.high
            }).addTo(window.map);
            this.trafficPolylines.push(polyline);
        });
        
        this.updateTrafficList();
        logEvent('🎲 Traffic');
    }

    async clearTraffic() {
        await fetch(CONFIG.API.TRAFFIC_CLEAR, { method: 'POST' });
        this.clearTrafficLayers();
        this.updateTrafficList();
        logEvent('🗑️ Traffic');
    }

    clearTrafficLayers() {
        if (window.map) {
            this.trafficPolylines.forEach(p => window.map.removeLayer(p));
        }
        this.trafficPolylines = [];
    }
}
