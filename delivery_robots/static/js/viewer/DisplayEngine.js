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

        const [locData, robotData, orderData] = await Promise.all([
            pathfindingManager.getLocations(),
            pathfindingManager.getRobots(),
            pathfindingManager.getOrders().catch(() => ({ orders: [] }))
        ]);

        this.snappedLocations = locData.locations;
        const initialStarts = this.snappedLocations.slice(0, 5);

        this.robots = robotData.robots.map((r, i) => {
            const start = initialStarts[i] || initialStarts[0];
            return new DeliveryRobot(i, start.lat, start.lon, r.name, r.color);
        });

        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        if (orderData && orderData.orders) {
            const store = Alpine.store('sim');
            if (store) {
                store.orders = orderData.orders;
            }
        }

        // Connect WebSocket
        if (typeof io !== 'undefined') {
            this.socket = io();

            this.socket.on('robot_state_update', (state) => {
                this.handleRobotState(state);
            });

            this.socket.on('order_state_update', (task) => {
                const store = Alpine.store('sim');
                if (store) {
                    const idx = store.orders.findIndex(o => o.id === task.id);
                    if (idx !== -1) {
                        store.orders[idx] = task;
                    } else {
                        store.orders.unshift(task);
                    }
                }
            });

            this.socket.on('system_event', (data) => {
                logEvent('🌐 ' + data.message);
                addDispatchInsight(data.message);
                if (typeof window.appendDispatchInsight === 'function') {
                    window.appendDispatchInsight(data.message);
                }
                if (data.message === "Simulation reset") {
                    const store = Alpine.store('sim');
                    if (store) {
                        store.orders = [];
                    }
                }
            });

            this.socket.on('clock_update', (data) => {
                const store = Alpine.store('sim');
                if (store) {
                    store.clock = data.time.display;
                    store.rushHour.active = data.rushHour.isActive;
                    store.rushHour.multiplier = data.rushHour.multiplier;
                    store.speed = data.simulationSpeed;
                }
            });
        }

        this.startAnimationLoop();
        logEvent('🚀 Frontend Display Ready');
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
        robot.battery = state.battery;
        robot.currentPathLength = state.current_path_length;
        robot.chargingStation = state.charging_station;
        robot.remainingChargeTime = state.remaining_charge_time;
        robot.updateMarkerIcon();
        
        // Save duration per path index to prevent overwriting the duration of the current interpolating segment
        robot.backendDurations = robot.backendDurations || {};
        if (state.segment_duration !== undefined) {
            robot.backendDurations[state.path_index] = state.segment_duration;
        }
        robot.segmentDuration = state.segment_duration; // fallback

        if (robot.routeTarget !== state.route_target) {
            robot.backendPathIndex = state.path_index;
        } else {
            robot.backendPathIndex = Math.max(robot.backendPathIndex || 0, state.path_index);
        }

        robot.routeTarget = state.route_target

        if (state.geometry_path && state.geometry_path.length > 0) {
            // Detect route change: new target or different path length
            const needsReset = !robot.geometryPath
                || robot.geometryPath.length !== state.geometry_path.length
                || robot.routeTarget !== state.route_target;

            if (needsReset) {
                const isSameRoute = (robot.routeTarget === state.route_target && robot.status !== 'idle');
                const safePathIndex = isSameRoute ? Math.max(robot.path_index || 0, state.path_index) : state.path_index;
                robot.setPath(
                    [],                           // currentPath: not needed, kept empty
                    state.geometry_path,          // flat geometry — for drawing
                    state.segment_geometry || [], // nested — for proportional interpolation
                    state.route_target,
                    null,
                    state.path_index
                );
            }
        } else if (state.status === 'idle' || state.status === 'charging') {
            robot.clearPathLine();
            robot.currentPath    = [];
            robot.geometryPath   = [];
            robot.segmentGeometry = [];
            robot.backendDurations = {};
        }

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
            this.isPaused = false;
            logEvent('▶ Requested Start');
        }
    }

    pause() {
        if (this.socket) {
            this.socket.emit('pause_simulation');
            this.isPaused = true;
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
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div class="robot-name" style="color:${robot.color}; margin-bottom: 0;">${robot.name}</div>
                    <span style="font-size: 11px; font-weight: 700; color: ${robot.battery < 20 ? '#ea4335' : '#34a853'};">
                        ${(robot.battery || 100).toFixed(1)}%
                    </span>
                </div>
                <div class="robot-detail">Status: ${robot.status.toUpperCase()}</div>
                ${robot.status === 'charging' && robot.remainingChargeTime > 0 ? `
                    <div class="robot-detail">Remaining Charge Time: ${Math.round(robot.remainingChargeTime)}s</div>
                ` : ''}
                <div class="robot-detail">Target: ${robot.routeTarget ? robot.routeTarget : 'None'}</div>
                <div class="battery-bar">
                    <div class="battery-fill" style="width: ${robot.battery || 100}%; background: ${robot.battery < 20 ? '#ea4335' : 'linear-gradient(90deg, #34a853, #4285f4)'}"></div>
                </div>
            `;
            container.appendChild(card);
        });
    }
}
