class RainManager {
    constructor() {
        this.rainCircles = [];
    }

    async addRainZone(lat, lon, radius) {
        const res = await fetch(CONFIG.API.RAIN_ADD, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat, lon, radius })
        });
        const d = await res.json();
        if (res.ok) {
            this.displayRainZone(d.rainZone);
            this.updateRainList();
            logEvent('🌧️ ' + d.rainZone.name);
        }
    }

    displayRainZone(z) {
        if (!window.map) return;
        const c = L.circle([z.center.lat, z.center.lon], {
            color: CONFIG.ROBOT.COLORS.info,
            fillColor: CONFIG.ROBOT.COLORS.info,
            fillOpacity: 0.2,
            radius: z.radius
        }).addTo(window.map);
        
        c.bindPopup(`<strong>${z.name}</strong><br>Radius: ${Math.round(z.radius)}m`);
        this.rainCircles.push(c);
    }

    async updateRainList() {
        try {
            const res = await fetch(CONFIG.API.RAIN_LIST);
            const d = await res.json();
            const html = d.rainZones.length 
                ? d.rainZones.map((z, i) => `<div class="py-4 border-bottom-standard"><strong>${i + 1}. ${z.name}</strong><br>${z.center.lat.toFixed(4)}, ${z.center.lon.toFixed(4)} | ${Math.round(z.radius)}m</div>`).join('') 
                : 'No rain zones';
            
            const store = Alpine.store('sim');
            if (store) store.weather.rainZonesHtml = html;
        } catch (error) {
            console.error('Failed to update rain list:', error);
        }
    }

    async randomizeRain() {
        const res = await fetch(CONFIG.API.RAIN_RANDOMIZE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                count: CONFIG.SIMULATION.RANDOM_RAIN_COUNT,
                minRadius: CONFIG.SIMULATION.RANDOM_RAIN_MIN_RADIUS,
                maxRadius: CONFIG.SIMULATION.RANDOM_RAIN_MAX_RADIUS
            })
        });
        const d = await res.json();
        
        this.clearRainLayers();
        d.rainZones.forEach(z => this.displayRainZone(z));
        this.updateRainList();
        logEvent('🎲 Rain');
    }

    async clearRain() {
        await fetch(CONFIG.API.RAIN_CLEAR, { method: 'POST' });
        this.clearRainLayers();
        this.updateRainList();
        logEvent('🗑️ Rain');
    }

    clearRainLayers() {
        if (window.map) {
            this.rainCircles.forEach(c => window.map.removeLayer(c));
        }
        this.rainCircles = [];
    }
}
