# 🤖 AI Delivery Robots - Suburban Hanoi Simulation

An interactive AI-powered delivery robot simulation set in Hoan Kiem District, Hanoi. Features autonomous delivery robots with **A* pathfinding**, **dynamic weather/obstacle avoidance**, **multi-algorithm scheduling**, and **real-time decision analytics**.

---

## ✨ Key Features

### 🗺️ Real Map Integration
- **OpenStreetMap Data**: Real road network from Hoan Kiem District (1096 nodes, 2441 edges)
- **Optimized Loading**: Bounding box loading (2.2km → Hoan Kiem boundaries only) saves 40-60% resources
- **Accurate Coordinates**: Real lat/lon coordinates with Haversine distance calculations

### 🧠 AI Pathfinding (A* Algorithm)
- **Dynamic Weighting**: `f(n) = g(n) + h(n)` with real-time penalties
  - 🌧️ Rain zones: **2× slower**
  - 🚗 Traffic congestion: **1.5×-4× slower**
  - 🚧 Obstacles: **5×-50×** (forces complete avoidance)
- **Real-Time Rerouting**: Robots recalculate paths when conditions change
- **Performance Tracking**: Metrics for calculation time, nodes explored, path length

### 🌦️ Dynamic Environment
- **Rain Zones** (🌧️): Place anywhere on map, adjustable radius (50-300m), randomize button
- **Traffic Routes** (🚗): Click two points to create congestion, adjustable severity (0-1)
- **Obstacles** (🚧): Roadblocks, construction, accidents with high penalty zones
- **All zones update routes instantly** - robots avoid bad areas automatically

### 📦 Delivery Scheduling Algorithms
Compare three algorithms in real-time:
- **FIFO** (First-Come-First-Serve): Fair but inefficient
- **Priority**: Smart scoring based on wait time, pickup type, distance
- **Nearest-First**: Minimizes travel distance, fastest completion
- **Live comparison panel** shows deliveries completed & total distance per algorithm

### 🤖 Autonomous Robots
- **5 Robots** with unique identities, colors, and battery management
- **Smart Charging**: Automatically return to charging when battery < 20%
- **Detailed Click Info**: Click any robot to see:
  - 🎯 Current destination & waypoints remaining
  - 🔋 Battery level with color-coded bar & projected drain
  - ⚡ Speed multiplier (affected by weather/traffic)
  - 🧠 Decision breakdown (base distance + traffic/rain penalties)
  - 📊 Total deliveries & distance traveled

### 📊 AI Decision Analytics Panel
Real-time metrics dashboard showing:
- A* calculation speed (avg, min, max, last)
- Nodes explored per search
- Graph statistics (nodes, edges)
- Active environment factors count
- Auto-refreshes every 3 seconds

---

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip

### Installation

```bash
cd delivery_robots
pip install -r requirements.txt
```

### Running

```bash
# Use project virtual environment for best performance
.venv\Scripts\python.exe main.py

# Or directly
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🎮 How to Use

### Basic Simulation
1. Click **▶ Start** to begin
2. Robots automatically accept and deliver packages
3. Adjust speed with slider (1x-10x)
4. Watch real-time stats in side panels

### Weather & Traffic Controls
1. Click **🌧️** FAB button (bottom right)
2. Switch between tabs: Rain / Traffic / Obstacles
3. **Click on map** to place zones manually
4. Use **🎲 Randomize** for instant chaos
5. Use **🗑️ Clear** to remove all zones

### Scheduling Algorithm
1. Open weather panel (🌧️)
2. Scroll to bottom
3. Click **Priority / FIFO / Nearest** to switch
4. Watch comparison panel update in real-time

### Robot Inspection
1. **Click any robot** on the map
2. See detailed popup with:
   - Destination & phase (pickup vs delivery)
   - Battery level & projected drain
   - Speed affected by conditions
   - Decision breakdown showing A* cost calculation

### AI Analytics
1. Click **🔍** FAB button
2. View A* performance metrics
3. See how fast robots make decisions
4. Monitor active environment factors

---

## 🔌 API Endpoints

### Routing
- `GET /api/route?fromLat=&fromLon=&toLat=&toLon=` - Get optimal A* path
- `GET /api/snap?lat=&lon=` - Snap coordinate to nearest road node

### Environment
- `POST /api/rain/add` - Add rain zone at coordinates
- `POST /api/rain/randomize` - Generate random rain zones
- `POST /api/rain/clear` - Remove all rain zones
- `POST /api/traffic/add` - Add traffic congestion route
- `POST /api/traffic/randomize` - Generate random traffic
- `POST /api/traffic/clear` - Remove all traffic
- `POST /api/obstacle/add` - Add obstacle (roadblock/construction/accident)
- `POST /api/obstacle/randomize` - Generate random obstacles
- `POST /api/obstacle/clear` - Remove all obstacles

### Metrics & Status
- `GET /api/metrics` - A* pathfinding performance metrics
- `GET /api/weather` - Current rain zones & district bounds
- `GET /api/traffic` - Active traffic routes with animation data
- `GET /api/rain/list` - List rain zones
- `GET /api/traffic/list` - List traffic routes
- `GET /api/obstacle/list` - List obstacles

---

## 🏗️ Project Structure

```
delivery_robots/
├── app.py                      # Flask server + all API endpoints
├── requirements.txt            # Python dependencies
├── templates/
│   ├── index.html              # Main application (robots + controls)
│   ├── main_map.html           # Standalone map with weather controls
│   └── rain_control.html       # Dedicated rain zone control page
└── static/
    ├── css/
    │   └── style.css           # Full UI styling
    └── js/
        ├── app.js               # Main app + weather controls
        ├── simulation.js        # Simulation engine + scheduling algorithms
        ├── robot.js             # Robot class with detailed popup
        ├── map.js               # Leaflet map + OSM integration
        └── pathfinding.js       # A* pathfinding client
```

---

## 🔬 Technical Details

### A* Pathfinding
- **Graph Source**: OpenStreetMap via OSMnx library
- **Heuristic**: Haversine distance (great-circle distance on sphere)
- **Edge Weights**: `length × traffic_penalty × rain_penalty × obstacle_penalty`
- **Metrics Tracking**: Calculation time, nodes explored, path length
- **Dynamic Updates**: Weights recalculated each request based on live conditions

### Scheduling Algorithms
- **FIFO**: `sort by timestamp` - fair queue order
- **Priority**: `score = wait_time × pickup_weight + distance_factor`
- **Nearest**: `sort by avg haversine distance to all robots`
- **Statistics**: Per-algorithm delivery count and total distance tracked

### Environment Simulation
- **Rain Zones**: Circular zones with 2× speed penalty
- **Traffic Routes**: Line segments with moving congestion wave (36s cycle)
- **Obstacles**: High-penalty zones (5-50×) forcing complete avoidance
- **Thread Safety**: All dynamic zones use locks for concurrent access

### Performance Optimizations
- **Bounding Box Loading**: Only loads Hoan Kiem district (not circular 2.2km radius)
- **Graph Caching**: Road graph loaded once and reused
- **Efficient Lookups**: Nearest node by haversine pre-calculation
- **Auto-Refresh**: Metrics panel updates every 3s only when visible

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Graph Nodes | 1,096 |
| Graph Edges | 2,441 |
| Avg A* Time | < 50ms |
| Avg Nodes Explored | ~200-400 |
| Avg Path Length | ~30-50 waypoints |
| Active Robots | 5 |
| Delivery Interval | 6.5s |

---

## 🎓 Academic Value

This project demonstrates:
- **Classical AI**: A* search with dynamic edge weights
- **Multi-Agent Systems**: Independent robots with shared environment
- **Algorithm Comparison**: FIFO vs Priority vs Nearest scheduling
- **Reactive AI**: Real-time rerouting based on environment changes
- **Constraint Handling**: Battery management, capacity limits, charging behavior
- **Real-World Data**: OpenStreetMap integration with actual Hanoi roads

Perfect for midterm demonstrations showing:
1. Robots avoiding rain zones you place
2. Robots rerouting around obstacles in real-time
3. Algorithm comparison (Priority beats FIFO in delivery count)
4. A* decision breakdown showing exact cost calculation

---

## 🛠️ Dependencies

```
flask==3.0.0
osmnx==2.1.0
networkx==3.6.1
```

---

## 📝 License

MIT License - Feel free to use and modify!

---

## 👨‍💻 Author

Built with ❤️ for AI learning and demonstration
