# Project Map

This document provides a comprehensive layout of the directory structure, highlighting the purpose and function of each module within the **AI Delivery Robots Simulation** project.

---

## 📂 Directory Tree & Module Breakdown

```text
AI-Intro/
├── .agents/                    # Agent-specific instruction and metadata files
├── delivery_robots/            # Main application package
│   ├── algorithms/             # Search engines and AI clustering modules
│   │   ├── __init__.py
│   │   ├── astar.py            # A* Search algorithm with Haversine heuristic
│   │   ├── base.py             # Reconstructs routes from node parent listings
│   │   ├── dijkstra.py         # Dijkstra's Algorithm
│   │   ├── gbfs.py             # Greedy Best-First Search
│   │   └── search_manager.py   # Dispatches path routing queries dynamically
│   │
│   ├── core/                   # Core simulation logic, math, and OSMnx graphs
│   │   ├── simulation/         # SimPy-based discrete event simulation components
│   │   │   ├── __init__.py
│   │   │   ├── robot_agent.py  # RobotAgent state machines, battery, and travel logic
│   │   │   └── simulator.py    # SimulatorManager scheduling thread, naive CSP order dispatcher
│   │   ├── __init__.py
│   │   ├── data.py             # Static list of landmark coordinates, charging stations, and colors
│   │   ├── environment.py      # Calculations of rush hours, rain, traffic, and obstacle costs
│   │   ├── graph.py            # OSMnx Hanoi Hoan Kiem graph building, indexing spatial trees
│   │   └── hubs.py             # Unsupervised K-means algorithm to find optimized charging centers
│   │
│   ├── routes/                 # Flask HTTP API Controller blueprints
│   │   ├── __init__.py
│   │   ├── environment_routes.py # CRUD APIs for rain, traffic, obstacles, logging, and metrics
│   │   └── main_routes.py      # Static resources render, hub optimization actions, static configs
│   │
│   ├── static/                 # Front-end public assets (Leaflet, JS, CSS)
│   │   ├── css/
│   │   │   └── style.css       # Clean layout styling, badges, glassmorphism dashboard styling
│   │   └── js/
│   │       ├── environment/    # Scripts representing dynamic map layers (Rain, Traffic, Obstacles)
│   │       ├── viewer/         # Animation handlers, interpolation loops, map builders
│   │       ├── api.js          # REST Client wrappers for backend endpoint interactions
│   │       ├── config.js       # Centralized UI variables, refresh intervals, styling colors
│   │       └── main.js         # Entrypoint, Alpine.js listener hooks, metrics retrieval loops
│   │
│   ├── templates/              # HTML layout definitions
│   │   └── index.html          # Simulation dashboard frame, Alpine.js stores and layout panels
│   │
│   ├── utils/                  # Helper utilities and formulas
│   │   ├── __init__.py
│   │   ├── geo.py              # Math modules for Haversine distances and cross-track errors
│   │   ├── metrics.py          # Data collectors logging computational times and explored nodes
│   │   ├── profiler.py         # Time logging wrappers and profile blocks
│   │   ├── route_analysis.py   # Geometry parsers, spatial nearest node identifiers
│   │   └── validation.py       # Validators verifying coordinates and constraint bounds
│   │
│   ├── app.py                  # App initialization, thread safety structures, websocket events
│   └── config.py               # Backend configuration constants (traffic periods, penalization scales)
│
├── docs/                       # Project documentation directory
├── logs/                       # Application run logs
├── tests/                      # Python automated test suite
│   ├── __init__.py
│   ├── test_api.py             # Verifies environment API endpoints and validation limits
│   ├── test_route_analysis.py  # Tests cost breakdowns and trajectory geometries
│   └── test_validation.py      # Asserts validation constraints are parsed accurately
│
├── main.py                     # Main Python entrance script initiating graph generation and WSGI
├── requirements.txt            # Package dependencies list
└── README.md                   # Simulation overview and execution instructions
```

---

## 🛠️ Key File Overviews

*   **`main.py`**: The server's entry point. Initializes the Hanoi OpenStreetMap graph on launch, prints connection routes, and boots the Flask-SocketIO runtime.
*   **`delivery_robots/app.py`**: Integrates modules. Instantiates the global state dictionary, sets up websocket hooks for simulation steps (`start_simulation`, `pause_simulation`, `reset_simulation`), and initializes the SimPy-to-SocketIO thread.
*   **`delivery_robots/config.py`**: Houses all simulation magic numbers, scale parameters, and default values. Centralizing variables here avoids code smells and helps decouple parameters from algorithms.
*   **`delivery_robots/core/environment.py`**: Contains pure math methods calculating rain cost factors, rush hour wave multipliers, and obstacle distance penalties.
*   **`delivery_robots/utils/route_analysis.py`**: Contains trajectory formatting functions. Uses raw OSMnx edge data, builds linear coordinates, and structures segments so the frontend can animate movement smoothly.
