class Pathfinding {
    async getRoute(startLat, startLon, endLat, endLon, roadMemory = {}) {
        const params = new URLSearchParams({
            fromLat: startLat,
            fromLon: startLon,
            toLat: endLat,
            toLon: endLon,
            memory: JSON.stringify(roadMemory)
        });

        const response = await fetch(`/api/route?${params.toString()}`);
        if (!response.ok) {
            throw new Error(`Route request failed: ${response.status}`);
        }

        return response.json();
    }

    async snapToRoad(lat, lon) {
        const params = new URLSearchParams({ lat, lon });
        const response = await fetch(`/api/snap?${params.toString()}`);

        if (!response.ok) {
            throw new Error(`Snap request failed: ${response.status}`);
        }

        return response.json();
    }

    async getTraffic() {
        const response = await fetch('/api/traffic');

        if (!response.ok) {
            throw new Error(`Traffic request failed: ${response.status}`);
        }

        return response.json();
    }

    async getWeather() {
        const response = await fetch('/api/weather');

        if (!response.ok) {
            throw new Error(`Weather request failed: ${response.status}`);
        }

        return response.json();
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
