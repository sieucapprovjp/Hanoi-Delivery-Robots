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
        this.schedulingAlgorithm = 'priority'; // 'fifo', 'priority', 'nearest'
        this.algorithmStats = {
            fifo: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
            priority: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
            nearest: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
        };
    }

    async initialize() {
        // Map
        pathfindingManager = new Pathfinding();
        mapManager = new HanoiMap();
        mapManager.initializeMap();

        const [startA, startB, startC, startD, startE] = await Promise.all([
            pathfindingManager.snapToRoad(21.0285, 105.8542),
            pathfindingManager.snapToRoad(21.0355, 105.8516),
            pathfindingManager.snapToRoad(21.0240, 105.8480),
            pathfindingManager.snapToRoad(21.0220, 105.8510),
            pathfindingManager.snapToRoad(21.0300, 105.8530)
        ]);

        // Robots
        this.robots = [
            new DeliveryRobot(0, startA.lat, startA.lon, 'Robot α', '#4285f4'),
            new DeliveryRobot(1, startB.lat, startB.lon, 'Robot β', '#34a853'),
            new DeliveryRobot(2, startC.lat, startC.lon, 'Robot γ', '#fbbc04'),
            new DeliveryRobot(3, startD.lat, startD.lon, 'Robot δ', '#ff6b6b'),
            new DeliveryRobot(4, startE.lat, startE.lon, 'Robot ε', '#845ef7')
        ];

        this.robots.forEach(robot => robot.createMarker(mapManager.map));

        // Initial deliveries
        for (let i = 0; i < 6; i++) {
            await this.generateDelivery();
        }

        console.log('✓ Ready - Click START!');
        logEvent('🚀 Click START to begin!');
        addDispatchInsight('Dispatch engine online. Monitoring queue pressure, weather, and traffic.', 'neutral');
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
        this.updateDeliveryQueue();
    }

    async assignDeliveries() {
        // Sort pending deliveries based on scheduling algorithm
        let sortedDeliveries = [...this.pendingDeliveries];
        
        if (this.schedulingAlgorithm === 'fifo') {
            // First-Come-First-Serve: keep original order
            sortedDeliveries.sort((a, b) => a.timestamp - b.timestamp);
        } else if (this.schedulingAlgorithm === 'priority') {
            // Priority-based: highest priority first
            sortedDeliveries.forEach(delivery => {
                delivery.priorityScore = this.calculatePriorityScore(delivery);
            });
            sortedDeliveries.sort((a, b) => b.priorityScore - a.priorityScore);
        } else if (this.schedulingAlgorithm === 'nearest') {
            // Nearest-First: closest deliveries first
            sortedDeliveries.forEach(delivery => {
                const avgDist = this.robots.reduce((sum, r) => {
                    return sum + this.haversineDistance(r.lat, r.lon, delivery.pickup.lat, delivery.pickup.lon);
                }, 0) / this.robots.length;
                delivery.priorityScore = -avgDist; // Negative so nearest comes first
            });
            sortedDeliveries.sort((a, b) => b.priorityScore - a.priorityScore);
        }

        for (let i = sortedDeliveries.length - 1; i >= 0; i--) {
            const delivery = sortedDeliveries[i];
            const candidateRobots = this.robots.filter(r => r.status === 'idle' && r.currentLoad < r.capacity && !r.isRouting);

            if (candidateRobots.length > 0) {
                const best = await this.chooseBestRobotForDelivery(candidateRobots, delivery);
                if (!best) continue;

                this.lastDecisionCost = best.totalScore;
                const algoName = this.schedulingAlgorithm.toUpperCase();
                addDispatchInsight(
                    `[${algoName}] ${best.robot.name} assigned to order #${delivery.id}. Cost: ${best.totalScore.toFixed(0)}m`,
                    'good'
                );
                const assigned = await best.robot.assignDelivery(delivery);
                if (assigned) {
                    const idx = this.pendingDeliveries.findIndex(d => d.id === delivery.id);
                    if (idx !== -1) {
                        this.pendingDeliveries.splice(idx, 1);
                    }
                    // Track algorithm stats
                    this.algorithmStats[this.schedulingAlgorithm].deliveries++;
                    this.algorithmStats[this.schedulingAlgorithm].totalDistance += best.totalScore;
                }
            }
        }
    }

    haversineDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const phi1 = Math.radians(lat1);
        const phi2 = Math.radians(lat2);
        const deltaPhi = Math.radians(lat2 - lat1);
        const deltaLambda = Math.radians(lon2 - lon1);
        const a = Math.sin(deltaPhi/2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda/2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
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
        this.algorithmStats = {
            fifo: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
            priority: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
            nearest: { deliveries: 0, avgDistance: 0, totalDistance: 0 },
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
            robot.isRouting = false;
            robot.clearPathLine();
            if (robot.marker) robot.marker.setLatLng([robot.lat, robot.lon]);
        });

        for (let i = 0; i < 6; i++) await this.generateDelivery();
        
        logEvent('🔄 Reset');
        addDispatchInsight('Dispatch state reset. Queue rebuilt and analytics cleared.', 'neutral');
        this.updateStats();
        this.updateRobotStatus();
        this.updateAnalytics();
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
                <div class="robot-detail">📦 ${robot.totalDeliveries} | ${robot.totalDistance.toFixed(0)}m</div>
                <div class="battery-bar">
                    <div class="battery-fill" style="width:${robot.battery}%;background:${robot.battery>60?'#34a853':robot.battery>30?'#fbbc04':'#ea4335'}"></div>
                </div>
            `;
            container.appendChild(card);
        });
    }

    updateDeliveryQueue() {
        const container = document.getElementById('delivery-queue');
        if (!container) return;
        
        container.innerHTML = '';

        this.pendingDeliveries.slice(0, 10).forEach(d => {
            const item = document.createElement('div');
            item.className = 'delivery-item';
            item.innerHTML = `
                <div class="delivery-id">Order #${d.id} <span class="delivery-priority">Priority ${d.priorityScore.toFixed(1)}</span></div>
                <div class="delivery-route">
                    <span class="delivery-stop pickup">${d.theme?.pickupIcon || '📦'} Pickup ${d.pickup.name}</span>
                    <span class="delivery-arrow">→</span>
                    <span class="delivery-stop dropoff">${d.theme?.dropoffIcon || '📍'} Drop ${d.destination.name}</span>
                </div>
            `;
            container.appendChild(item);
        });
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

    updateAlgorithmComparison() {
        const container = document.getElementById('algorithm-comparison');
        if (!container) return;

        const stats = this.algorithmStats;
        container.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 8px;">
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #5f6368;">FIFO</div>
                    <div style="font-size: 18px; font-weight: 700; color: #1a73e8;">${stats.fifo.deliveries}</div>
                    <div style="font-size: 10px; color: #5f6368;">${stats.fifo.totalDistance.toFixed(0)}m</div>
                </div>
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #5f6368;">Priority</div>
                    <div style="font-size: 18px; font-weight: 700; color: #34a853;">${stats.priority.deliveries}</div>
                    <div style="font-size: 10px; color: #5f6368;">${stats.priority.totalDistance.toFixed(0)}m</div>
                </div>
                <div style="background: #f8f9fa; padding: 8px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #5f6368;">Nearest</div>
                    <div style="font-size: 18px; font-weight: 700; color: #ea4335;">${stats.nearest.deliveries}</div>
                    <div style="font-size: 10px; color: #5f6368;">${stats.nearest.totalDistance.toFixed(0)}m</div>
                </div>
            </div>
        `;
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
                const route = await pathfindingManager.getRoute(robot.lat, robot.lon, delivery.pickup.lat, delivery.pickup.lon);
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
