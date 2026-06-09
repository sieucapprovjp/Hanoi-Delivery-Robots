// Working simulation
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

        logEvent('🚀 Click START to begin!');
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
            if (robot.currentDelivery && robot.status === CONFIG.ROBOT.STATUSES.MOVING) {
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
        const pickupGroups = CONFIG.SIMULATION.PICKUP_WEIGHTS;
        const dropoffGroups = CONFIG.SIMULATION.DROPOFF_WEIGHTS;

        const weightedPick = (weights) => {
            const entries = Object.entries(weights);
            const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
            let target = Math.random() * total;

            for (const [category, weight] of entries) {
                target -= weight;
                if (target <= 0) return category;
            }

            return entries[entries.length - 1][0];
        };

        const randomLocationForCategory = (category, excludeName = null) => {
            const matches = locations.filter(location => location.category === category && location.name !== excludeName);
            const pool = matches.length > 0 ? matches : locations.filter(location => location.name !== excludeName);
            return pool[Math.floor(Math.random() * pool.length)];
        };

        const pickupCategory = weightedPick(pickupGroups);
        const pickup = randomLocationForCategory(pickupCategory);
        let dropoffCategory = weightedPick(dropoffGroups);
        let dest = randomLocationForCategory(dropoffCategory, pickup.name);

        if (dest.name === pickup.name) {
            dropoffCategory = CONFIG.SIMULATION.CATEGORIES.RESIDENTIAL;
            dest = randomLocationForCategory(dropoffCategory, pickup.name);
        }

        const delivery = {
            id: this.totalDeliveries + this.pendingDeliveries.length + 1,
            pickup: pickup,
            destination: dest,
            status: CONFIG.SIMULATION.DELIVERY_STATUSES.PENDING,
            createdAt: Date.now(),
            theme: {
                pickupCategory,
                dropoffCategory,
                pickupIcon: pickup.icon,
                dropoffIcon: dest.icon
            },
        };

        this.pendingDeliveries.push(delivery);
        this.logDeliveryData(delivery);
    }

    async logDeliveryData(delivery) {
        try {
            await postJson(CONFIG.API.LOG_DELIVERY, {
                pickupLat: delivery.pickup.lat,
                pickupLon: delivery.pickup.lon,
                dropoffLat: delivery.destination.lat,
                dropoffLon: delivery.destination.lon
            });
        } catch (e) {
            console.error('Failed to log delivery data', e);
        }
    }

    async assignDeliveries() {
        if (this.isAssigning) return;

        const hasAvailableRobot = this.robots.some(r => r.status === CONFIG.ROBOT.STATUSES.IDLE && r.currentLoad < r.capacity && !r.isRouting);
        if (!hasAvailableRobot || this.pendingDeliveries.length === 0) return;

        this.isAssigning = true;
        try {
            const data = await postJson(CONFIG.API.DISPATCH_ASSIGN, {
                robots: this.robots.map(r => ({
                    id: r.id,
                    name: r.name,
                    lat: r.lat,
                    lon: r.lon,
                    battery: r.battery,
                    status: r.status,
                    currentLoad: r.currentLoad,
                    capacity: r.capacity,
                    roadMemory: r.roadMemory,
                    routeAlgorithm: r.routeAlgorithm
                })),
                deliveries: this.pendingDeliveries,
                currentTime: Date.now()
            });
            const assignments = data.assignments || [];
            this.updateDispatchTimeline(data.explanations || []);

            for (const best of assignments) {
                const deliveryIndex = this.pendingDeliveries.findIndex(d => d.id === best.deliveryId);
                if (deliveryIndex === -1) continue;
                const delivery = this.pendingDeliveries[deliveryIndex];

                const robot = this.robots.find(r => r.id === best.robotId);
                if (!robot) continue;

                delivery.priorityScore = best.priorityScore;
                this.lastDecisionCost = best.totalScore;
                this.latestDecision = {
                    robotName: best.robotName,
                    deliveryId: delivery.id,
                    priorityScore: best.priorityScore,
                    batteryRisk: best.batteryRisk,
                    totalScore: best.totalScore,
                    breakdown: best.breakdown,
                    pickupName: delivery.pickup.name,
                    destinationName: delivery.destination.name,
                    explanation: best.explanation || null
                };

                addDispatchInsight(
                    `${robot.name} assigned to order #${delivery.id} with priority ${best.priorityScore.toFixed(1)}.`,
                    CONFIG.UI.LOG_LEVELS.SUCCESS
                );

                const assigned = await robot.assignDelivery(delivery, best.route, best.breakdown);
                if (assigned) {
                    this.pendingDeliveries.splice(deliveryIndex, 1);
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
        this.updateAlgorithmComparison();
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
        logEvent('▶ Started!');
    }

    pause() {
        this.running = false;
        logEvent('⏸ Paused');
    }

    async reset() {
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
            robot.lat = start.lat;
            robot.lon = start.lon;
            robot.battery = CONFIG.ROBOT.INITIAL_BATTERY;
            robot.status = CONFIG.ROBOT.STATUSES.IDLE;
            robot.currentLoad = 0;
            robot.totalDeliveries = 0;
            robot.totalDistance = 0;
            robot.currentPath = [];
            robot.pathIndex = 0;
            robot.currentDelivery = null;
            robot.currentDeliveryAlgorithm = null;
            robot.isRouting = false;
            robot.lastRouteEtaMinutes = 0;
            robot.lastRouteBreakdown = null;
            robot.routeAlgorithm = this.fleetAlgorithm;
            robot.clearPathLine();
            if (robot.marker) robot.marker.setLatLng([robot.lat, robot.lon]);
        });


        for (let i = 0; i < CONFIG.SIMULATION.INITIAL_DELIVERY_COUNT; i++) {
            this.generateDelivery();
        }

        logEvent('🔄 Reset');
        addDispatchInsight('Dispatch state reset. Queue rebuilt and analytics cleared.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
        this.updateFleetAlgorithmState();
        this.updateRobotStatus();
        this.updateAlgorithmComparison();
    }

    async optimizeHubs() {
        logEvent('🧠 Optimizing hub locations...');
        addDispatchInsight('Running k-means clustering on delivery hotspots to reposition fleet...', CONFIG.UI.LOG_LEVELS.NEUTRAL);

        try {
            const data = await postJson(CONFIG.API.OPTIMIZE_HUBS, undefined, 'Optimization failed');

            const hubs = data.hubs;

            this.robots.forEach((robot, i) => {
                if (i < hubs.length) {
                    const hub = hubs[i];
                    robot.lat = hub.lat;
                    robot.lon = hub.lon;
                    robot.status = CONFIG.ROBOT.STATUSES.IDLE;
                    robot.currentPath = [];
                    robot.clearPathLine();
                    if (robot.marker) robot.marker.setLatLng([robot.lat, robot.lon]);
                }
            });

            logEvent('✅ Hubs optimized!');
            addDispatchInsight(`Fleet repositioned to ${hubs.length} optimal centroids. Check map for new starting points.`, CONFIG.UI.LOG_LEVELS.SUCCESS);

            if (window.mapManager) {
                window.mapManager.drawHubs(hubs);
                await window.mapManager.reloadChargingStations();
            }

        } catch (e) {
            logEvent('❌ Optimization failed');
            addDispatchInsight(`Hub optimization error: ${e.message}`, CONFIG.UI.LOG_LEVELS.WARN);
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
