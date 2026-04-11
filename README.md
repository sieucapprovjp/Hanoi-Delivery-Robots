# 🤖 AI Delivery Robots - Suburban Hanoi Simulation

An interactive AI-powered delivery robot simulation set in suburban Hanoi, featuring 3 autonomous delivery robots with advanced pathfinding and routing capabilities.

## Features

### 🎯 Core Features
- **3 Autonomous Robots**: Each with unique identities and capabilities
- **A* Pathfinding**: Intelligent route planning through road networks
- **Dynamic Rerouting**: Real-time obstacle avoidance and path adjustment
- **Delivery Management**: Automated package pickup and delivery system
- **Traffic Simulation**: Traffic lights and congestion modeling
- **Battery Management**: Robots autonomously manage charging cycles

### 🗺️ Hanoi Suburban Map
- Realistic road network with named streets
- 10 landmarks (Big C, Aeon Mall, markets, schools, etc.)
- 80+ buildings (residential, commercial, offices)
- Dynamic obstacles (construction zones, traffic)
- Traffic light system at intersections

### 🤖 AI Capabilities
- **Pathfinding**: A* algorithm for optimal routes
- **Obstacle Avoidance**: Dynamic detection and rerouting
- **Task Scheduling**: Intelligent delivery assignment
- **Traffic Response**: Wait at red lights and avoid congestion
- **Battery Optimization**: Autonomous charging behavior

### 🎮 Interactive Controls
- Start/Pause/Reset simulation
- Adjustable simulation speed (1x-10x)
- Zoom in/out controls
- Real-time robot status monitoring
- Live delivery queue tracking
- Event logging system

## Installation & Running

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Setup

1. **Install dependencies**:
```bash
cd delivery_robots
pip install -r requirements.txt
```

2. **Run the application**:
```bash
python app.py
```

3. **Open in browser**:
Navigate to `http://127.0.0.1:5000`

## Usage

1. Click **▶ Start** to begin the simulation
2. Robots will automatically:
   - Accept delivery assignments
   - Navigate to pickup locations
   - Deliver packages to destinations
   - Avoid obstacles and traffic
   - Recharge when battery is low
3. Adjust simulation speed using the slider
4. Use + / - buttons to zoom in/out on the map
5. Watch the event log for real-time updates

## Technical Stack

- **Backend**: Python Flask
- **Frontend**: HTML5 Canvas + Vanilla JavaScript
- **Algorithm**: A* Pathfinding with dynamic rerouting
- **Rendering**: Canvas 2D with custom animations

## Project Structure

```
delivery_robots/
├── app.py                 # Flask server
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Styling
    └── js/
        ├── app.js        # Main application entry
        ├── simulation.js # Simulation engine
        ├── robot.js      # Robot class
        ├── map.js        # Hanoi map configuration
        └── pathfinding.js # A* algorithm
```

## Future Enhancements

- [ ] Multi-robot coordination algorithms
- [ ] Machine learning for delivery pattern optimization
- [ ] Real-time traffic data integration
- [ ] Weather effects on delivery times
- [ ] Package weight and priority handling
- [ ] Robot-to-robot communication
- [ ] Historical delivery analytics

## License

MIT License - Feel free to use and modify!

## Author

Built with ❤️ for AI learning and demonstration
