class DisplayEngine {
    constructor() {
        this.robots = [];
        this.socket = null;
    }

    async initialize() {
        if (this.robots && this.robots.length > 0) {
            this.robots.forEach(robot => robot.removeMarker());
            this.robots = [];
        }

        pathfindingManager = new BackendAPI();
        if (!mapManager) {
            mapManager = new HanoiMap();
            await mapManager.initializeMap();
            window.mapManager = mapManager;
        }

        const [locData, robotData] = await Promise.all([
            pathfindingManager.getLocations(),
            pathfindingManager.getRobots()
        ]);

        this.snappedLocations = locData.locations;
        const initialStarts = this.snappedLocations.slice(0, 5);

        this.robots = robotData.robots.map((r, i) => {
            const start = initialStarts[i] || initialStarts[0];
            return new DeliveryRobot(i, start.lat, start.lon, r.name, r.color);
        });

        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        // Connect WebSocket
        if (typeof io !== 'undefined') {
            this.socket = io();
            
            this.socket.on('robot_state_update', (state) => {
                this.handleRobotState(state);
            });
            
            this.socket.on('system_event', (data) => {
                logEvent('🌐 ' + data.message);
                addDispatchInsight(data.message);
            });
        }

        this.startAnimationLoop();
        logEvent('🚀 Frontend Display Ready (Event-Driven)');
    }

    startAnimationLoop() {
        const loop = () => {
            this.robots.forEach(robot => robot.update());
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }

    handleRobotState(state) {
        const robot = this.robots[state.id];
        if (!robot) return;
        
        robot.status = state.status;
        robot.backendPathIndex = state.path_index;
        robot.battery = state.battery;
        robot.routeTarget = state.route_target;
        robot.currentPathLength = state.current_path_length;

        if (state.path_coords && state.path_coords.length > 0) {
            if (!robot.currentPath || robot.currentPath.length !== state.current_path_length || robot.routeTarget !== state.route_target) {
                robot.setPath(state.path_coords, state.route_target, null, state.path_index);
            }
        } else if (state.status === 'idle') {
            robot.clearPathLine();
            robot.currentPath = [];
        }
        
        // Only snap position if idle to allow interpolation to work when moving
        if (state.status === 'idle') {
            robot.lat = state.lat;
            robot.lon = state.lon;
            if (robot.marker) robot.marker.setLatLng([state.lat, state.lon]);
        }
        
        if (robot.marker && robot.marker.isPopupOpen()) {
            robot.updatePopup();
        }
        
        this.updateRobotStatus();
    }

    start() {
        if (this.socket) {
            this.socket.emit('start_simulation');
            logEvent('▶ Requested Start');
        }
    }

    pause() {
        if (this.socket) {
            this.socket.emit('pause_simulation');
            logEvent('⏸ Requested Pause');
        }
    }

    reset() {
        if (this.socket) {
            this.socket.emit('reset_simulation');
            logEvent('🔄 Requested Reset');
        }
    }

    updateRobotStatus() {
        const container = document.getElementById('robot-status');
        if (!container) return;

        container.innerHTML = '';

        this.robots.forEach(robot => {
            const card = document.createElement('div');
            card.className = 'robot-card';
            card.style.borderLeftColor = robot.color;
            card.innerHTML = `
                <div class="robot-name" style="color:${robot.color}">${robot.name}</div>
                <div class="robot-detail">Status: ${robot.status.toUpperCase()}</div>
                <div class="robot-detail">Target: ${robot.routeTarget ? robot.routeTarget : 'None'}</div>
                <div class="battery-bar">
                    <div class="battery-fill" style="width: ${robot.battery || 100}%; background: ${robot.battery < 20 ? '#ea4335' : 'linear-gradient(90deg, #34a853, #4285f4)'}"></div>
                </div>
            `;
            container.appendChild(card);
        });
    }
}
