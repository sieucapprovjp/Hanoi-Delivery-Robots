"""
Centralized configuration constants for the delivery_robots project.
All magic numbers, default values, and static literals are consolidated here for maintainability.
Organized by domain.
"""

# ── Graph Construction (OSMnx) ──
GRAPH_CENTER = (21.0285, 105.8542)
GRAPH_DIST_METERS = 2200
GRAPH_NETWORK_TYPE = "bike"

# ── Simulation Time ──
SIMULATION_SPEED = 30
SIMULATION_START_OFFSET_SECONDS = 21600  # 6:00 AM expressed as seconds from midnight
SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60

# ── Rush Hour ──
RUSH_HOURS = [
    {"name": "Morning Rush", "start": 7, "end": 9, "multiplier": 2.5},
    {"name": "Lunch Traffic", "start": 11, "end": 13, "multiplier": 1.3},
    {"name": "Evening Rush", "start": 17, "end": 19, "multiplier": 3.0},
]
DEFAULT_RUSH_HOUR_MULTIPLIER = 1.0
DEFAULT_RUSH_HOUR_LABEL = "Normal"
RUSH_HOUR_INACTIVE_LABEL = "Normal"

# ── Traffic ──
TRAFFIC_ANCHORS = []
TRAFFIC_PERIOD_SECONDS = 36
DEFAULT_TRAFFIC_PENALTY = 1.0
TRAFFIC_ACTIVE_SEGMENT_THRESHOLD = 0.9
TRAFFIC_INFLUENCE_RADIUS_METERS = 24
TRAFFIC_MIN_SEGMENT_STRENGTH = 0.35
TRAFFIC_SEVERITY_SCALING_FACTOR = 3.2
TRAFFIC_SEGMENT_STRENGTH_THRESHOLD = 0.15
TRAFFIC_ROUTE_NAME_PREFIX = "Traffic "
DEFAULT_TRAFFIC_SEVERITY = 0.7
TRAFFIC_SEVERITY_CLAMP_MIN = 0.0
TRAFFIC_SEVERITY_CLAMP_MAX = 1.0
DEFAULT_RANDOMIZE_TRAFFIC_COUNT = 3
RANDOM_TRAFFIC_SEVERITY_MIN = 0.4
RANDOM_TRAFFIC_SEVERITY_MAX = 0.9
RANDOM_TRAFFIC_LAT_MIN = 21.0200
RANDOM_TRAFFIC_LAT_MAX = 21.0350
RANDOM_TRAFFIC_LON_MIN = 105.8450
RANDOM_TRAFFIC_LON_MAX = 105.8600
RANDOM_TRAFFIC_PATH_POINT_COUNT = 10

# ── Weather / Rain ──
RAIN_ZONES_INITIAL = []
DEFAULT_RAIN_PENALTY = 1.0
DEFAULT_RAIN_SEVERITY = 1.0
DEFAULT_WEATHER_RAIN_SEVERITY = 1.0
RAIN_ZONE_NAME_PREFIX = "Rain "
DEFAULT_RAIN_RADIUS = 150
DEFAULT_RANDOMIZE_RAIN_COUNT = 3
DEFAULT_RAIN_MIN_RADIUS = 100
DEFAULT_RAIN_MAX_RADIUS = 200

# ── Obstacles ──
DEFAULT_OBSTACLE_PENALTY = 1.0
DEFAULT_OBSTACLE_SEVERITY = 10.0
OBSTACLE_SEVERITY_DIVISOR = 10.0
OBSTACLE_MIN_CLOSENESS_FACTOR = 0.2
OBSTACLE_NAME_PREFIX = "Obstacle "
OBSTACLE_RANDOMIZE_NAME_PREFIX = "Obs "
DEFAULT_OBSTACLE_RADIUS = 80
DEFAULT_OBSTACLE_TYPE = "roadblock"
DEFAULT_RANDOMIZE_OBSTACLE_COUNT = 3
OBSTACLE_TYPES = ["roadblock", "construction", "accident"]
RANDOM_OBSTACLE_RADIUS_MIN = 50
RANDOM_OBSTACLE_RADIUS_MAX = 120
RANDOM_OBSTACLE_SEVERITY_MIN = 5
RANDOM_OBSTACLE_SEVERITY_MAX = 50

# ── Routing ──
DEFAULT_EDGE_LENGTH = 0.0
DEFAULT_ROUTE_DISTANCE = 0.0
SPEED_METERS_PER_SECOND = 2

# ── Hub Optimization ──
DEFAULT_HUB_CLUSTER_COUNT = 5
MIN_DELIVERY_HISTORY_POINTS = 5
MIN_DELIVERY_HISTORY_ERROR_MSG = (
    "Not enough delivery data to optimize hubs. Need at least "
    + str(MIN_DELIVERY_HISTORY_POINTS)
    + " points."
)
KMEANS_RANDOM_STATE = 42
KMEANS_N_INIT = "auto"
HUB_NAME_PREFIX = "AI Hub "
HUB_NAME_ASCII_OFFSET = 65  # ASCII code for 'A'

# ── Geography / Geodesy ──
EARTH_RADIUS_METERS = 6371009
METERS_PER_DEGREE_LATITUDE = 111320
RANDOM_LAT_MIN = 21.0180
RANDOM_LAT_MAX = 21.0380
RANDOM_LON_MIN = 105.8430
RANDOM_LON_MAX = 105.8650

# ── Validation ──
LATITUDE_MIN = -90
LATITUDE_MAX = 90
LATITUDE_ERROR_MSG = "Latitude must be between -90 and 90"
LONGITUDE_MIN = -180
LONGITUDE_MAX = 180
LONGITUDE_ERROR_MSG = "Longitude must be between -180 and 180"

# ── Metrics ──
METRICS_INITIAL_MIN_CALC_TIME = 999
METRICS_PATH_LENGTHS_MAX_SIZE = 100

# ── API / Logs ──
API_LOGS_MAX_LENGTH = 500
TIMESTAMP_MS_MULTIPLIER = 1000
DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_SOURCE = "frontend"
DEFAULT_LOGS_LIMIT = 200
LOGS_LIMIT_MIN = 1
LOGS_LIMIT_MAX = 1000

# ── Robot Statuses ──
ROBOT_STATUS_IDLE = "idle"
ROBOT_STATUS_MOVING_TO_PICKUP = "moving_to_pickup"
ROBOT_STATUS_MOVING_TO_DROPOFF = "moving_to_dropoff"
ROBOT_STATUS_MOVING_TO_CHARGE = "moving_to_charge"
ROBOT_STATUS_CHARGING = "charging"

# ── Battery & Charging ──
BATTERY_MAX = 100.0  # Maximum battery percentage (b_max)
BATTERY_LOW = 30.0  # Threshold below which robot goes to charge after completing current order (b_low)
BATTERY_PROACTIVE = (
    50.0  # Threshold below which idle robot goes to charge proactively (b_proactive)
)
CHARGING_RATE_PERCENT_PER_MINUTE = 5.0  # Rate at which battery charges (r_charge)
BATTERY_DRAIN_RATE = (
    1.0 / 60.0
)  # Base battery consumption rate per physical travel second (r_drain)
BATTERY_SAFETY_MARGIN = 10.0  # Safety buffer percentage for dynamic safety-aware charging check (B_safety_margin)

# ── Charging Station Selection ──
W1_TRAVEL_COST_WEIGHT = (
    1.0  # Weight for physical/dynamic travel cost to charging hub (w1)
)
W2_WAIT_TIME_WEIGHT = 1.0  # Weight for estimated waiting time at charging hub (w2)

# ── Dispatching Weights (Weighted Cost Assignment) ──
DISPATCH_ALPHA = 1.0  # Weight for travel distance/cost to pickup point (alpha)
DISPATCH_BETA = 1.0  # Weight for distance/cost from pickup to delivery point (beta)
DISPATCH_GAMMA = 100.0  # Weight for battery penalty (gamma)
DISPATCH_LAMBDA = 0.05  # Exponential coefficient in battery penalty function f(B) = e^(-lambda * B) (lambda)
DEFAULT_DISPATCH_MODEL = "nearest_idle"  # Default dispatch model identifier

# ── Re-dispatching & Re-assignment ──
REPLANNING_THRESHOLD = 15.0  # Allowable gap threshold before triggering replanning
REASSIGN_PENALTY = 60.0  # Penalty weight to prevent chattering/oscillating order re-assignments (penalty_reassign)
MAX_REASSIGN_LIMIT = (
    2  # Maximum number of times an order can be reassigned (N_max_reassign)
)
REASSIGN_COOLDOWN = (
    60  # Cooldown time in simulation seconds between re-assignments (T_cooldown)
)

# ── Order Statuses & Expiry ──
ORDER_EXPIRY_TIMEOUT = (
    300  # Order waiting queue expiration timeout in simulation seconds (T_expire)
)
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_ASSIGNED = "assigned"
ORDER_STATUS_IN_TRANSIT = "in_transit"
ORDER_STATUS_DELIVERED = "delivered"
ORDER_STATUS_EXPIRED = "expired"

# ── Query Difficulty Stratification ──
DIFFICULTY_SHORT_MAX_METERS = 500.0
DIFFICULTY_MEDIUM_MAX_METERS = 2000.0
DIFFICULTY_ONE_WAY_THRESHOLD = 0.2

# ── Neighbor Ordering ──
NEIGHBOR_ORDERING_POLICY = "id"  # Default neighbor ordering policy
