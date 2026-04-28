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
        // Map
        pathfindingManager = new Pathfinding();
        mapManager = new HanoiMap();
        mapManager.initializeMap();
        window.mapManager = mapManager;

        const [startA, startB, startC, startD, startE] = await Promise.all(
            CONFIG.DATA.LOCATIONS.slice(0, 5).map(loc => pathfindingManager.snapToRoad(loc.lat, loc.lon))
        );

        // Robots
        this.robots = CONFIG.SIMULATION.INITIAL_ROBOTS.map((r, i) => {
            const start = [startA, startB, startC, startD, startE][i];
            return new DeliveryRobot(i, start.lat, start.lon, r.name, r.color, this.fleetAlgorithm);
        });

        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        // Initial deliveries
        for (let i = 0; i < CONFIG.SIMULATION.INITIAL_DELIVERY_COUNT; i++) {
            await this.generateDelivery();
        }

        console.log('✓ Ready - Click START!');
        logEvent('🚀 Click START to begin!');
        addDispatchInsight('Dispatch engine online. Monitoring queue pressure, weather, and traffic.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
        this.updateFleetAlgorithmLabel();
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

        this.updateFleetAlgorithmLabel();
        this.updateRobotStatus();
        this.updateAlgorithmComparison();
        logEvent(`🧠 Fleet AI switched to ${normalized.toUpperCase()} for all robots`);
        addDispatchInsight(`Fleet benchmark mode: all ${this.robots.length} robots now use ${normalized.toUpperCase()}. Metrics reset for fair comparison.`, CONFIG.UI.LOG_LEVELS.NEUTRAL);
    }

    updateFleetAlgorithmLabel() {
        const labelMap = {
            astar: 'A*',
            dijkstra: 'Dijkstra',
            gbfs: 'GBFS'
        };
        const label = document.getElementById('fleet-algo-current');
        if (label) label.textContent = labelMap[this.fleetAlgorithm] || 'A*';
        const academicLabel = document.getElementById('academic-fleet-algo');
        if (academicLabel) academicLabel.textContent = labelMap[this.fleetAlgorithm] || 'A*';
        const select = document.getElementById('fleet-algo-select');
        if (select) select.value = this.fleetAlgorithm;
    }

    async generateDelivery() {
        const baseLocations = CONFIG.DATA.LOCATIONS;
        const locations = await Promise.all(
            baseLocations.map(async location => {
                const snapped = await pathfindingManager.snapToRoad(location.lat, location.lon);
                return { ...location, lat: snapped.lat, lon: snapped.lon };
            })
        );
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

        // 🧠 Log delivery coordinates for k-means optimization
        this.logDeliveryData(delivery);
    }

    async logDeliveryData(delivery) {
        try {
            await fetch(CONFIG.API.LOG_DELIVERY, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pickupLat: delivery.pickup.lat,
                    pickupLon: delivery.pickup.lon,
                    dropoffLat: delivery.destination.lat,
                    dropoffLon: delivery.destination.lon
                })
            });
        } catch (e) {
            console.error('Failed to log delivery data', e);
        }
    }

    async assignDeliveries() {
        const candidateRobots = this.robots.filter(r => r.status === CONFIG.ROBOT.STATUSES.IDLE && r.currentLoad < r.capacity && !r.isRouting);
        if (candidateRobots.length === 0 || this.pendingDeliveries.length === 0) return;

        try {
            const response = await fetch(CONFIG.API.DISPATCH_ASSIGN, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    robots: candidateRobots.map(r => ({
                        id: r.id,
                        name: r.name,
                        lat: r.lat,
                        lon: r.lon,
                        battery: r.battery,
                        roadMemory: r.roadMemory,
                        routeAlgorithm: r.routeAlgorithm
                    })),
                    deliveries: this.pendingDeliveries,
                    currentTime: Date.now()
                })
            });

            if (!response.ok) throw new Error('Assignment failed');
            const data = await response.json();
            const assignments = data.assignments || [];

            for (const best of assignments) {
                const deliveryIndex = this.pendingDeliveries.findIndex(d => d.id === best.deliveryId);
                if (deliveryIndex === -1) continue;
                const delivery = this.pendingDeliveries[deliveryIndex];

                const robot = this.robots.find(r => r.id === best.robotId);
                if (!robot) continue;

                // Sync the priority score back so the UI can show it if needed
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
                    destinationName: delivery.destination.name
                };

                addDispatchInsight(
                    `${robot.name} assigned to order #${delivery.id} with priority ${best.priorityScore.toFixed(1)}. Cost breakdown: base ${best.breakdown.baseDistance.toFixed(0)}m, traffic +${best.breakdown.trafficPenalty.toFixed(0)}m, rain +${best.breakdown.rainPenalty.toFixed(0)}m, obstacles +${best.breakdown.obstaclePenalty.toFixed(0)}m, battery risk +${best.batteryRisk.toFixed(1)}.`,
                    CONFIG.UI.LOG_LEVELS.SUCCESS
                );

                const assigned = await robot.assignDelivery(delivery, best.route, best.breakdown);
                if (assigned) {
                    this.pendingDeliveries.splice(deliveryIndex, 1);
                }
            }
        } catch (e) {
            console.error('Dispatch assignment error:', e);
        }
    }

    async update() {
        if (!this.running) return;

        this.simulationTime += CONFIG.SIMULATION.TIME_DELTA * this.speed;

        // Generate deliveries
        if (Date.now() - this.lastDeliveryTime > this.deliveryInterval / this.speed) {
            await this.generateDelivery();
            this.lastDeliveryTime = Date.now();
        }

        // Update robots
        const batteryBefore = this.robots.reduce((sum, r) => sum + r.battery, 0);
        this.robots.forEach(robot => robot.update());
        const batteryAfter = this.robots.reduce((sum, r) => sum + r.battery, 0);
        this.totalBatteryConsumed += Math.max(0, batteryBefore - batteryAfter);
        this.totalDistance = this.robots.reduce((sum, r) => sum + r.totalDistance, 0);

        // Assign pending deliveries
        await this.assignDeliveries();

        // Update UI
        this.totalDeliveries = this.robots.reduce((sum, r) => sum + r.totalDeliveries, 0);
        this.updateStats();
        this.updateRobotStatus();
        this.updateAnalytics();
        this.updateLatestDecision();
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

        const starts = await Promise.all(
            CONFIG.DATA.LOCATIONS.slice(0, 5).map(loc => pathfindingManager.snapToRoad(loc.lat, loc.lon))
        );
        this.robots.forEach((robot, i) => {
            robot.lat = starts[i].lat;
            robot.lon = starts[i].lon;
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

        this.robots.forEach(robot => robot.createMarker(mapManager.map));
        
        for (let i = 0; i < CONFIG.SIMULATION.INITIAL_DELIVERY_COUNT; i++) {
            await this.generateDelivery();
        }

        logEvent('🔄 Reset');
        addDispatchInsight('Dispatch state reset. Queue rebuilt and analytics cleared.', CONFIG.UI.LOG_LEVELS.NEUTRAL);
        this.updateStats();
        this.updateFleetAlgorithmLabel();
        this.updateRobotStatus();
        this.updateAnalytics();
        this.updateLatestDecision();
        this.updateAlgorithmComparison();
    }

    async optimizeHubs() {
        logEvent('🧠 Optimizing hub locations...');
        addDispatchInsight('Running k-means clustering on delivery hotspots to reposition fleet...', CONFIG.UI.LOG_LEVELS.NEUTRAL);

        try {
            const res = await fetch(CONFIG.API.OPTIMIZE_HUBS, { method: 'POST' });
            const data = await res.json();

            if (!res.ok) throw new Error(data.error || 'Optimization failed');

            const hubs = data.hubs;

            // Relocate robots to optimal centroids
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

            // Optional: visualize hubs on map
            if (window.mapManager) {
                window.mapManager.drawHubs(hubs);
            }

        } catch (e) {
            logEvent('❌ Optimization failed');
            addDispatchInsight(`Hub optimization error: ${e.message}`, CONFIG.UI.LOG_LEVELS.WARN);
        }
    }

    updateStats() {

        const el = id => document.getElementById(id);
        if (el('total-deliveries')) el('total-deliveries').textContent = this.totalDeliveries;
        if (el('total-distance')) el('total-distance').textContent = `${(this.totalDistance / 1000).toFixed(2)} km`;

        const avgBattery = this.robots.reduce((sum, r) => sum + r.battery, 0) / this.robots.length;
        if (el('avg-battery')) el('avg-battery').textContent = `${avgBattery.toFixed(0)}%`;

        const min = Math.floor(this.simulationTime / 60);
        const sec = Math.floor(this.simulationTime % 60);
        if (el('sim-time')) el('sim-time').textContent = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
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
                <div class="robot-detail">${robot.getStatusText()}</div>
                <div class="robot-detail">📦 ${robot.totalDeliveries} | ${robot.totalDistance.toFixed(0)}m | ⏱ ${robot.getEtaText()}</div>
                <div class="robot-detail">🎯 ${robot.routeMode || CONFIG.UI.STATE_LABELS.STANDBY} | 🔋 ${robot.battery.toFixed(0)}%</div>
                <div class="robot-detail">🧠 <strong>${robot.routeAlgorithm.toUpperCase()}</strong></div>
                <div class="battery-bar">
                    <div class="battery-fill" style="width:${robot.battery}%;background:${robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? CONFIG.ROBOT.COLORS.good : robot.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? CONFIG.ROBOT.COLORS.warn : CONFIG.ROBOT.COLORS.error}"></div>
                </div>
            `;
            container.appendChild(card);
        });
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
        const totalPathCostKm = stats.totalPathCost / 1000;
        const avgTimeMs = stats.routeCount > 0 ? stats.totalRouteTimeMs / stats.routeCount : 0;
        const avgNodes = stats.routeCount > 0 ? stats.totalNodesExplored / stats.routeCount : 0;

        const weights = CONFIG.SIMULATION.EFFICIENCY_WEIGHTS;
        const denominator = totalPathCostKm + (weights.TIME * avgTimeMs) + (weights.NODES * avgNodes) + (weights.REROUTE * stats.rerouteCount) + 1;
        return stats.deliveriesCompleted / denominator;
    }

    updateAlgorithmComparison() {
        const table = document.getElementById('algo-comparison-table');
        if (!table) return;

        const label = {
            astar: 'A*',
            dijkstra: 'Dijkstra',
            gbfs: 'GBFS'
        };

        const rows = CONFIG.SIMULATION.ALGORITHMS.map(algo => {
            const stats = this.algorithmStats[algo];
            const avgTimeMs = stats.routeCount > 0 ? stats.totalRouteTimeMs / stats.routeCount : 0;
            const avgNodes = stats.routeCount > 0 ? stats.totalNodesExplored / stats.routeCount : 0;
            const avgPathCost = stats.routeCount > 0 ? stats.totalPathCost / stats.routeCount : 0;
            const efficiency = this.calculateEfficiencyScore(stats);
            const isActive = algo === this.fleetAlgorithm;

            return `
                <tr style="background:${isActive ? CONFIG.UI.COLORS.infoLight : CONFIG.UI.COLORS.transparent};">
                    <td><strong>${label[algo]}</strong></td>
                    <td>${stats.deliveriesCompleted}</td>
                    <td>${avgTimeMs.toFixed(1)} ms</td>
                    <td>${avgNodes.toFixed(0)}</td>
                    <td>${avgPathCost.toFixed(0)} m</td>
                    <td>${stats.rerouteCount}</td>
                    <td><strong>${efficiency.toFixed(3)}</strong></td>
                </tr>
            `;
        }).join('');

        table.innerHTML = `
            <table style="width:100%;font-size:11px;border-collapse:collapse;">
                <thead>
                    <tr style="background:#f1f3f4;">
                        <th style="padding:6px;text-align:left;">Algorithm</th>
                        <th style="padding:6px;text-align:center;">Deliveries</th>
                        <th style="padding:6px;text-align:center;">Avg Time</th>
                        <th style="padding:6px;text-align:center;">Avg Nodes</th>
                        <th style="padding:6px;text-align:center;">Avg Cost</th>
                        <th style="padding:6px;text-align:center;">Reroutes</th>
                        <th style="padding:6px;text-align:center;">Efficiency</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `;

        const academicTable = document.getElementById('academic-algo-comparison-table');
        if (academicTable) {
            academicTable.innerHTML = table.innerHTML;
        }
    }

    updateLatestDecision() {
        const container = document.getElementById('latest-route-choice');
        if (!container) return;
        if (!this.latestDecision) {
            container.textContent = CONFIG.UI.STATE_LABELS.WAITING_ASSIGNMENT;
            return;
        }

        const d = this.latestDecision;
        container.innerHTML = `
            <div style="font-weight:700;color:#202124;margin-bottom:8px;">${d.robotName} → Order #${d.deliveryId}</div>
            <div style="font-size:11px;color:#5f6368;margin-bottom:8px;">${d.pickupName} → ${d.destinationName}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px;">
                <div>📏 Base: <strong>${d.breakdown.baseDistance.toFixed(0)}m</strong></div>
                <div>🚗 Traffic: <strong>+${d.breakdown.trafficPenalty.toFixed(0)}m</strong></div>
                <div>🌧️ Rain: <strong>+${d.breakdown.rainPenalty.toFixed(0)}m</strong></div>
                <div>🚧 Obstacles: <strong>+${d.breakdown.obstaclePenalty.toFixed(0)}m</strong></div>
                <div>⚠️ Battery risk: <strong>${d.batteryRisk.toFixed(1)}</strong></div>
                <div>⏱ ETA: <strong>${d.breakdown.estimatedMinutes.toFixed(1)} min</strong></div>
            </div>
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid ${CONFIG.UI.COLORS.neutral};font-size:11px;">
                <div>Priority score: <strong>${d.priorityScore.toFixed(1)}</strong></div>
                <div>Chosen total cost: <strong style="color:${CONFIG.ROBOT.COLORS.info};">${d.breakdown.totalCost.toFixed(0)}m</strong></div>
            </div>
        `;
    }

    updateAnalytics() {
        const setText = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        };
        const setBar = (id, pct) => {
            const el = document.getElementById(id);
            if (el) el.style.width = `${Math.max(6, Math.min(100, pct))}%`;
        };

        const simHours = Math.max(this.simulationTime / 3600, 0.01);
        const throughput = this.totalDeliveries / simHours;
        const queuePressure = this.pendingDeliveries.length;
        const avgEnergyPerDelivery = this.totalDeliveries > 0 ? this.totalBatteryConsumed / this.totalDeliveries : this.totalBatteryConsumed;

        setText('metric-throughput', `${throughput.toFixed(1)}/hr`);
        setText('metric-queue-pressure', `${queuePressure} waiting`);
        setText('metric-reroutes', `${this.totalReroutes}`);
        setText('metric-energy', `${avgEnergyPerDelivery.toFixed(1)}%/job`);
        setText('metric-decision-cost', `${this.lastDecisionCost.toFixed(0)} m`);

        setBar('bar-throughput', throughput * CONFIG.SIMULATION.BAR_SCALES.THROUGHPUT);
        setBar('bar-queue-pressure', queuePressure * CONFIG.SIMULATION.BAR_SCALES.QUEUE);
        setBar('bar-reroutes', this.totalReroutes * CONFIG.SIMULATION.BAR_SCALES.REROUTE);
        setBar('bar-energy', avgEnergyPerDelivery * CONFIG.SIMULATION.BAR_SCALES.ENERGY);
        setBar('bar-decision-cost', this.lastDecisionCost / CONFIG.SIMULATION.BAR_SCALES.COST);
    }

}
