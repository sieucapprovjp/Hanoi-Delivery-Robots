class EnvironmentManager {
    constructor() {
        this.rain = new RainManager();
        this.traffic = new TrafficManager();
        this.obstacles = new ObstacleManager();
    }

    initialize() {
        this.setupControls();
        this.setupMapClick();

        // Initial data fetch
        this.rain.updateRainList().catch(() => { });
        this.traffic.updateTrafficList().catch(() => { });
        this.obstacles.updateObstacleList().catch(() => { });
        
        console.log('🌍 Environment Manager initialized');
    }

    setupControls() {
        // Rain actions
        document.getElementById('randomize-rain-btn')?.addEventListener('click', () => this.rain.randomizeRain());
        document.getElementById('clear-rain-btn')?.addEventListener('click', () => this.rain.clearRain());

        // Traffic actions
        document.getElementById('reset-traffic-points-btn')?.addEventListener('click', () => this.traffic.resetTrafficPoints());
        document.getElementById('randomize-traffic-btn')?.addEventListener('click', () => this.traffic.randomizeTraffic());
        document.getElementById('clear-traffic-btn')?.addEventListener('click', () => this.traffic.clearTraffic());

        // Obstacle actions
        document.getElementById('randomize-obstacle-btn')?.addEventListener('click', () => this.obstacles.randomizeObstacles());
        document.getElementById('clear-obstacle-btn')?.addEventListener('click', () => this.obstacles.clearObstacles());
    }

    setupMapClick() {
        const setupListener = () => {
            const map = window.map;
            if (map && typeof map.on === 'function') {
                map.on('click', (e) => {
                    const store = Alpine.store('sim');
                    if (!store || !store.panels.weather) return;

                    const mode = store.weather.mode;
                    const lat = e.latlng.lat;
                    const lon = e.latlng.lng;

                    if (mode === CONFIG.UI.WEATHER_MODES.RAIN) {
                        this.rain.addRainZone(lat, lon, +store.weather.rainRadius);
                    } else if (mode === CONFIG.UI.WEATHER_MODES.TRAFFIC) {
                        this.traffic.handleTrafficClick(lat, lon);
                    } else if (mode === 'obstacle') {
                        this.obstacles.addObstacle(lat, lon, +store.weather.obstacleRadius, +store.weather.obstacleSeverity);
                    }
                });
                console.log('📍 Environment map click listener ready');
            } else {
                setTimeout(setupListener, 500);
            }
        };
        setupListener();
    }
}
