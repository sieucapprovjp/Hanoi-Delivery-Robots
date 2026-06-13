/**
 * Configuration constants for the Delivery Robots project.
 * Centralized store for runtime constants and UI copy.
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
        INITIAL_BATTERY: 100,
        BATTERY_HEALTH_THRESHOLDS: {
            GOOD: 60,
            WARN: 30
        },
        BASE_SPEED_MULTIPLIER: 0.55,
        MIN_SPEED_MULTIPLIER: 0.08,
        TRAFFIC_IMPACT_FACTOR: 0.65,
        BATTERY_DRAIN: 0.0065,
        CAPACITY: 10,
        HISTORY_SIZE_LIMIT: 20,
        BATTERY_LOW_THRESHOLD: 20,
        BATTERY_CHARGE_INCREMENT: 8,
        BATTERY_CHARGE_TARGET: 90,
        CHARGING_INTERVAL_MS: 700,
        REROUTE_INTERVAL_MS: 5500,
        REROUTE_MIN_IMPROVEMENT_RATIO: 0.12,
        REROUTE_BACKTRACK_DISTANCE_METERS: 35,
        TRAFFIC_REROUTE_THRESHOLD: 0.45,
        RAIN_REROUTE_THRESHOLD: 2,
        MEMORY_DECAY: 0.995,
        MEMORY_UPDATE_WEIGHT: 0.7,
        MEMORY_CLEANUP_THRESHOLD: 0.01,
        EXPERIENCE_PENALTIES: {
            heavy: 1.8,
            moderate: 1.3,
            light: 0.95
        },
        EXPERIENCE_THRESHOLDS: {
            heavy: 0.3,
            moderate: 0.6
        },
        BATTERY_PROJECTED_DRAIN_FACTOR: 4.5,
        BATTERY_SAFETY_MARGIN: 0.35,
        CHARGING_ARRIVAL_THRESHOLD: 0.0005,
        METERS_PER_DEGREE: 111000,
        FRAME_COUNT_RECORD_MEMORY: 30,
        FRAME_COUNT_DECAY_MEMORY: 300,
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
            DELIVERY: 'delivery',
            CHARGING: 'charging'
        },
        CALC_TIME_THRESHOLDS: {
            GOOD: 30,
            WARN: 80
        }
    },

    // Simulation Settings
    SIMULATION: {
        DELIVERY_INTERVAL_MS: 6500,
        INITIAL_DELIVERY_COUNT: 6,
        DEFAULT_ALGORITHM: 'astar',
        ALGORITHMS: ['astar', 'dijkstra', 'gbfs'],
        CATEGORIES: {
            RESIDENTIAL: 'residential',
            RESTAURANT: 'restaurant',
            MARKET: 'market',
            OFFICE: 'office',
            RETAIL: 'retail',
            HOTEL: 'hotel',
            LANDMARK: 'landmark'
        },
        INITIAL_ROBOTS: [
            { name: 'Robot 1', color: '#4285f4' },
            { name: 'Robot 2', color: '#34a853' },
            { name: 'Robot 3', color: '#fbbc04' },
            { name: 'Robot 4', color: '#ff6b6b' },
            { name: 'Robot 5', color: '#845ef7' }
        ],
        RANDOM_RAIN_COUNT: 3,
        RANDOM_RAIN_MIN_RADIUS: 100,
        RANDOM_RAIN_MAX_RADIUS: 200,
        RANDOM_TRAFFIC_COUNT: 3,
        DEFAULT_TRAFFIC_SEVERITY: 0.7,
        RANDOM_OBSTACLE_COUNT: 4,
        DEFAULT_OBSTACLE_TYPE: 'roadblock',
        PICKUP_WEIGHTS: {
            restaurant: 0.24,
            market: 0.22,
            retail: 0.18,
            office: 0.14,
            hotel: 0.12,
            landmark: 0.06,
            residential: 0.04
        },
        DROPOFF_WEIGHTS: {
            residential: 0.32,
            hotel: 0.18,
            office: 0.16,
            retail: 0.12,
            restaurant: 0.10,
            landmark: 0.07,
            market: 0.05
        },
        DELIVERY_STATUSES: {
            PENDING: 'pending',
            ASSIGNED: 'assigned',
            COMPLETED: 'completed'
        },
        TIME_DELTA: 0.016,
        EFFICIENCY_WEIGHTS: {
            TIME: 0.02,
            NODES: 0.005,
            REROUTE: 0.5
        },
        BAR_SCALES: {
            THROUGHPUT: 4,
            QUEUE: 6,
            REROUTE: 8,
            ENERGY: 18,
            COST: 40
        }
    },

    // VRP Settings
    VRP: {
        ENABLED: true,
        MAX_ORDERS_PER_ROBOT: 3
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
        ASTEP: '/api/astep',
        INSIDER: '/api/insider',
        LOG_DELIVERY: '/api/log_delivery',
        OPTIMIZE_HUBS: '/api/optimize-hubs',
        DISPATCH_ASSIGN: '/api/dispatch/assign',
        CHARGING_STATIONS: '/api/charging-stations'
    },

    // UI Settings
    UI: {
        METRICS_REFRESH_INTERVAL_MS: 3000,
        COMPUTING_PANEL_REFRESH_INTERVAL_MS: 2000,
        TRAFFIC_REFRESH_INTERVAL_MS: 3500,
        WEATHER_MODES: {
            RAIN: 'rain',
            TRAFFIC: 'traffic',
            OBSTACLE: 'obstacle'
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
            CHARGING: '🔋 Charging',
            REROUTING: '🧠 Rerouting',
            LOW_BATTERY: '⚠️ Low Battery',
            STANDBY: 'standby',
            WAITING_ASSIGNMENT: 'Waiting for a robot assignment...',
            ROUTING_PICKUP: '📦 Routing to pickup location',
            ROUTING_DROPOFF: '🚚 Routing to delivery destination',
            PICKUP: '📦 To Pickup',
            DROPOFF: '🚚 To Dropoff',
            WAITING: 'Waiting...'
        },
        TEXT: {
            EMPTY: {
                NO_ACTIVE_ROUTE: 'Robot has no active route. Wait for it to accept a delivery.',
                NO_ASTAR_STEPS: 'No steps recorded',
                NO_ASTAR_VISUALIZATION_STEPS: 'No steps to visualize',
                NO_DELIVERY: 'No delivery',
                NO_DISPATCH_DECISION: 'No dispatch decision yet.',
                ROUTE_PENDING: 'Waiting for route calculation...',
                ORDERS_DISPATCHED: 'All orders dispatched. Waiting for new orders...'
            },
            LOADING: {
                ASTAR_COMPUTING: '⏳ Computing A*...',
                ASTAR_STEP_RUNNING: '⏳ Running A* step-by-step...',
                INSIDER_COMPARISON_RUNNING: '⏳ Running 4 algorithms...',
                POPUP: 'Loading...'
            },
            LOGS: {
                READY: '✅ Ready',
                INIT_FAILED: '❌ Init failed',
                START_PROMPT: '🚀 Click START to begin!',
                STARTED: '▶ Started!',
                PAUSED: '⏸ Paused',
                RESET: '🔄 Reset',
                OPTIMIZING_HUBS: '🧠 Optimizing hub locations...',
                HUBS_OPTIMIZED: '✅ Hubs optimized!',
                OPTIMIZATION_FAILED: '❌ Optimization failed'
            },
            API_ERRORS: {
                METRICS: 'Metrics request failed',
                CLOCK: 'Clock request failed',
                ASTAR_PROCESS: 'A* process request failed',
                ASTAR_VISUALIZATION: 'A* visualization request failed',
                INSIDER_COMPARISON: 'Insider comparison request failed',
                DISPATCH_ASSIGNMENT: 'Assignment failed',
                HUB_OPTIMIZATION: 'Optimization failed',
                ROUTE: 'Route request failed',
                SNAP: 'Snap request failed',
                TRAFFIC: 'Traffic request failed',
                WEATHER: 'Weather request failed',
                CHARGING_STATIONS: 'Charging stations request failed',
                CHARGING_STATIONS_FALLBACK: 'Failed to load charging stations from API, fallback to static config.',
                CHARGING_STATION_SAVE: 'Failed to save charging station',
                WEATHER_LOAD: 'Weather load failed',
                TRAFFIC_REFRESH: 'Traffic refresh failed'
            },
            XAI: {
                CONSTRAINTS: {
                    idle: 'Idle',
                    batteryOk: 'Battery',
                    capacityOk: 'Capacity',
                    pickupDistanceOk: 'Pickup',
                    batteryReserveOk: 'Reserve',
                    routeEtaOk: 'ETA'
                },
                SCORE_LABELS: {
                    preScore: 'Pre-score',
                    pickup: 'Pickup',
                    route: 'Route',
                    batteryRisk: 'Battery risk',
                    priority: 'Priority',
                    total: 'Total'
                },
                META_LABELS: {
                    battery: 'Battery',
                    load: 'Load',
                    pickup: 'Pickup',
                    selected: 'Selected',
                    priority: 'priority'
                }
            },
            ROBOT: {
                SPEED: 'Speed',
                BATTERY: 'Battery',
                DRAIN: 'Drain',
                COMPLETED: 'Completed',
                DISTANCE: 'Distance',
                WAYPOINTS_LEFT: 'waypoints left',
                ACTIVE_ORDERS: 'Active orders',
                NEXT_STOP: 'Next',
                STOPS_PROGRESS: 'Stops',
                GOING_PICKUP: '🔵 Going to pickup',
                GOING_DELIVER: '🔴 Going to deliver',
                ROUTE_BREAKDOWN_TITLE: '🧠 A* Route Cost Breakdown',
                BASE_DISTANCE: '📏 Base Distance:',
                TRAFFIC_PENALTY: '🚗 Traffic Penalty:',
                RAIN_PENALTY: '🌧️ Rain Penalty:',
                OBSTACLE_PENALTY: '🚧 Obstacle Penalty:',
                TOTAL_COST: '🎯 Total Cost:',
                SIM_ETA: '⏱ Sim ETA:',
                COMPUTING_ENGINE: 'Computing Engine',
                STATE: 'State:',
                CALC_HISTORY: '📊 Calculation History',
                LIFETIME_PERFORMANCE: '📈 Lifetime Performance',
                DELIVERIES: 'Deliveries',
                CALCULATIONS: 'Calculations',
                SHOW_ASTAR_PROCESS: '🔬 Show Full A* Calculation Process'
            },
            TABLE: {
                ALGORITHM: 'Algorithm',
                DONE: 'Done',
                TIME: 'Time',
                NODES: 'Nodes',
                COST: 'Cost',
                REROUTES: 'Reroutes',
                EFFICIENCY: 'Eff.',
                PATH: 'Path',
                OPTIMAL: 'Optimal?'
            },
            INSIDER: {
                ASTAR_STEP_TITLE: '🔬 A* Step-by-Step Calculation',
                ASTAR_EXPANSION_TITLE: '🔬 A* Expansion',
                GOAL_REACHED: '✅ Goal Reached!',
                PATH_RECONSTRUCTED: 'Path reconstructed:',
                PENALTIES_APPLIED: '⚙️ Penalties Applied:',
                KEY_INSIGHT: '💡 Key Insight:',
                MAP_LEGEND: 'Blue markers show exploration order on the map, orange shows the latest expanded node, green is the start, red is the goal, and purple is the final chosen path.'
            },
            ENVIRONMENT: {
                RADIUS: 'Radius:',
                SEVERITY: 'Severity:',
                SEVERITY_SHORT: 'Sev:',
                NO_RAIN_ZONES: 'No rain zones',
                NO_TRAFFIC_ROUTES: 'No traffic routes',
                NO_OBSTACLES: 'No obstacles',
                TRAFFIC_START_POPUP: '<strong>Traffic start</strong><br>Click another point to set the end.',
                LOG_TRAFFIC_RESET: '🔄 Traffic points reset',
                LOG_TRAFFIC_START: '🚗 Traffic start set',
                LOG_RANDOM_RAIN: '🎲 Rain',
                LOG_CLEAR_RAIN: '🗑️ Rain',
                LOG_RANDOM_TRAFFIC: '🎲 Traffic',
                LOG_CLEAR_TRAFFIC: '🗑️ Traffic',
                LOG_RANDOM_OBSTACLES: '🎲 Obstacles',
                LOG_CLEAR_OBSTACLES: '🗑️ Obstacles',
                ERROR_RAIN_ADD: 'Rain add failed',
                ERROR_RAIN_LIST: 'Rain list request failed',
                ERROR_TRAFFIC_ADD: 'Traffic add failed',
                ERROR_TRAFFIC_LIST: 'Traffic list request failed',
                ERROR_TRAFFIC_RANDOMIZE: 'Traffic randomize failed',
                ERROR_OBSTACLE_ADD: 'Obstacle add failed',
                ERROR_OBSTACLE_LIST: 'Obstacle list request failed',
                ERROR_OBSTACLE_RANDOMIZE: 'Obstacle randomize failed'
            }
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

    // Predefined Data
    DATA: {
        STREETS: [
            { name: "Phố Lê Thái Tổ", points: [[21.0240, 105.8480], [21.0250, 105.8486], [21.0260, 105.8492], [21.0270, 105.8498], [21.0280, 105.8504], [21.0290, 105.8509], [21.0300, 105.8513]], type: "main" },
            { name: "Phố Đinh Tiên Hoàng", points: [[21.0300, 105.8513], [21.0310, 105.8517], [21.0320, 105.8521], [21.0330, 105.8525], [21.0340, 105.8529], [21.0355, 105.8532]], type: "main" },
            { name: "Phố Tràng Tiền", points: [[21.0240, 105.8480], [21.0243, 105.8492], [21.0247, 105.8505], [21.0252, 105.8518], [21.0256, 105.8530]], type: "main" },
            { name: "Phố Hàng Khay", points: [[21.0256, 105.8530], [21.0262, 105.8534], [21.0270, 105.8538], [21.0278, 105.8543], [21.0285, 105.8548]], type: "main" },
            { name: "Phố Hai Bà Trưng", points: [[21.0220, 105.8510], [21.0240, 105.8515], [21.0260, 105.8520], [21.0280, 105.8525], [21.0300, 105.8530]], type: "main" },
            { name: "Phố Lý Thường Kiệt", points: [[21.0210, 105.8500], [21.0230, 105.8505], [21.0250, 105.8510], [21.0270, 105.8515], [21.0290, 105.8520]], type: "main" },
            { name: "Phố Hàng Đào", points: [[21.0300, 105.8530], [21.0310, 105.8528], [21.0320, 105.8526], [21.0330, 105.8524], [21.0340, 105.8522], [21.0350, 105.8520]], type: "secondary" },
            { name: "Phố Hàng Ngang", points: [[21.0305, 105.8538], [21.0315, 105.8536], [21.0325, 105.8534], [21.0335, 105.8532], [21.0345, 105.8530]], type: "secondary" },
            { name: "Phố Đồng Xuân", points: [[21.0345, 105.8530], [21.0350, 105.8525], [21.0353, 105.8519], [21.0355, 105.8516]], type: "secondary" },
            { name: "Phố Bà Triệu", points: [[21.0220, 105.8510], [21.0230, 105.8513], [21.0240, 105.8515], [21.0250, 105.8517], [21.0260, 105.8520]], type: "secondary" }
        ],
        INTERSECTIONS: [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Lake", connections: [0, 1, 3] },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien", connections: [1, 2] },
            { lat: 21.0265, lon: 105.8505, name: "Hang Bai", connections: [2] },
            { lat: 21.0275, lon: 105.8520, name: "Dinh Tien Hoang", connections: [0] }
        ],
        CHARGING_STATIONS: [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Hub", spots: 3 },
            { lat: 21.0355, lon: 105.8516, name: "Dong Xuan", spots: 2 },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien", spots: 2 },
            { lat: 21.0220, lon: 105.8510, name: "Ly Thuong Kiet", spots: 2 },
            { lat: 21.0300, lon: 105.8530, name: "Hang Ngang", spots: 2 },
            { lat: 21.0275, lon: 105.8520, name: "Opera House", spots: 2 }
        ],
        OBSTACLE_COLORS: {
            roadblock: '#ff6b6b',
            construction: '#ffa94d',
            accident: '#ffd43b'
        },
        LOCATIONS: [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Lake", category: "landmark", icon: "📍" },
            { lat: 21.0355, lon: 105.8516, name: "Dong Xuan Market", category: "market", icon: "🛍" },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien Plaza", category: "retail", icon: "🛒" },
            { lat: 21.0275, lon: 105.8520, name: "Opera House", category: "office", icon: "🏛" },
            { lat: 21.0220, lon: 105.8510, name: "Ly Thuong Kiet Residences", category: "residential", icon: "🏠" },
            { lat: 21.0300, lon: 105.8530, name: "Hang Ngang Shops", category: "retail", icon: "🛍" },
            { lat: 21.0318, lon: 105.8524, name: "Ngoc Son Gate", category: "landmark", icon: "📍" },
            { lat: 21.0334, lon: 105.8509, name: "Ta Hien Bistro Row", category: "restaurant", icon: "🍜" },
            { lat: 21.0268, lon: 105.8496, name: "Hang Trong Studios", category: "office", icon: "🏢" },
            { lat: 21.0235, lon: 105.8504, name: "Melia Hanoi", category: "hotel", icon: "🏨" },
            { lat: 21.0294, lon: 105.8555, name: "Water Puppet Theatre", category: "landmark", icon: "🎭" },
            { lat: 21.0248, lon: 105.8528, name: "French Quarter Cafe", category: "restaurant", icon: "☕" },
            { lat: 21.0271, lon: 105.8558, name: "Post Office Square", category: "office", icon: "🏢" },
            { lat: 21.0343, lon: 105.8522, name: "Hang Dao Market", category: "market", icon: "🛍" },
            { lat: 21.0218, lon: 105.8499, name: "Thong Nhat Apartments", category: "residential", icon: "🏠" },
            { lat: 21.0298, lon: 105.8515, name: "Pho Cau Go Dining", category: "restaurant", icon: "🍲" },
            { lat: 21.0257, lon: 105.8544, name: "Ba Kieu Temple", category: "landmark", icon: "⛩" },
            { lat: 21.0326, lon: 105.8517, name: "Old Quarter Hostel", category: "hotel", icon: "🛎" },
            { lat: 21.0261, lon: 105.8517, name: "Press Club Offices", category: "office", icon: "🏢" },
            { lat: 21.0230, lon: 105.8522, name: "Tran Hung Dao Homes", category: "residential", icon: "🏡" }
        ]
    }
};
