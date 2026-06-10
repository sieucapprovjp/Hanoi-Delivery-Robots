HanoiMap.prototype.enableRainOverlay = function () {
    if (this.rainOverlayEnabled) return;

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
    this.rainOverlayEnabled = true;
};

HanoiMap.prototype.loadWeather = async function () {
    this.enableRainOverlay();

    if (typeof pathfindingManager === 'undefined' || !pathfindingManager) {
        return;
    }

    try {
        const weather = await pathfindingManager.getWeather();
        this.rainZones = weather.rainZones || [];
        this.renderRainZones();
    } catch (error) {
        console.error('Weather load failed', error);
    }
};

HanoiMap.prototype.renderRainZones = function () {
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
        }).addTo(this.map).bindTooltip(`🌧 ${zone.name} rain x${zone.multiplier.toFixed(1)}`);

        this.rainLayers.push(halo, core);
    });
};
