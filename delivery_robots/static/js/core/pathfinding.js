class Pathfinding {
    async getRoute(startLat, startLon, endLat, endLon, roadMemory = {}, algo = CONFIG.SIMULATION.DEFAULT_ALGORITHM) {
        const params = new URLSearchParams({
            fromLat: startLat,
            fromLon: startLon,
            toLat: endLat,
            toLon: endLon,
            memory: JSON.stringify(roadMemory),
            algo
        });

        return getJson(`${CONFIG.API.ROUTE}?${params.toString()}`, null, CONFIG.UI.TEXT.API_ERRORS.ROUTE);
    }

    async snapToRoad(lat, lon) {
        const params = new URLSearchParams({ lat, lon });
        return getJson(`${CONFIG.API.SNAP}?${params.toString()}`, null, CONFIG.UI.TEXT.API_ERRORS.SNAP);
    }

    async getTraffic() {
        return getJson(CONFIG.API.TRAFFIC, null, CONFIG.UI.TEXT.API_ERRORS.TRAFFIC);
    }

    async getWeather() {
        return getJson(CONFIG.API.WEATHER, null, CONFIG.UI.TEXT.API_ERRORS.WEATHER);
    }

    estimateRouteCost(route) {
        const breakdown = route?.costBreakdown || {};
        return {
            baseDistance: breakdown.baseDistance || 0,
            trafficPenalty: breakdown.trafficPenalty || 0,
            rainPenalty: breakdown.rainPenalty || 0,
            obstaclePenalty: breakdown.obstaclePenalty || 0,
            totalCost: breakdown.totalCost || 0,
            estimatedMinutes: breakdown.estimatedMinutes || 0
        };
    }
}
