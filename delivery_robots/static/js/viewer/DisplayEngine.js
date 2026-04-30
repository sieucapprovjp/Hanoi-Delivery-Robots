class DisplayEngine {
    constructor() {
        this.robots = [];
        this.running = false;
        this.speed = 1;
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

        logEvent('🚀 Frontend Display Ready');
        addDispatchInsight('Display engine online. Waiting for backend updates.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
    }

    update() {
        if (!this.running) return;
        this.robots.forEach(robot => robot.update());
        this.updateRobotStatus();
    }

    start() {
        if (this.running) return;
        this.running = true;

        const loop = () => {
            if (!this.running) return;
            this.update();
            requestAnimationFrame(loop);
        };

        requestAnimationFrame(loop);
        logEvent('▶ Started Display Loop');
    }

    pause() {
        this.running = false;
        logEvent('⏸ Paused Display Loop');
    }

    reset() {
        this.pause();

        const starts = this.snappedLocations.slice(0, 5);
        this.robots.forEach((robot, i) => {
            const start = starts[i] || starts[0];
            robot.lat = start.lat;
            robot.lon = start.lon;
            robot.status = CONFIG.ROBOT.STATUSES.IDLE;
            robot.currentPath = [];
            robot.pathIndex = 0;
            robot.routeTarget = null;
            robot.deliveryPhase = null;
            robot.clearPathLine();
            if (robot.marker) robot.marker.setLatLng([robot.lat, robot.lon]);
        });

        logEvent('🔄 Reset Display');
        this.updateRobotStatus();
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
                <div class="robot-detail">Pos: ${robot.lat.toFixed(4)}, ${robot.lon.toFixed(4)}</div>
            `;
            container.appendChild(card);
        });
    }
}
