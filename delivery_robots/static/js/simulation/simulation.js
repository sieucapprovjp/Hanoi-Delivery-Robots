// Coordinates fleet state, dispatch assignment, and metrics updates.
let simulation;
let mapManager;
let pathfindingManager;

class Simulation {
    constructor() {
        this.robots = [];
        this.pendingDeliveries = [];
        this.running = false;
        this.speed = 1;
        this.totalDeliveries = 0;
        this.totalDistance = 0;
        this.simulationTime = 0;
        this.lastDeliveryTime = 0;
        this.deliveryInterval = CONFIG.SIMULATION.DELIVERY_INTERVAL_MS;
        this.totalReroutes = 0;
        this.totalBatteryConsumed = 0;
        this.lastDecisionCost = 0;
        this.latestDecision = null;
        this.fleetAlgorithm = CONFIG.SIMULATION.DEFAULT_ALGORITHM;
        this.dispatchVersion = 0;
        this.algorithmStats = {};
        CONFIG.SIMULATION.ALGORITHMS.forEach(algo => {
            this.algorithmStats[algo] = this.createAlgoStats();
        });
    }

    createAlgoStats() {
        return {
            routeCount: 0,
            totalRouteTimeMs: 0,
            totalNodesExplored: 0,
            totalPathCost: 0,
            deliveriesCompleted: 0,
            rerouteCount: 0
        };
    }

    async initialize() {
        if (this.robots && this.robots.length > 0) {
            console.log('Cleaning up existing robots...');
            this.robots.forEach(robot => robot.removeMarker());
            this.robots = [];
        }

        pathfindingManager = new Pathfinding();
        if (mapManager) {
            console.log('Map already initialized, reuse existing mapManager');
        } else {
            mapManager = new HanoiMap();
            mapManager.initializeMap();
            window.mapManager = mapManager;
        }

        console.log('📍 Snapping locations to road network...');
        this.snappedLocations = await Promise.all(
            CONFIG.DATA.LOCATIONS.map(async location => {
                try {
                    const snapped = await pathfindingManager.snapToRoad(location.lat, location.lon);
                    return { ...location, lat: snapped.lat, lon: snapped.lon };
                } catch (e) {
                    console.warn(`Failed to snap ${location.name}, using original coords`);
                    return location;
                }
            })
        );

        const initialStarts = this.snappedLocations.slice(0, 5);

        this.robots = CONFIG.SIMULATION.INITIAL_ROBOTS.map((r, i) => {
            const start = initialStarts[i] || initialStarts[0];
            return new DeliveryRobot(i, start.lat, start.lon, r.name, r.color, this.fleetAlgorithm);
        });

        console.log(`🚀 Creating markers for ${this.robots.length} robots`);
        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        for (let i = 0; i < CONFIG.SIMULATION.INITIAL_DELIVERY_COUNT; i++) {
            this.generateDelivery();
        }

        logEvent(CONFIG.UI.TEXT.LOGS.START_PROMPT);
        addDispatchInsight('Dispatch engine online. Monitoring queue pressure, weather, and traffic.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
        this.updateFleetAlgorithmState();
        this.updateAlgorithmComparison();
    }

    setFleetAlgorithm(algo) {
        const normalized = (algo || '').toLowerCase();
        if (!CONFIG.SIMULATION.ALGORITHMS.includes(normalized)) return;

        this.fleetAlgorithm = normalized;
        this.algorithmStats = {};
        CONFIG.SIMULATION.ALGORITHMS.forEach(a => {
            this.algorithmStats[a] = this.createAlgoStats();
        });

        this.robots.forEach(robot => {
            robot.routeAlgorithm = normalized;
            if ((robot.currentDelivery || robot.routeSequence?.length) && robot.status === CONFIG.ROBOT.STATUSES.MOVING) {
                robot.currentDeliveryAlgorithm = normalized;
            }
        });

        this.updateFleetAlgorithmState();
        this.updateAlgorithmComparison();
        logEvent(`🧠 Fleet AI switched to ${normalized.toUpperCase()} for all robots`);
        addDispatchInsight(`Fleet benchmark mode: all ${this.robots.length} robots now use ${normalized.toUpperCase()}. Metrics reset for fair comparison.`, CONFIG.UI.LOG_LEVELS.NEUTRAL);
    }

    updateFleetAlgorithmState() {
        const store = Alpine.store('sim');
        if (store) {
            store.metrics.fleetAlgo = this.fleetAlgorithm.toUpperCase();
        }
    }

    generateDelivery() {
        const locations = this.snappedLocations || CONFIG.DATA.LOCATIONS;
        const deliveryId = this.totalDeliveries + this.pendingDeliveries.length + 1;
        const delivery = createDelivery(locations, deliveryId);
        this.pendingDeliveries.push(delivery);
        this.logDeliveryData(delivery);
    }

    async logDeliveryData(delivery) {
        try {
            await postJson(CONFIG.API.LOG_DELIVERY, buildDeliveryLogPayload(delivery));
        } catch (e) {
            console.error('Failed to log delivery data', e);
        }
    }

    async assignDeliveries() {
        if (this.isAssigning) return;

        const hasAvailableRobot = this.robots.some(r => (
            r.status === CONFIG.ROBOT.STATUSES.IDLE
            && r.currentLoad < Math.min(r.capacity, CONFIG.VRP.MAX_ORDERS_PER_ROBOT)
            && !r.isRouting
        ));
        if (!hasAvailableRobot || this.pendingDeliveries.length === 0) return;

        this.isAssigning = true;
        const dispatchVersion = this.dispatchVersion;
        try {
            const { assignments, explanations } = await requestDispatchAssignments(this.robots, this.pendingDeliveries);
            if (dispatchVersion !== this.dispatchVersion) return;
            this.updateDispatchTimeline(explanations);

            for (const best of assignments) {
                if (dispatchVersion !== this.dispatchVersion) return;
                const deliveryIds = best.deliveryIds || [best.deliveryId];
                const deliveryBatch = deliveryIds
                    .map(id => this.pendingDeliveries.find(d => String(d.id) === String(id)))
                    .filter(Boolean);
                if (!deliveryBatch.length) continue;
                const delivery = deliveryBatch[0];

                const robot = this.robots.find(r => r.id === best.robotId);
                if (!robot) continue;

                delivery.priorityScore = best.priorityScore;
                this.lastDecisionCost = best.totalScore;
                this.latestDecision = buildLatestDecision(best, delivery);

                addDispatchInsight(
                    `${robot.name} assigned ${deliveryBatch.length} order(s): ${deliveryBatch.map(item => `#${item.id}`).join(', ')}.`,
                    CONFIG.UI.LOG_LEVELS.SUCCESS
                );

                const assigned = await robot.assignDelivery(
                    delivery,
                    best.route,
                    best.breakdown,
                    best,
                    deliveryBatch
                );
                if (assigned) {
                    const assignedIds = new Set(deliveryBatch.map(item => String(item.id)));
                    this.pendingDeliveries = this.pendingDeliveries.filter(
                        item => !assignedIds.has(String(item.id))
                    );
                }
            }
        } catch (e) {
            console.error('Dispatch assignment error:', e);
        } finally {
            this.isAssigning = false;
        }
    }

    updateDispatchTimeline(explanations) {
        const store = Alpine.store('sim');
        if (!store) return;
        store.decision.dispatchTimeline = renderDispatchTimeline(explanations);
    }

    update() {
        if (!this.running) return;

        this.simulationTime += CONFIG.SIMULATION.TIME_DELTA * this.speed;

        if (Date.now() - this.lastDeliveryTime > this.deliveryInterval / this.speed) {
            this.generateDelivery();
            this.lastDeliveryTime = Date.now();
        }

        const batteryBefore = this.robots.reduce((sum, r) => sum + r.battery, 0);
        this.robots.forEach(robot => robot.update());
        const batteryAfter = this.robots.reduce((sum, r) => sum + r.battery, 0);
        this.totalBatteryConsumed += Math.max(0, batteryBefore - batteryAfter);
        this.totalDistance = this.robots.reduce((sum, r) => sum + r.totalDistance, 0);

        if (!this.isAssigning) {
            this.assignDeliveries();
        }

        this.totalDeliveries = this.robots.reduce((sum, r) => sum + r.totalDeliveries, 0);

        // UI Updates via store or minimal direct DOM for high frequency
        this.updateRobotStatus();
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.lastDeliveryTime = Date.now();

        const loop = async () => {
            if (!this.running) return;
            await this.update();
            requestAnimationFrame(loop);
        };

        requestAnimationFrame(loop);
        logEvent(CONFIG.UI.TEXT.LOGS.STARTED);
    }

    pause() {
        this.running = false;
        logEvent(CONFIG.UI.TEXT.LOGS.PAUSED);
    }

    async reset() {
        this.dispatchVersion++;
        this.pause();
        this.totalDeliveries = 0;
        this.totalDistance = 0;
        this.simulationTime = 0;
        this.pendingDeliveries = [];
        mapManager.clearAllDeliveryMarkers();
        this.totalReroutes = 0;
        this.totalBatteryConsumed = 0;
        this.lastDecisionCost = 0;
        this.latestDecision = null;
        this.algorithmStats = {};
        CONFIG.SIMULATION.ALGORITHMS.forEach(algo => {
            this.algorithmStats[algo] = this.createAlgoStats();
        });

        const starts = this.snappedLocations.slice(0, 5);
        this.robots.forEach((robot, i) => {
            const start = starts[i] || starts[0];
            robot.resetOperationalState(start.lat, start.lon, {
                resetBattery: true,
                resetStats: true
            });
            robot.routeAlgorithm = this.fleetAlgorithm;
        });


        for (let i = 0; i < CONFIG.SIMULATION.INITIAL_DELIVERY_COUNT; i++) {
            this.generateDelivery();
        }

        logEvent(CONFIG.UI.TEXT.LOGS.RESET);
        addDispatchInsight('Dispatch state reset. Queue rebuilt and analytics cleared.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
        this.updateFleetAlgorithmState();
        this.updateRobotStatus();
        this.updateAlgorithmComparison();
    }

    async optimizeHubs() {
        this.dispatchVersion++;
        this.isAssigning = true;
        logEvent(CONFIG.UI.TEXT.LOGS.OPTIMIZING_HUBS);
        addDispatchInsight('Running k-means clustering on delivery hotspots to reposition fleet...', CONFIG.UI.LOG_LEVELS.NEUTRAL);

        try {
            const data = await postJson(
                CONFIG.API.OPTIMIZE_HUBS,
                undefined,
                CONFIG.UI.TEXT.API_ERRORS.HUB_OPTIMIZATION
            );

            const hubs = data.hubs;
            const returnedDeliveries = [];
            const returnedIds = new Set(this.pendingDeliveries.map(item => String(item.id)));

            this.robots.forEach((robot, i) => {
                robot.deliveryQueue.forEach(delivery => {
                    const key = String(delivery.id);
                    if (!returnedIds.has(key)) {
                        returnedDeliveries.push(delivery);
                        returnedIds.add(key);
                    }
                });

                const hub = hubs[i] || hubs[i % hubs.length];
                if (hub) {
                    robot.resetOperationalState(hub.lat, hub.lon);
                }
            });

            if (returnedDeliveries.length > 0) {
                this.pendingDeliveries.unshift(...returnedDeliveries);
                returnedDeliveries.forEach(delivery => mapManager.clearDeliveryMarkers(delivery.id));
                addDispatchInsight(
                    `${returnedDeliveries.length} active order(s) were returned to the queue before hub relocation.`,
                    CONFIG.UI.LOG_LEVELS.NEUTRAL
                );
            }

            this.isAssigning = false;
            this.lastDeliveryTime = Date.now();
            logEvent(CONFIG.UI.TEXT.LOGS.HUBS_OPTIMIZED);
            addDispatchInsight(`Fleet repositioned to ${hubs.length} optimal centroids. Check map for new starting points.`, CONFIG.UI.LOG_LEVELS.SUCCESS);

            if (window.mapManager) {
                window.mapManager.drawHubs(hubs);
                await window.mapManager.reloadChargingStations();
            }

            this.updateRobotStatus();
        } catch (e) {
            logEvent(CONFIG.UI.TEXT.LOGS.OPTIMIZATION_FAILED);
            addDispatchInsight(`Hub optimization error: ${e.message}`, CONFIG.UI.LOG_LEVELS.WARN);
        } finally {
            this.isAssigning = false;
        }
    }

    updateRobotStatus() {
        const container = document.getElementById('robot-status');
        if (container) {
            container.innerHTML = renderRobotStatusCards(this.robots);
        }

        const queueContainer = document.getElementById('delivery-queue');
        if (queueContainer) {
            queueContainer.innerHTML = renderDeliveryQueue(this.pendingDeliveries);
        }
    }

    recordRouteMetrics(algo, route) {
        const bucket = this.algorithmStats[algo];
        if (!bucket) return;

        bucket.routeCount += 1;
        bucket.totalRouteTimeMs += route.timeMs || 0;
        bucket.totalNodesExplored += route.nodesExplored || 0;
        bucket.totalPathCost += route.pathCost || route.distance || 0;
    }

    recordDeliveryCompleted(algo) {
        const bucket = this.algorithmStats[algo];
        if (bucket) bucket.deliveriesCompleted += 1;
    }

    recordReroute(algo) {
        const bucket = this.algorithmStats[algo];
        if (bucket) bucket.rerouteCount += 1;
    }

    calculateEfficiencyScore(stats) {
        return calculateAlgorithmEfficiency(stats);
    }

    updateAlgorithmComparison() {
        const store = Alpine.store('sim');
        if (!store) return;
        store.insider.comparison = renderAlgorithmComparison(
            this.algorithmStats,
            this.fleetAlgorithm
        );
    }
}
