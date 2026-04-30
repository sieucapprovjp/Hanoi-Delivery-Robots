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
        STREET_COLORS: {
            main: '#ffa94d',
            secondary: '#ffd43b',
            residential: '#e9ecef'
        },
        RAIN_COLORS: {
            halo: '#4dabf7',
            core: '#228be6',
            fill: '#74c0fc'
        },
        TRAFFIC_COLORS: {
            heavy: '#ff6b6b',
            moderate: '#ff922b'
        },
        TRAFFIC_RADIUS: 26,
        TRAFFIC_PENALTY_MULTIPLIER: 2,
        ROADBLOCK_DISTANCE_THRESHOLD: 35,
        HUB_COLOR: '#1a73e8',
        HUB_RING_RADIUS: 90,
        HUB_RING_WEIGHT: 2,
        HUB_RING_OPACITY: 0.5,
        HUB_FILL_OPACITY: 0.08,
        RAIN_ZONES_CORE_SCALE: 0.62,
        EARTH_RADIUS_METERS: 6371e3,
        METERS_PER_DEGREE: 111320
    },

    // Robot Settings
    ROBOT: {
        DEFAULT_SPEED: 0.000010,
        COLORS: {
            good: '#34a853',
            warn: '#fbbc04',
            error: '#ea4335',
            info: '#1a73e8',
            neutral: '#9e9e9e',
            highlight: '#ff9800'
        },
        STATUSES: {
            IDLE: 'idle',
            MOVING: 'moving',
            CHARGING: 'charging'
        },
        PHASES: {
            IDLE: 'idle',
            TO_PICKUP: 'to_pickup',
            TO_DROPOFF: 'to_dropoff'
        },
        ROUTE_MODES: {
            DELIVERY: 'delivery'
        },
        CALC_TIME_THRESHOLDS: {
            GOOD: 30,
            WARN: 80
        }
    },

    // Simulation Settings
    SIMULATION: {
        CATEGORIES: {
            RESIDENTIAL: 'residential',
            RESTAURANT: 'restaurant',
            MARKET: 'market',
            OFFICE: 'office',
            RETAIL: 'retail',
            HOTEL: 'hotel',
            LANDMARK: 'landmark'
        },
        INITIAL_ROBOTS: [], // Will be fetched from backend
        RANDOM_RAIN_COUNT: 3,
        RANDOM_RAIN_MIN_RADIUS: 100,
        RANDOM_RAIN_MAX_RADIUS: 200,
        RANDOM_TRAFFIC_COUNT: 3,
        DEFAULT_TRAFFIC_SEVERITY: 0.7,
        RANDOM_OBSTACLE_COUNT: 4,
        DEFAULT_OBSTACLE_TYPE: 'roadblock',
        TIME_DELTA: 0.016
    },

    // API Endpoints
    API: {
        LOGS: '/api/logs',
        ROUTE: '/api/route',
        SNAP: '/api/snap',
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
        CLOCK: '/api/clock',
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
        INITIAL_WEATHER: 'rain',
        LOG_LEVELS: {
            INFO: 'info',
            SUCCESS: 'good',
            WARN: 'warn',
            ERROR: 'error',
            NEUTRAL: 'neutral'
        },
        STATE_LABELS: {
            IDLE: '⏸ Idle',
            MOVING: '🔄 Moving',
            STANDBY: 'standby',
            WAITING_ASSIGNMENT: 'Waiting for a robot assignment...',
            ROUTING_PICKUP: '📦 Routing to pickup location',
            ROUTING_DROPOFF: '🚚 Routing to delivery destination',
            PICKUP: '📦 To Pickup',
            DROPOFF: '🚚 To Dropoff',
            WAITING: 'Waiting...'
        },
        LOG_SOURCES: {
            UI: 'ui',
            DISPATCH: 'dispatch'
        },
        GRADIENTS: {
            info: 'linear-gradient(135deg,#e3f2fd,#bbdefb)',
            purple: 'linear-gradient(135deg,#ede7f6,#d1c4e9)',
            success: 'linear-gradient(135deg,#e8f5e9,#c8e6c9)',
            expansion: 'linear-gradient(90deg,#4285f4,#ff9800)',
            surface: 'linear-gradient(135deg,#f8f9fa,#e8eaed)'
        },
        COLORS: {
            text: '#3c4043',
            textLight: '#5f6368',
            border: '#e0e0e0',
            background: '#f8f9fa',
            surface: '#ffffff',
            primary: '#1a73e8',
            secondary: '#9c27b0',
            accent: '#ff9800',
            success: '#34a853',
            error: '#ea4335',
            link: '#1a73e8',
            highlight: '#90caf9',
            rainBg: '#e3f2fd',
            trafficBg: '#fce4ec',
            obstacleBg: '#fff3e0',
            infoBorder: '#bbdefb',
            successLight: '#e8f5e9',
            errorLight: '#fce4ec',
            warnLight: '#fff8e1',
            surfaceLight: '#f8f9fa',
            purpleDark: '#7b1fa2',
            purpleLight: '#f3e5f5',
            transparent: 'transparent'
        },
        RADII: {
            markerSmall: 4,
            markerMedium: 5,
            markerLarge: 7
        },
        OPACITY: {
            low: 0.2,
            medium: 0.3,
            high: 0.7,
            full: 1.0,
            overlay: 0.85
        },
        WEIGHTS: {
            thin: 1,
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
