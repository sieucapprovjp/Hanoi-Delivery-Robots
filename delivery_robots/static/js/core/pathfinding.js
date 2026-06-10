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

        return getJson(`${CONFIG.API.ROUTE}?${params.toString()}`, null, 'Route request failed');
    }

    async snapToRoad(lat, lon) {
        const params = new URLSearchParams({ lat, lon });
        return getJson(`${CONFIG.API.SNAP}?${params.toString()}`, null, 'Snap request failed');
    }

    async getTraffic() {
        return getJson(CONFIG.API.TRAFFIC, null, 'Traffic request failed');
    }

    async getWeather() {
        return getJson(CONFIG.API.WEATHER, null, 'Weather request failed');
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
