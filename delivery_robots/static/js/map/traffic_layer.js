HanoiMap.prototype.startTraffic = function () {
    this.refreshTraffic();
    this.trafficRefreshHandle = setInterval(() => this.refreshTraffic(), CONFIG.UI.TRAFFIC_REFRESH_INTERVAL_MS);
};

HanoiMap.prototype.refreshTraffic = async function () {
    if (typeof pathfindingManager === 'undefined' || !pathfindingManager) {
        return;
    }

    try {
        const traffic = await pathfindingManager.getTraffic();
        this.trafficJams = traffic.roads;
        this.renderTraffic();
    } catch (error) {
        console.error('Traffic refresh failed', error);
    }
};

HanoiMap.prototype.renderTraffic = function () {
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
};
