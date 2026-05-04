class HanoiMap {
    constructor() {
        this.map = null;
        this.chargingStations = [];
        this.trafficJams = [];
        this.roadblocks = [];
        this.trafficLayers = [];
        this.trafficRefreshHandle = null;
        this.rainZones = [];
        this.rainLayers = [];
    }

    async initializeMap() {
        this.map = L.map('map').setView(CONFIG.MAP.INITIAL_VIEW, CONFIG.MAP.INITIAL_ZOOM);
        window.map = this.map;

        L.tileLayer(CONFIG.MAP.TILE_LAYER_URL, {
            maxZoom: CONFIG.MAP.MAX_ZOOM,
            attribution: CONFIG.MAP.ATTRIBUTION
        }).addTo(this.map);

        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        await this.setupChargingStations();
        await this.renderLocations();
        this.loadWeather();
        this.startTraffic();

        console.log('✓ Map Display Ready');
    }

    async renderLocations() {
        if (!pathfindingManager) return;
        const data = await pathfindingManager.getLocations();

        data.locations.forEach(loc => {
            L.marker([loc.lat, loc.lon], {
                icon: L.divIcon({
                    className: 'location-marker',
                    html: `<div class="location-inner">${loc.icon || '📍'}</div>`,
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                })
            }).addTo(this.map).bindTooltip(loc.name);
        });
    }

    async setupChargingStations() {
        if (!pathfindingManager) return;
        const data = await pathfindingManager.getHubs();
        const locations = data.hubs;

        locations.forEach(loc => {
            const station = {
                lat: loc.lat, lon: loc.lon,
                name: loc.name, totalSpots: loc.spots, availableSpots: loc.spots,
                marker: null
            };

            station.marker = L.marker([loc.lat, loc.lon], {
                icon: L.divIcon({
                    className: 'charging-station-marker',
                    html: `<div class="charging-station-inner">⚡</div>`,
                    iconSize: [CONFIG.UI.RADII.markerLarge * 6, CONFIG.UI.RADII.markerLarge * 6],
                    iconAnchor: [CONFIG.UI.RADII.markerLarge * 3, CONFIG.UI.RADII.markerLarge * 3]
                }),
                zIndexOffset: 900
            }).addTo(this.map);

            this.chargingStations.push(station);
        });
    }

    enableRainOverlay() {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes rain { 0% { background-position: 0% 0%; } 100% { background-position: 20% 100%; } }
            #map::after {
                content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
                background: repeating-linear-gradient(170deg, rgba(174,194,224,0.1) 0px, rgba(174,194,224,0.15) 2px, transparent 2px, transparent 8px);
                animation: rain 0.5s linear infinite; pointer-events: none; z-index: 1000;
            }
        `;
        document.head.appendChild(style);
    }

    async loadWeather() {
        this.enableRainOverlay();
        if (typeof pathfindingManager === 'undefined' || !pathfindingManager) return;
        try {
            const weather = await pathfindingManager.getWeather();
            this.rainZones = weather.rainZones || [];
            this.renderRainZones();
        } catch (error) {
            console.error('Weather load failed', error);
        }
    }

    renderRainZones() {
        this.rainLayers.forEach(layer => layer.remove());
        this.rainLayers = [];

        this.rainZones.forEach(zone => {
            const halo = L.circle([zone.center.lat, zone.center.lon], {
                radius: zone.radius,
                color: CONFIG.MAP.RAIN_COLORS.halo,
                weight: 2,
                opacity: 0.45,
                fillColor: CONFIG.MAP.RAIN_COLORS.fill,
                fillOpacity: 0.12
            }).addTo(this.map);

            const core = L.circle([zone.center.lat, zone.center.lon], {
                radius: zone.radius * CONFIG.MAP.RAIN_ZONES_CORE_SCALE,
                color: CONFIG.MAP.RAIN_COLORS.core,
                weight: 1,
                opacity: 0.3,
                fillColor: CONFIG.MAP.RAIN_COLORS.halo,
                fillOpacity: 0.12
            }).addTo(this.map).bindTooltip(`🌧 ${zone.name}`);

            this.rainLayers.push(halo, core);
        });
    }

    startTraffic() {
        this.refreshTraffic();
        this.trafficRefreshHandle = setInterval(() => this.refreshTraffic(), CONFIG.UI.TRAFFIC_REFRESH_INTERVAL_MS);
    }

    async refreshTraffic() {
        if (typeof pathfindingManager === 'undefined' || !pathfindingManager) return;
        try {
            const traffic = await pathfindingManager.getTraffic();
            this.trafficJams = traffic.roads;
            this.renderTraffic();
        } catch (error) {
            console.error('Traffic refresh failed', error);
        }
    }

    renderTraffic() {
        this.trafficLayers.forEach(layer => layer.remove());
        this.trafficLayers = [];

        this.trafficJams.forEach(road => {
            road.segments.forEach(segment => {
                const latlngs = segment.points.map(point => [point[0], point[1]]);
                const core = L.polyline(latlngs, {
                    color: segment.severity > 0.55 ? CONFIG.MAP.TRAFFIC_COLORS.heavy : CONFIG.MAP.TRAFFIC_COLORS.moderate,
                    weight: segment.severity > 0.55 ? 5 : 4,
                    opacity: 0.85,
                    lineCap: 'round',
                    dashArray: '10, 10'
                }).addTo(this.map).bindTooltip(`${road.name} traffic ${(segment.severity * 100).toFixed(0)}%`);

                this.trafficLayers.push(core);
            });
        });
    }
}