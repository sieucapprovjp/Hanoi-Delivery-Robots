// Simple working robot
class DeliveryRobot {
    constructor(id, lat, lon, name, color, routeAlgorithm = 'astar') {
        this.id = id;
        this.lat = lat;
        this.lon = lon;
        this.name = name;
        this.color = color;
        this.speed = CONFIG.ROBOT.DEFAULT_SPEED;
        this.battery = CONFIG.ROBOT.INITIAL_BATTERY;
        this.batteryDrain = CONFIG.ROBOT.BATTERY_DRAIN;
        this.capacity = CONFIG.ROBOT.CAPACITY;
        this.currentLoad = 0;
        this.status = CONFIG.ROBOT.STATUSES.IDLE;
        this.currentPath = [];
        this.pathIndex = 0;
        this.currentDelivery = null;
        this.totalDeliveries = 0;
        this.totalDistance = 0;
        this.marker = null;
        this._calcHistory = [];
        this.pathLine = null;
        this.chargingStation = null;
        this.speedMultiplier = 1;
        this.isRouting = false;
        this.routeMode = null;
        this.routeDeliveryId = null;
        this.routeTarget = null;
        this.lastRerouteAt = 0;
        this.deliveryPhase = null;
        this.resumeAfterCharge = false;
        this.lastRouteBreakdown = null;
        this.lastRouteEtaMinutes = 0;
        this.routeAlgorithm = routeAlgorithm;
        this.currentDeliveryAlgorithm = null;

        // 🧠 Road memory system (Q-learning lite)
        this.roadMemory = {};
        this.memoryDecay = CONFIG.ROBOT.MEMORY_DECAY;
        this._frameCount = 0;
    }

    recordRoadExperience(fromLat, fromLon, toLat, toLon, speedMultiplier) {
        const key = `${fromLat.toFixed(4)},${fromLon.toFixed(4)}->${toLat.toFixed(4)},${toLon.toFixed(4)}`;
        const currentPenalty = this.roadMemory[key] || 1.0;
        const penalties = CONFIG.ROBOT.EXPERIENCE_PENALTIES;
        const thresholds = CONFIG.ROBOT.EXPERIENCE_THRESHOLDS;
        const experiencedPenalty = speedMultiplier < thresholds.heavy ? penalties.heavy : speedMultiplier < thresholds.moderate ? penalties.moderate : penalties.light;
        this.roadMemory[key] = currentPenalty * CONFIG.ROBOT.MEMORY_UPDATE_WEIGHT + experiencedPenalty * (1 - CONFIG.ROBOT.MEMORY_UPDATE_WEIGHT);
    }

    decayMemory() {
        for (const key in this.roadMemory) {
            this.roadMemory[key] = this.roadMemory[key] * this.memoryDecay + 1.0 * (1 - this.memoryDecay);
            if (Math.abs(this.roadMemory[key] - 1.0) < CONFIG.ROBOT.MEMORY_CLEANUP_THRESHOLD) delete this.roadMemory[key];
        }
    }

    update() {
        if (this.status !== CONFIG.ROBOT.STATUSES.MOVING) return;

        if (this.currentPath.length === 0 || this.pathIndex >= this.currentPath.length - 1) {
            this.arriveAtWaypoint();
            return;
        }

        const target = this.currentPath[this.pathIndex + 1];
        const dist = this.distanceTo(target);

        if (dist < this.speed * this.speedMultiplier) {
            this.lat = target.lat;
            this.lon = target.lon;
            this.pathIndex++;

            if (this.pathIndex >= this.currentPath.length - 1) {
                this.arriveAtWaypoint();
            }
        } else {
            const ratio = (this.speed * this.speedMultiplier) / dist;
            this.lat += (target.lat - this.lat) * ratio;
            this.lon += (target.lon - this.lon) * ratio;
            this.totalDistance += this.speed * this.speedMultiplier * CONFIG.ROBOT.METERS_PER_DEGREE; // to meters
        }

        // Battery
        const rainPenalty = mapManager.getRainPenaltyAt(this.lat, this.lon);
        this.battery -= this.batteryDrain * rainPenalty;

        // Check traffic
        const traffic = mapManager.getTrafficAt(this.lat, this.lon);
        this.speedMultiplier = Math.max(
            CONFIG.ROBOT.MIN_SPEED_MULTIPLIER,
            (CONFIG.ROBOT.BASE_SPEED_MULTIPLIER * (1 - traffic * CONFIG.ROBOT.TRAFFIC_IMPACT_FACTOR)) / rainPenalty
        );

        // 🧠 Record road experience for learning
        this._frameCount++;
        if (this.pathIndex + 1 < this.currentPath.length && this._frameCount % CONFIG.ROBOT.FRAME_COUNT_RECORD_MEMORY === 0) {
            const from = this.currentPath[this.pathIndex];
            const to = this.currentPath[this.pathIndex + 1];
            this.recordRoadExperience(from.lat, from.lon, to.lat, to.lon, this.speedMultiplier);
        }
        // Decay memory every ~5 seconds (300 frames at 60fps)
        if (this._frameCount % CONFIG.ROBOT.FRAME_COUNT_DECAY_MEMORY === 0) this.decayMemory();

        this.maybeReroute(traffic, rainPenalty);

        // Update marker
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
            if (this.marker.isPopupOpen()) this.updatePopup();
        }

        // Check if need charging
        if (this.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD && this.status === CONFIG.ROBOT.STATUSES.MOVING && !this.isRouting && this.routeMode !== CONFIG.ROBOT.ROUTE_MODES.CHARGING) {
            this.goCharge();
        }

        // Check if arrived at charging
        if (this.status === CONFIG.ROBOT.STATUSES.MOVING && this.chargingStation) {
            const distToCharge = this.distanceTo(this.chargingStation);
            if (distToCharge < CONFIG.ROBOT.CHARGING_ARRIVAL_THRESHOLD) {
                this.startCharging();
            }
        }
    }

    async arriveAtWaypoint() {
        if (this.isRouting) return;
        this.isRouting = true;

        try {
            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING && this.chargingStation) {
                this.startCharging();
                return;
            }

            if (this.currentDelivery && this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) {
                this.deliveryPhase = CONFIG.ROBOT.PHASES.TO_DROPOFF;
                this.routeTarget = {
                    lat: this.currentDelivery.destination.lat,
                    lon: this.currentDelivery.destination.lon
                };
                logEvent(`📍 ${this.name} picked up order #${this.currentDelivery.id}`);
                addDispatchInsight(`${this.name} completed pickup and is now committing to the final dropoff leg.`, CONFIG.UI.LOG_LEVELS.SUCCESS);
                await this.buildRouteToTarget(this.currentDelivery.destination.lat, this.currentDelivery.destination.lon);
                return;
            }

            if (this.currentDelivery && this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) {
                this.currentLoad--;
                this.totalDeliveries++;
                if (typeof simulation !== 'undefined' && simulation && typeof simulation.recordDeliveryCompleted === 'function') {
                    simulation.recordDeliveryCompleted(this.currentDeliveryAlgorithm || this.routeAlgorithm);
                }
                logEvent(`✅ ${this.name} completed delivery #${this.currentDelivery.id}`);
                mapManager.clearDeliveryMarkers(this.currentDelivery.id);
                this.currentDelivery = null;
                this.currentDeliveryAlgorithm = null;
            }

            this.status = CONFIG.ROBOT.STATUSES.IDLE;
            this.currentPath = [];
            this.pathIndex = 0;
            this.routeMode = null;
            this.routeDeliveryId = null;
            this.routeTarget = null;
            this.deliveryPhase = null;
            this.clearPathLine();
        } finally {
            this.isRouting = false;
        }
    }

    async goCharge() {
        const station = mapManager.chargingStations
            .filter(s => s.availableSpots > 0)
            .sort((a, b) => this.distanceTo(a) - this.distanceTo(b))[0];
        if (!station) return;
        if (this.isRouting) return;

        this.isRouting = true;
        this.resumeAfterCharge = this.routeMode === CONFIG.ROBOT.ROUTE_MODES.DELIVERY && !!this.currentDelivery;
        this.chargingStation = station;
        mapManager.occupyChargingSpot(station);

        try {
            this.routeMode = CONFIG.ROBOT.ROUTE_MODES.CHARGING;
            this.routeTarget = { lat: station.lat, lon: station.lon };
            this.routeDeliveryId = null;
            await this.buildRouteToTarget(station.lat, station.lon);
            logEvent(`⚡ ${this.name} → ${station.name}`);
            addDispatchInsight(`${this.name} is diverting to nearest charger ${station.name} because battery dropped below ${CONFIG.ROBOT.BATTERY_LOW_THRESHOLD}%.`, CONFIG.UI.LOG_LEVELS.WARN);
        } catch (error) {
            mapManager.releaseChargingSpot(station);
            this.chargingStation = null;
            logEvent(`❌ ${this.name} could not route to ${station.name}`);
            console.error(error);
        } finally {
            this.isRouting = false;
        }
    }

    startCharging() {
        this.status = CONFIG.ROBOT.STATUSES.CHARGING;
        logEvent(`🔌 ${this.name} charging`);

        const charge = setInterval(() => {
            this.battery += CONFIG.ROBOT.BATTERY_CHARGE_INCREMENT;
            if (this.battery >= CONFIG.ROBOT.BATTERY_CHARGE_TARGET) {
                this.battery = CONFIG.ROBOT.BATTERY_CHARGE_TARGET;
                clearInterval(charge);
                if (this.chargingStation) {
                    mapManager.releaseChargingSpot(this.chargingStation);
                    this.chargingStation = null;
                }
                logEvent(`⚡ ${this.name} charged and ready`);
                this.finishCharging();
            }
        }, CONFIG.ROBOT.CHARGING_INTERVAL_MS);
    }

    async assignDelivery(delivery, precalculatedRoute = null, precalculatedBreakdown = null) {
        if (this.isRouting) return false;

        this.isRouting = true;
        this.currentDelivery = delivery;
        this.currentDeliveryAlgorithm = this.routeAlgorithm;
        this.currentLoad++;
        this.deliveryPhase = CONFIG.ROBOT.PHASES.TO_PICKUP;
        mapManager.showDeliveryMarkers(delivery);

        try {
            this.routeMode = CONFIG.ROBOT.ROUTE_MODES.DELIVERY;
            this.routeDeliveryId = delivery.id;
            this.routeTarget = { lat: delivery.pickup.lat, lon: delivery.pickup.lon };
            this.lastRerouteAt = Date.now();
            await this.buildRouteToTarget(delivery.pickup.lat, delivery.pickup.lon, precalculatedRoute, precalculatedBreakdown);

            logEvent(`📦 ${this.name} → ${delivery.pickup.name} → ${delivery.destination.name}`);
            addDispatchInsight(`${this.name} selected a low-cost route that balances distance with current rain and congestion exposure.`, CONFIG.UI.LOG_LEVELS.NEUTRAL);
            return true;
        } catch (error) {
            this.currentDelivery = null;
            this.currentDeliveryAlgorithm = null;
            this.currentLoad = Math.max(0, this.currentLoad - 1);
            mapManager.clearDeliveryMarkers(delivery.id);
            logEvent(`❌ ${this.name} could not route delivery #${delivery.id}`);
            console.error(error);
            return false;
        } finally {
            this.isRouting = false;
        }
    }

    removeMarker() {
        if (this.marker) {
            this.marker.remove();
            this.marker = null;
        }
        this.clearPathLine();
    }

    createMarker(map) {
        this.removeMarker();

        this.marker = L.marker([this.lat, this.lon], {
            icon: L.divIcon({
                html: `<div class="robot-marker-icon" style="--robot-color: ${this.color}">🤖</div>`,
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }),
            zIndexOffset: 1000
        }).addTo(map);

        this.marker.bindPopup('Loading...');
        this.marker.on('click', () => {
            this.updatePopup();
            this.marker.openPopup();
            
            // Sync with Alpine store for Computing panel
            const store = Alpine.store('sim');
            if (store) {
                store.computing.robotId = this.id;
                store.computing.details = this.getComputingDetails();
            }
        });
    }

    updatePopup() {
        const batteryClass = this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? 'battery-good' : this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? 'battery-warn' : 'battery-error';

        let decisionState = CONFIG.UI.STATE_LABELS.IDLE;
        if (this.status === CONFIG.ROBOT.STATUSES.MOVING) {
            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING) decisionState = CONFIG.UI.STATE_LABELS.CHARGING;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_PICKUP;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_DROPOFF;
            else decisionState = CONFIG.UI.STATE_LABELS.MOVING;
        }
        if (this.isRouting) decisionState = CONFIG.UI.STATE_LABELS.REROUTING;
        if (this.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD && this.status !== CONFIG.ROBOT.STATUSES.CHARGING) decisionState = CONFIG.UI.STATE_LABELS.LOW_BATTERY;

        const content = `
            <div class="robot-popup">
                <div class="popup-title" style="--robot-color: ${this.color}">🤖 ${this.name}</div>
                
                <div class="popup-status-badge ${this.isRouting ? 'status-warn' : this.status === CONFIG.ROBOT.STATUSES.MOVING ? 'status-success' : 'status-neutral'}">
                    ${decisionState}
                </div>

                <div class="popup-grid-3">
                    <div class="grid-item"><div class="item-label">Speed</div><div class="item-value">${(this.speedMultiplier * 100).toFixed(0)}%</div></div>
                    <div class="grid-item"><div class="item-label">Battery</div><div class="item-value ${batteryClass}">${this.battery.toFixed(1)}%</div></div>
                    <div class="grid-item"><div class="item-label">Drain</div><div class="item-value">${this.batteryDrain.toFixed(3)}/s</div></div>
                </div>

                <div class="popup-grid-2">
                    <div class="grid-item"><div class="item-label">Completed</div><div class="item-value color-success">${this.totalDeliveries}</div></div>
                    <div class="grid-item"><div class="item-label">Distance</div><div class="item-value color-primary">${this.totalDistance.toFixed(0)}m</div></div>
                </div>

                ${this.routeTarget ? `<div class="popup-info-box status-success">🎯 ${this.routeTarget.lat.toFixed(4)}, ${this.routeTarget.lon.toFixed(4)}<br>${this.currentPath.length - this.pathIndex} waypoints left<br>⏱ ETA ${this.getEtaText()}</div>` : ''}
                
                ${this.currentDelivery ? `<div class="popup-info-box status-neutral"><div class="item-label">📦 Order #${this.currentDelivery.id}</div><div class="item-value">${this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP ? '🔵 Going to pickup' : '🔴 Going to deliver'}</div></div>` : '<div class="popup-info-box status-neutral">No delivery</div>'}
            </div>
        `;

        const popup = this.marker.getPopup();
        if (popup) popup.setContent(content);
    }

    getComputingDetails() {
        const batteryClass = this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? 'battery-good' : this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? 'battery-warn' : 'battery-error';

        let decisionState = CONFIG.UI.STATE_LABELS.IDLE;
        if (this.status === CONFIG.ROBOT.STATUSES.MOVING) {
            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING) decisionState = CONFIG.UI.STATE_LABELS.CHARGING;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) decisionState = CONFIG.UI.STATE_LABELS.PICKUP;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) decisionState = CONFIG.UI.STATE_LABELS.DROPOFF;
            else decisionState = CONFIG.UI.STATE_LABELS.MOVING;
        }
        if (this.isRouting) decisionState = CONFIG.UI.STATE_LABELS.REROUTING;
        if (this.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD) decisionState = CONFIG.UI.STATE_LABELS.LOW_BATTERY;

        const calcHistory = this._calcHistory && this._calcHistory.length > 0 ?
            this._calcHistory.slice(-8).reverse().map(c => {
                const ago = ((Date.now() - c.timestamp) / 1000).toFixed(1);
                const colorClass = c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.GOOD ? 'color-success' : c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.WARN ? 'color-warning' : 'color-error';
                return `<tr><td>${ago}s</td><td class="text-center">${c.nodes}</td><td class="text-right fw-600 ${colorClass}">${c.time.toFixed(1)}ms</td></tr>`;
            }).join('') : `<tr><td colspan="3" class="p-8 text-center">${CONFIG.UI.STATE_LABELS.WAITING}</td></tr>`;

        const routeInfo = this.lastRouteBreakdown ?
            `<div class="insight-box">
                <div class="insight-title">🧠 A* Route Cost Breakdown</div>
                <div class="breakdown-container">
                    <div class="breakdown-row"><span>📏 Base Distance:</span><strong>${this.lastRouteBreakdown.baseDistance.toFixed(0)}m</strong></div>
                    <div class="breakdown-row"><span>🚗 Traffic Penalty:</span><span class="color-error">+${this.lastRouteBreakdown.trafficPenalty.toFixed(0)}m</span></div>
                    <div class="breakdown-row"><span>🌧️ Rain Penalty:</span><span class="color-primary">+${this.lastRouteBreakdown.rainPenalty.toFixed(0)}m</span></div>
                    <div class="breakdown-row"><span>🚧 Obstacle Penalty:</span><span class="color-warning">+${this.lastRouteBreakdown.obstaclePenalty.toFixed(0)}m</span></div>
                    <div class="breakdown-total"><span>🎯 Total Cost:</span><strong>${this.lastRouteBreakdown.totalCost.toFixed(0)}m</strong></div>
                    <div class="breakdown-row"><span>⏱ Sim ETA:</span><strong class="color-success">${this.getEtaText()}</strong></div>
                </div>
            </div>` : `<div class="insight-box text-center">Waiting for route calculation...</div>`;

        const avgTime = this._calcHistory?.length > 0 ? (this._calcHistory.reduce((a, b) => a + b.time, 0) / this._calcHistory.length).toFixed(1) : '0';
        const fastest = this._calcHistory?.length > 0 ? Math.min(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';
        const slowest = this._calcHistory?.length > 0 ? Math.max(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';

        return `
            <div class="computing-details">
                <div class="details-header">
                    🤖 ${this.name} <span>| Computing Engine</span>
                </div>
                
                <div class="status-badge ${this.isRouting ? 'status-warn' : this.status === CONFIG.ROBOT.STATUSES.MOVING ? 'status-success' : 'status-neutral'}">
                    State: ${decisionState}
                </div>

                <div class="stats-grid-3">
                    <div class="stat-card"><div class="stat-label">Speed</div><div class="stat-value">${(this.speedMultiplier * 100).toFixed(0)}%</div></div>
                    <div class="stat-card"><div class="stat-label">Battery</div><div class="stat-value ${batteryClass}">${this.battery.toFixed(1)}%</div></div>
                    <div class="stat-card"><div class="stat-label">Drain/s</div><div class="stat-value">${this.batteryDrain.toFixed(3)}</div></div>
                </div>

                ${routeInfo}

                <div class="history-container">
                    <div class="history-title">📊 Calculation History</div>
                    <table class="history-table">
                        <thead><tr><th>⏱ When</th><th>🔢 Nodes</th><th>⚡ Time</th></tr></thead>
                        <tbody>${calcHistory}</tbody>
                    </table>
                </div>

                <div class="performance-container">
                    <div class="perf-title">📈 Lifetime Performance</div>
                    <div class="perf-grid">
                        <div class="perf-card"><div class="stat-label">Deliveries</div><div class="stat-value text-success">${this.totalDeliveries}</div></div>
                        <div class="perf-card"><div class="stat-label">Distance</div><div class="stat-value text-info">${this.totalDistance.toFixed(0)}m</div></div>
                        <div class="perf-card"><div class="stat-label">Calculations</div><div class="stat-value text-highlight">${this._calcHistory?.length || 0}</div></div>
                    </div>
                    <div class="perf-summary">
                        <div>⚡ Fast: <strong class="text-success">${fastest}ms</strong></div>
                        <div>🐌 Slow: <strong class="text-error">${slowest}ms</strong></div>
                        <div>📊 Avg: <strong>${avgTime}ms</strong></div>
                    </div>
                </div>

                <div class="action-container">
                    <button @click="$store.sim.panels.insider = true; showAStarProcess(${this.id})" class="btn-primary-small">
                        🔬 Show Full A* Calculation Process
                    </button>
                </div>
            </div>
        `;
    }

    drawPathLine() {
        if (this.pathLine) this.pathLine.remove();

        if (this.currentPath.length > 1) {
            const latlngs = this.currentPath.map(p => [p.lat, p.lon]);
            this.pathLine = L.polyline(latlngs, {
                color: this.color,
                weight: CONFIG.UI.WEIGHTS.medium,
                opacity: CONFIG.UI.OPACITY.high,
                dashArray: CONFIG.UI.DASH_ARRAY
            }).addTo(mapManager.map);
        }
    }

    clearPathLine() {
        if (this.pathLine) {
            this.pathLine.remove();
            this.pathLine = null;
        }
    }

    distanceTo(point) {
        return Math.sqrt((this.lat - point.lat) ** 2 + (this.lon - point.lon) ** 2);
    }

    getStatusText() {
        return this.status === CONFIG.ROBOT.STATUSES.MOVING ? `Moving (${(this.speedMultiplier * 100).toFixed(0)}%)` : this.status;
    }

    getEtaText() {
        if (!this.lastRouteEtaMinutes) return '--';
        return `${this.lastRouteEtaMinutes.toFixed(1)} min`;
    }

    estimateBatteryRisk(routeCostMeters) {
        const projectedDrain = (routeCostMeters / 1000) * CONFIG.ROBOT.BATTERY_PROJECTED_DRAIN_FACTOR;
        return Math.max(0, projectedDrain - this.battery * CONFIG.ROBOT.BATTERY_SAFETY_MARGIN);
    }

    async maybeReroute(traffic, rainPenalty) {
        if (this.isRouting || this.status !== CONFIG.ROBOT.STATUSES.MOVING || !this.routeTarget) return;
        if (this.pathIndex >= this.currentPath.length - 2) return;
        if (Date.now() - this.lastRerouteAt < CONFIG.ROBOT.REROUTE_INTERVAL_MS) return;
        if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING) return;
        if (traffic < CONFIG.ROBOT.TRAFFIC_REROUTE_THRESHOLD && rainPenalty < CONFIG.ROBOT.RAIN_REROUTE_THRESHOLD) return;

        this.isRouting = true;
        this.lastRerouteAt = Date.now();

        try {
            const rebuilt = await this.buildRouteToTarget(this.routeTarget.lat, this.routeTarget.lon);

            if (rebuilt) {
                if (typeof simulation !== 'undefined' && simulation) {
                    simulation.totalReroutes++;
                    if (typeof simulation.recordReroute === 'function') {
                        simulation.recordReroute(this.routeAlgorithm);
                    }
                }
                logEvent(`↺ ${this.name} rerouted around ${traffic >= CONFIG.ROBOT.TRAFFIC_REROUTE_THRESHOLD ? 'traffic' : 'rain'}`);
                addDispatchInsight(
                    `${this.name} rerouted to avoid ${traffic >= CONFIG.ROBOT.TRAFFIC_REROUTE_THRESHOLD ? 'heavy traffic buildup' : 'high rain cost'} while preserving the shortest viable path.`,
                    CONFIG.UI.LOG_LEVELS.WARN
                );
            }
        } catch (error) {
            console.error(error);
        } finally {
            this.isRouting = false;
        }
    }

    async buildRouteToTarget(targetLat, targetLon, precalculatedRoute = null, precalculatedBreakdown = null) {
        const startTime = performance.now();
        const route = precalculatedRoute || await pathfindingManager.getRoute(
            this.lat,
            this.lon,
            targetLat,
            targetLon,
            this.roadMemory,
            this.routeAlgorithm
        );
        const calcTime = performance.now() - startTime;

        if (!route.path || route.path.length <= 1) return false;

        this.currentPath = route.path;
        this.lastRouteBreakdown = precalculatedBreakdown || pathfindingManager.estimateRouteCost(route);
        this.lastRouteEtaMinutes = this.lastRouteBreakdown.estimatedMinutes || 0;
        this.pathIndex = 0;
        this.status = CONFIG.ROBOT.STATUSES.MOVING;
        this.drawPathLine();

        this._calcHistory.push({
            time: calcTime,
            nodes: route.nodesExplored || route.path.length,
            timestamp: Date.now()
        });
        if (this._calcHistory.length > CONFIG.ROBOT.HISTORY_SIZE_LIMIT) {
            this._calcHistory = this._calcHistory.slice(-CONFIG.ROBOT.HISTORY_SIZE_LIMIT);
        }

        if (typeof simulation !== 'undefined' && simulation && typeof simulation.recordRouteMetrics === 'function') {
            simulation.recordRouteMetrics(this.routeAlgorithm, route);
        }

        return true;
    }

    async finishCharging() {
        if (this.resumeAfterCharge && this.currentDelivery) {
            this.resumeAfterCharge = false;
            this.routeMode = CONFIG.ROBOT.ROUTE_MODES.DELIVERY;

            if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) {
                this.routeTarget = {
                    lat: this.currentDelivery.pickup.lat,
                    lon: this.currentDelivery.pickup.lon
                };
                addDispatchInsight(`${this.name} resumed its interrupted pickup after charging.`, CONFIG.UI.LOG_LEVELS.SUCCESS || 'good');
                await this.buildRouteToTarget(this.currentDelivery.pickup.lat, this.currentDelivery.pickup.lon);
                return;
            }

            if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) {
                this.routeTarget = {
                    lat: this.currentDelivery.destination.lat,
                    lon: this.currentDelivery.destination.lon
                };
                addDispatchInsight(`${this.name} resumed its interrupted dropoff after charging.`, CONFIG.UI.LOG_LEVELS.SUCCESS);
                await this.buildRouteToTarget(this.currentDelivery.destination.lat, this.currentDelivery.destination.lon);
                return;
            }
        }

        this.status = CONFIG.ROBOT.STATUSES.IDLE;
        this.currentPath = [];
        this.pathIndex = 0;
        this.routeMode = null;
        this.routeTarget = null;
        this.clearPathLine();
    }
}
