/**
 * Configuration constants for the Delivery Robots project.
 * Centralized store for hardcoded values to improve maintainability.
 */
const CONFIG = {
    // Map Settings
    MAP: {
        INITIAL_VIEW: [21.0285, 105.8542],
        INITIAL_ZOOM: 16,
        MAX_ZOOM: 19,
        TILE_LAYER_URL: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        ATTRIBUTION: '© OpenStreetMap',
        RAIN_COLORS: {
            halo: '#4dabf7',
            core: '#228be6',
            fill: '#74c0fc'
        },
        TRAFFIC_COLORS: {
            heavy: '#ff6b6b',
            moderate: '#ff922b'
        },
        RAIN_ZONES_CORE_SCALE: 0.62
    },

    // Robot Settings
    ROBOT: {
        COLORS: {
            error: '#ea4335',
            info: '#1a73e8'
        },
        STATUSES: {
            IDLE: 'idle',
            MOVING: 'moving',
            MOVING_TO_PICKUP: 'moving_to_pickup',
            MOVING_TO_DROPOFF: 'moving_to_dropoff',
            MOVING_TO_CHARGE: 'moving_to_charge',
            CHARGING: 'charging'
        },
        PHASES: {
            TO_PICKUP: 'to_pickup',
            TO_DROPOFF: 'to_dropoff'
        }
    },

    // Simulation Settings
    SIMULATION: {
        RANDOM_RAIN_COUNT: 3,
        RANDOM_RAIN_MIN_RADIUS: 100,
        RANDOM_RAIN_MAX_RADIUS: 200,
        RANDOM_TRAFFIC_COUNT: 3,
        DEFAULT_TRAFFIC_SEVERITY: 0.7,
        RANDOM_OBSTACLE_COUNT: 4,
        DEFAULT_OBSTACLE_TYPE: 'roadblock'
    },

    // API Endpoints
    API: {
        LOGS: '/api/logs',
        TRAFFIC: '/api/traffic',
        TRAFFIC_ADD: '/api/traffic/add',
        TRAFFIC_LIST: '/api/traffic/list',
        TRAFFIC_CLEAR: '/api/traffic/clear',
        TRAFFIC_RANDOMIZE: '/api/traffic/randomize',
        WEATHER: '/api/weather',
        RAIN_ADD: '/api/rain/add',
        RAIN_LIST: '/api/rain/list',
        RAIN_CLEAR: '/api/rain/clear',
        RAIN_RANDOMIZE: '/api/rain/randomize',
        OBSTACLE_ADD: '/api/obstacle/add',
        OBSTACLE_LIST: '/api/obstacle/list',
        OBSTACLE_CLEAR: '/api/obstacle/clear',
        OBSTACLE_RANDOMIZE: '/api/obstacle/randomize',
        METRICS: '/api/metrics',
        ORDERS: '/api/orders',
        DATA_LOCATIONS: '/api/data/locations',
        DATA_HUBS: '/api/data/hubs',
        DATA_ROBOTS: '/api/data/robots'
    },

    // UI Settings
    UI: {
        METRICS_REFRESH_INTERVAL_MS: 3000,
        TRAFFIC_REFRESH_INTERVAL_MS: 3500,
        WEATHER_MODES: {
            RAIN: 'rain',
            TRAFFIC: 'traffic'
        },
        LOG_LEVELS: {
            INFO: 'info',
            NEUTRAL: 'neutral'
        },
        STATE_LABELS: {
            IDLE: '⏸ Idle',
            MOVING: '🔄 Moving',
            ROUTING_PICKUP: '📦 Routing to pickup location',
            ROUTING_DROPOFF: '🚚 Routing to delivery destination',
            ROUTING_CHARGE: '⚡ Routing to charging station',
            CHARGING: '🔋 Charging'
        },
        LOG_SOURCES: {
            UI: 'ui',
            DISPATCH: 'dispatch'
        },
        RADII: {
            markerLarge: 7
        },
        OPACITY: {
            medium: 0.3,
            high: 0.7
        },
        WEIGHTS: {
            medium: 3,
            thick: 5
        },
        DASH_ARRAY: '8, 8'
    },

    // UI Colors and Helpers
    OBSTACLE_COLORS: {
        roadblock: '#ff6b6b',
        construction: '#ffa94d',
        accident: '#ffd43b'
    }
};
