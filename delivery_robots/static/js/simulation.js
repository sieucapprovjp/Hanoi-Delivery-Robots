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
        this.deliveryInterval = 6500;
        this.totalReroutes = 0;
        this.totalBatteryConsumed = 0;
        this.lastDecisionCost = 0;
        this.latestDecision = null;
        this.fleetAlgorithm = 'astar';
        this.algorithmStats = {
            astar: this.createAlgoStats(),
            dijkstra: this.createAlgoStats(),
            gbfs: this.createAlgoStats()
        };
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

        const [startA, startB, startC, startD, startE] = await Promise.all([
            pathfindingManager.snapToRoad(21.0285, 105.8542),
            pathfindingManager.snapToRoad(21.0355, 105.8516),
            pathfindingManager.snapToRoad(21.0240, 105.8480),
            pathfindingManager.snapToRoad(21.0220, 105.8510),
            pathfindingManager.snapToRoad(21.0300, 105.8530)
        ]);

        // Robots
        this.robots = [
            new DeliveryRobot(0, startA.lat, startA.lon, 'Robot α', '#4285f4', this.fleetAlgorithm),
            new DeliveryRobot(1, startB.lat, startB.lon, 'Robot β', '#34a853', this.fleetAlgorithm),
            new DeliveryRobot(2, startC.lat, startC.lon, 'Robot γ', '#fbbc04', this.fleetAlgorithm),
            new DeliveryRobot(3, startD.lat, startD.lon, 'Robot δ', '#ff6b6b', this.fleetAlgorithm),
            new DeliveryRobot(4, startE.lat, startE.lon, 'Robot ε', '#845ef7', this.fleetAlgorithm)
        ];

        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        // Initial deliveries
        for (let i = 0; i < 6; i++) {
            await this.generateDelivery();
        }

        console.log('✓ Ready - Click START!');
        logEvent('🚀 Click START to begin!');
        addDispatchInsight('Dispatch engine online. Monitoring queue pressure, weather, and traffic.', 'neutral');
        this.updateFleetAlgorithmLabel();
        this.updateAlgorithmComparison();
    }

    setFleetAlgorithm(algo) {
        const normalized = (algo || '').toLowerCase();
        if (!['astar', 'dijkstra', 'gbfs'].includes(normalized)) return;

        this.fleetAlgorithm = normalized;
        this.algorithmStats = {
            astar: this.createAlgoStats(),
            dijkstra: this.createAlgoStats(),
            gbfs: this.createAlgoStats()
        };

        this.robots.forEach(robot => {
            robot.routeAlgorithm = normalized;
            if (robot.currentDelivery && robot.status === 'moving') {
                robot.currentDeliveryAlgorithm = normalized;
            }
        });

        this.updateFleetAlgorithmLabel();
        this.updateRobotStatus();
        this.updateAlgorithmComparison();
        logEvent(`🧠 Fleet AI switched to ${normalized.toUpperCase()} for all robots`);
        addDispatchInsight(`Fleet benchmark mode: all 5 robots now use ${normalized.toUpperCase()}. Metrics reset for fair comparison.`, 'neutral');
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
        const baseLocations = [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Lake", category: "landmark", icon: "📍" },
            { lat: 21.0355, lon: 105.8516, name: "Dong Xuan Market", category: "market", icon: "🛍" },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien Plaza", category: "retail", icon: "🛒" },
            { lat: 21.0275, lon: 105.8520, name: "Opera House", category: "office", icon: "🏛" },
            { lat: 21.0220, lon: 105.8510, name: "Ly Thuong Kiet Residences", category: "residential", icon: "🏠" },
            { lat: 21.0300, lon: 105.8530, name: "Hang Ngang Shops", category: "retail", icon: "🛍" },
            { lat: 21.0318, lon: 105.8524, name: "Ngoc Son Gate", category: "landmark", icon: "📍" },
            { lat: 21.0334, lon: 105.8509, name: "Ta Hien Bistro Row", category: "restaurant", icon: "🍜" },
            { lat: 21.0268, lon: 105.8496, name: "Hang Trong Studios", category: "office", icon: "🏢" },
            { lat: 21.0235, lon: 105.8504, name: "Melia Hanoi", category: "hotel", icon: "🏨" },
            { lat: 21.0294, lon: 105.8555, name: "Water Puppet Theatre", category: "landmark", icon: "🎭" },
            { lat: 21.0248, lon: 105.8528, name: "French Quarter Cafe", category: "restaurant", icon: "☕" },
            { lat: 21.0271, lon: 105.8558, name: "Post Office Square", category: "office", icon: "🏢" },
            { lat: 21.0343, lon: 105.8522, name: "Hang Dao Market", category: "market", icon: "🛍" },
            { lat: 21.0218, lon: 105.8499, name: "Thong Nhat Apartments", category: "residential", icon: "🏠" },
            { lat: 21.0298, lon: 105.8515, name: "Pho Cau Go Dining", category: "restaurant", icon: "🍲" },
            { lat: 21.0257, lon: 105.8544, name: "Ba Kieu Temple", category: "landmark", icon: "⛩" },
            { lat: 21.0326, lon: 105.8517, name: "Old Quarter Hostel", category: "hotel", icon: "🛎" },
            { lat: 21.0261, lon: 105.8517, name: "Press Club Offices", category: "office", icon: "🏢" },
            { lat: 21.0230, lon: 105.8522, name: "Tran Hung Dao Homes", category: "residential", icon: "🏡" }
        ];
        const locations = await Promise.all(
            baseLocations.map(async location => {
                const snapped = await pathfindingManager.snapToRoad(location.lat, location.lon);
                return { ...location, lat: snapped.lat, lon: snapped.lon };
            })
        );
        const pickupGroups = {
            restaurant: 0.24,
            market: 0.22,
            retail: 0.18,
            office: 0.14,
            hotel: 0.12,
            landmark: 0.06,
            residential: 0.04
        };
        const dropoffGroups = {
            residential: 0.32,
            hotel: 0.18,
            office: 0.16,
            retail: 0.12,
            restaurant: 0.10,
            landmark: 0.07,
            market: 0.05
        };

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
            dropoffCategory = 'residential';
            dest = randomLocationForCategory(dropoffCategory, pickup.name);
        }

        const delivery = {
            id: this.totalDeliveries + this.pendingDeliveries.length + 1,
            pickup: pickup,
            destination: dest,
            status: 'pending',
            createdAt: Date.now(),
            theme: {
                pickupCategory,
                dropoffCategory,
                pickupIcon: pickup.icon,
                dropoffIcon: dest.icon
            },
            priorityScore: 0
        };

        delivery.priorityScore = this.calculatePriorityScore(delivery);
        this.pendingDeliveries.push(delivery);

        // 🧠 Log delivery coordinates for k-means optimization
        this.logDeliveryData(delivery);
    }

    async logDeliveryData(delivery) {
        try {
            await fetch('/api/log_delivery', {
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

        for (let i = this.pendingDeliveries.length - 1; i >= 0; i--) {
            this.pendingDeliveries.forEach(delivery => {
                delivery.priorityScore = this.calculatePriorityScore(delivery);
            });
            this.pendingDeliveries.sort((a, b) => b.priorityScore - a.priorityScore);

            const delivery = this.pendingDeliveries[i];
            const candidateRobots = this.robots.filter(r => r.status === 'idle' && r.currentLoad < r.capacity && !r.isRouting);

            if (candidateRobots.length > 0) {
                const best = await this.chooseBestRobotForDelivery(candidateRobots, delivery);
                if (!best) continue;

                this.lastDecisionCost = best.totalScore;
                this.latestDecision = {
                    robotName: best.robot.name,
                    deliveryId: delivery.id,
                    priorityScore: delivery.priorityScore,
                    batteryRisk: best.batteryRisk,
                    totalScore: best.totalScore,
                    breakdown: best.breakdown,
                    pickupName: delivery.pickup.name,
                    destinationName: delivery.destination.name
                };
                addDispatchInsight(
                    `${best.robot.name} assigned to order #${delivery.id} with priority ${delivery.priorityScore.toFixed(1)}. Cost breakdown: base ${best.breakdown.baseDistance.toFixed(0)}m, traffic +${best.breakdown.trafficPenalty.toFixed(0)}m, rain +${best.breakdown.rainPenalty.toFixed(0)}m, obstacles +${best.breakdown.obstaclePenalty.toFixed(0)}m, battery risk +${best.batteryRisk.toFixed(1)}.`,
                    'good'
                );
                const assigned = await best.robot.assignDelivery(delivery);
                if (assigned) {
                    this.pendingDeliveries.splice(i, 1);
                }
            }
        }
    }

    async update() {
        if (!this.running) return;

        this.simulationTime += 0.016 * this.speed;

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
        this.algorithmStats = {
            astar: this.createAlgoStats(),
            dijkstra: this.createAlgoStats(),
            gbfs: this.createAlgoStats()
        };
        
        const [startA, startB, startC, startD, startE] = await Promise.all([
            pathfindingManager.snapToRoad(21.0285, 105.8542),
            pathfindingManager.snapToRoad(21.0355, 105.8516),
            pathfindingManager.snapToRoad(21.0240, 105.8480),
            pathfindingManager.snapToRoad(21.0220, 105.8510),
            pathfindingManager.snapToRoad(21.0300, 105.8530)
        ]);
        const starts = [startA, startB, startC, startD, startE];
        
        this.robots.forEach((robot, i) => {
            robot.lat = starts[i].lat;
            robot.lon = starts[i].lon;
            robot.battery = 100;
            robot.status = 'idle';
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
 
        for (let i = 0; i < 6; i++) await this.generateDelivery();
 
        logEvent('🔄 Reset');
        addDispatchInsight('Dispatch state reset. Queue rebuilt and analytics cleared.', 'neutral');
        this.updateStats();
        this.updateFleetAlgorithmLabel();
        this.updateRobotStatus();
        this.updateAnalytics();
        this.updateLatestDecision();
        this.updateAlgorithmComparison();
    }

    async optimizeHubs() {
        logEvent('🧠 Optimizing hub locations...');
        addDispatchInsight('Running k-means clustering on delivery hotspots to reposition fleet...', 'neutral');
        
        try {
            const res = await fetch('/api/optimize-hubs', { method: 'POST' });
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.error || 'Optimization failed');
            
            const hubs = data.hubs;
            
            // Relocate robots to optimal centroids
            this.robots.forEach((robot, i) => {
                if (i < hubs.length) {
                    const hub = hubs[i];
                    robot.lat = hub.lat;
                    robot.lon = hub.lon;
                    robot.status = 'idle';
                    robot.currentPath = [];
                    robot.clearPathLine();
                    if (robot.marker) robot.marker.setLatLng([robot.lat, robot.lon]);
                }
            });
            
            logEvent('✅ Hubs optimized!');
            addDispatchInsight(`Fleet repositioned to ${hubs.length} optimal centroids. Check map for new starting points.`, 'good');
            
            // Optional: visualize hubs on map
            if (window.mapManager) {
                window.mapManager.drawHubs(hubs);
            }
            
        } catch (e) {
            logEvent('❌ Optimization failed');
            addDispatchInsight(`Hub optimization error: ${e.message}`, 'warn');
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
        if (el('sim-time')) el('sim-time').textContent = `${String(min).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
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
                <div class="robot-detail">🎯 ${robot.routeMode || 'standby'} | 🔋 ${robot.battery.toFixed(0)}%</div>
                <div class="robot-detail">🧠 <strong>${robot.routeAlgorithm.toUpperCase()}</strong></div>
                <div class="battery-bar">
                    <div class="battery-fill" style="width:${robot.battery}%;background:${robot.battery>60?'#34a853':robot.battery>30?'#fbbc04':'#ea4335'}"></div>
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

        const denominator = totalPathCostKm + (0.02 * avgTimeMs) + (0.005 * avgNodes) + (0.5 * stats.rerouteCount) + 1;
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

        const rows = ['astar', 'dijkstra', 'gbfs'].map(algo => {
            const stats = this.algorithmStats[algo];
            const avgTimeMs = stats.routeCount > 0 ? stats.totalRouteTimeMs / stats.routeCount : 0;
            const avgNodes = stats.routeCount > 0 ? stats.totalNodesExplored / stats.routeCount : 0;
            const avgPathCost = stats.routeCount > 0 ? stats.totalPathCost / stats.routeCount : 0;
            const efficiency = this.calculateEfficiencyScore(stats);
            const isActive = algo === this.fleetAlgorithm;

            return `
                <tr style="background:${isActive ? '#e8f0fe' : 'transparent'};">
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
            container.textContent = 'Waiting for a robot assignment...';
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
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid #e0e0e0;font-size:11px;">
                <div>Priority score: <strong>${d.priorityScore.toFixed(1)}</strong></div>
                <div>Chosen total cost: <strong style="color:#1a73e8;">${d.breakdown.totalCost.toFixed(0)}m</strong></div>
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

        setBar('bar-throughput', throughput * 4);
        setBar('bar-queue-pressure', queuePressure * 6);
        setBar('bar-reroutes', this.totalReroutes * 8);
        setBar('bar-energy', avgEnergyPerDelivery * 18);
        setBar('bar-decision-cost', this.lastDecisionCost / 40);
    }

    calculatePriorityScore(delivery) {
        const waitMinutes = (Date.now() - delivery.createdAt) / 60000;
        const pickupWeights = {
            restaurant: 9,
            market: 7,
            retail: 6,
            office: 5,
            hotel: 5,
            landmark: 3,
            residential: 4
        };
        const dropWeights = {
            residential: 8,
            hotel: 6,
            office: 5,
            retail: 4,
            restaurant: 4,
            landmark: 2,
            market: 3
        };

        return (
            (pickupWeights[delivery.theme.pickupCategory] || 4) +
            (dropWeights[delivery.theme.dropoffCategory] || 4) +
            waitMinutes * 2.8
        );
    }

    async chooseBestRobotForDelivery(robots, delivery) {
        let best = null;

        for (const robot of robots) {
            try {
                const route = await pathfindingManager.getRoute(
                    robot.lat,
                    robot.lon,
                    delivery.pickup.lat,
                    delivery.pickup.lon,
                    robot.roadMemory,
                    robot.routeAlgorithm
                );
                const breakdown = pathfindingManager.estimateRouteCost(route);
                const batteryRisk = robot.estimateBatteryRisk(breakdown.totalCost);
                const totalScore = breakdown.totalCost + batteryRisk * 120 - delivery.priorityScore * 18;

                if (!best || totalScore < best.totalScore) {
                    best = {
                        robot,
                        route,
                        breakdown,
                        batteryRisk,
                        totalScore
                    };
                }
            } catch (error) {
                console.error(error);
            }
        }

        return best;
    }
}
