# Technology Stack

This document specifies the programming languages, frameworks, libraries, API versions, and tooling configured for the **AI Delivery Robots Simulation** project.

---

## 🐍 Backend (Python Services)

| Component / Library | Version Specified | Purpose |
| :--- | :--- | :--- |
| **Python** | `3.10+` | Core programming language |
| **Flask** | `3.0.0` | Micro WSGI web framework exposing REST APIs |
| **Flask-SocketIO** | *Latest (Implied)* | WebSocket wrapper for real-time simulation updates |
| **OSMnx** | `2.1.0` | Downloads and constructs spatial street graphs from OpenStreetMap |
| **NetworkX** | `3.6.1` | Underlying mathematical graph library representing nodes and edges |
| **SimPy** | *Latest (Implied)* | Discrete event simulation library scheduling asynchronous robot processes |
| **Scikit-learn** | *Latest (Implied)* | Machine learning package providing KMeans for hub optimization |
| **NumPy** | *Latest (Implied)* | Performs fast vector math, coordinate scaling, and spatial tree lookups |
| **Werkzeug** | *Dependency* | Underpins Flask; handles request routing and WSGI debugging |

---

## 🌐 Frontend (User Interface)

| Library / Tool | Version Loaded | Purpose |
| :--- | :--- | :--- |
| **HTML5 & CSS3** | Native | Semantics structure and stylesheet aesthetics |
| **Vanilla JavaScript** | ES6+ | Encapsulated client classes (`DisplayEngine`, `RainManager`, etc.) |
| **Leaflet.js** | `1.9.4` | Renders interactive maps, coordinates polylines, and plots icons |
| **Alpine.js** | `3.x.x` | Coordinates UI panel toggles, binds clock ticks, and renders log text |
| **Socket.IO Client** | `4.7.2` | Listens to backend websocket loops, feeding real-time updates to UI |

---

## 🛠️ Development & Testing Infrastructure

*   **Virtual Environments (`.venv`)**: Isolated runtime environment to prevent system package collisions.
*   **Testing Engine (`unittest`)**: Built-in Python testing suite executing assertions, regression checks, and mocks.
*   **Graph Construction**: Builds Hanoi's Hoan Kiem district street nodes (`GRAPH_CENTER = (21.0285, 105.8542)`) projected to bike networks using spatial coordinate maps.
*   **Python Package Installer (`pip`)**: Resolves backend library trees using the defined `requirements.txt`.
