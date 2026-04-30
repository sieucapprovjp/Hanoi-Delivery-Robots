class BackendAPI {

    async getTraffic() {
        const response = await fetch(CONFIG.API.TRAFFIC);

        if (!response.ok) {
            throw new Error(`Traffic request failed: ${response.status}`);
        }

        return response.json();
    }

    async getWeather() {
        const response = await fetch(CONFIG.API.WEATHER);

        if (!response.ok) {
            throw new Error(`Weather request failed: ${response.status}`);
        }

        return response.json();
    }

    async getLocations() {
        const response = await fetch(CONFIG.API.DATA_LOCATIONS);
        if (!response.ok) throw new Error(`Locations request failed: ${response.status}`);
        return response.json();
    }

    async getHubs() {
        const response = await fetch(CONFIG.API.DATA_HUBS);
        if (!response.ok) throw new Error(`Hubs request failed: ${response.status}`);
        return response.json();
    }

    async getRobots() {
        const response = await fetch(CONFIG.API.DATA_ROBOTS);
        if (!response.ok) throw new Error(`Robots request failed: ${response.status}`);
        return response.json();
    }

}
