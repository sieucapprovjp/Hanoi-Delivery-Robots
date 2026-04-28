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

    createMarker(map) {
        this.marker = L.marker([this.lat, this.lon], {
            icon: L.divIcon({
                html: `<div style="width:44px;height:44px;background:${this.color};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:22px;border:3px solid white;box-shadow:0 3px 10px rgba(0,0,0,0.3);">🤖</div>`,
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }),
            zIndexOffset: 1000
        }).addTo(map);

        // Initialize popup
        this.marker.bindPopup('Loading...');
        this.marker.on('click', () => {
            this.updatePopup();
            this.marker.openPopup();
            // Update computing panel if open
            const compPanel = document.querySelector('.computing-panel');
            if (compPanel && compPanel.style.display === 'block') {
                const content = document.getElementById('computing-content');
                if (content) {
                    content.dataset.robotId = this.id;
                    content.innerHTML = this.getComputingDetails();
                }
            }
        });
    }

    updatePopup() {
        const deliveryInfo = this.currentDelivery ?
            `<div style="margin:4px 0;padding:5px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:6px;"><div style="font-size:10px;color:${CONFIG.UI.COLORS.textLight};">📦 Order #${this.currentDelivery.id}</div><div style="font-size:11px;">${this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP ? '🔵 Going to pickup' : '🔴 Going to deliver'}</div></div>` :
            `<div style="font-size:11px;color:${CONFIG.UI.COLORS.textLight};">No delivery</div>`;

        const destInfo = this.routeTarget ?
            `<div style="margin:4px 0;padding:5px;background:${CONFIG.UI.COLORS.successLight};border-radius:6px;font-size:11px;">🎯 ${this.routeTarget.lat.toFixed(4)}, ${this.routeTarget.lon.toFixed(4)}<br>${this.currentPath.length - this.pathIndex} waypoints left<br>⏱ ETA ${this.getEtaText()}</div>` : '';

        const batteryColor = this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? CONFIG.ROBOT.COLORS.good : this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? CONFIG.ROBOT.COLORS.warn : CONFIG.ROBOT.COLORS.error;

        // Current decision state
        let decisionState = CONFIG.UI.STATE_LABELS.IDLE;
        if (this.status === CONFIG.ROBOT.STATUSES.MOVING) {
            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING) decisionState = CONFIG.UI.STATE_LABELS.CHARGING;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_PICKUP;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_DROPOFF;
            else decisionState = CONFIG.UI.STATE_LABELS.MOVING;
        }
        if (this.isRouting) decisionState = CONFIG.UI.STATE_LABELS.REROUTING;
        if (this.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD && this.status !== CONFIG.ROBOT.STATUSES.CHARGING) decisionState = CONFIG.UI.STATE_LABELS.LOW_BATTERY;

        const content = `<div style="min-width:240px;font-family:'Segoe UI',Arial,sans-serif;max-height:80vh;overflow-y:auto;">
            <div style="font-size:13px;font-weight:700;color:${this.color};margin-bottom:4px;">🤖 ${this.name}</div>
            
            <div style="margin:4px 0;padding:5px;background:${this.isRouting ? CONFIG.UI.COLORS.warnLight : this.status === CONFIG.ROBOT.STATUSES.MOVING ? CONFIG.UI.COLORS.successLight : CONFIG.UI.COLORS.surfaceLight};border-radius:6px;font-size:11px;border-left:3px solid ${this.isRouting ? CONFIG.ROBOT.COLORS.highlight : this.status === CONFIG.ROBOT.STATUSES.MOVING ? CONFIG.ROBOT.COLORS.good : CONFIG.ROBOT.COLORS.neutral};">
                <div style="font-weight:600;">${decisionState}</div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin:4px 0;">
                <div style="padding:4px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:4px;text-align:center;"><div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};">Speed</div><div style="font-size:11px;font-weight:600;">${(this.speedMultiplier * 100).toFixed(0)}%</div></div>
                <div style="padding:4px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:4px;text-align:center;"><div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};">Battery</div><div style="font-size:11px;font-weight:600;color:${batteryColor};">${this.battery.toFixed(1)}%</div></div>
                <div style="padding:4px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:4px;text-align:center;"><div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};">Drain</div><div style="font-size:11px;font-weight:600;">${this.batteryDrain.toFixed(3)}/s</div></div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0;">
                <div style="padding:4px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:4px;text-align:center;"><div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};">Completed</div><div style="font-size:14px;font-weight:700;color:${CONFIG.ROBOT.COLORS.good};">${this.totalDeliveries}</div></div>
                <div style="padding:4px;background:${CONFIG.UI.COLORS.surfaceLight};border-radius:4px;text-align:center;"><div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};">Distance</div><div style="font-size:14px;font-weight:700;color:${CONFIG.ROBOT.COLORS.info};">${this.totalDistance.toFixed(0)}m</div></div>
            </div>

            ${destInfo}${deliveryInfo}
        </div>`;

        const popup = this.marker.getPopup();
        if (popup) popup.setContent(content);
    }

    getComputingDetails() {
        const batteryColor = this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.GOOD ? CONFIG.ROBOT.COLORS.good : this.battery > CONFIG.ROBOT.BATTERY_HEALTH_THRESHOLDS.WARN ? CONFIG.ROBOT.COLORS.warn : CONFIG.ROBOT.COLORS.error;

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
                const color = c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.GOOD ? CONFIG.ROBOT.COLORS.good : c.time < CONFIG.ROBOT.CALC_TIME_THRESHOLDS.WARN ? CONFIG.ROBOT.COLORS.warn : CONFIG.ROBOT.COLORS.error;
                return `<tr style="border-bottom:1px solid ${CONFIG.UI.COLORS.border};">
                    <td style="padding:3px;color:${CONFIG.UI.COLORS.textLight};">${ago}s</td>
                    <td style="padding:3px;text-align:center;">${c.nodes}</td>
                    <td style="padding:3px;text-align:right;color:${color};font-weight:600;">${c.time.toFixed(1)}ms</td>
                </tr>`;
            }).join('') : `<tr><td colspan="3" style="padding:6px;text-align:center;color:${CONFIG.UI.COLORS.textLight};">${CONFIG.UI.STATE_LABELS.WAITING}</td></tr>`;

        const routeInfo = this.lastRouteBreakdown ?
            `<div style="background:${CONFIG.UI.GRADIENTS.info};padding:10px;border-radius:8px;margin:6px 0;">
                <div style="font-weight:700;font-size:11px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                    🧠 A* Route Cost Breakdown
                </div>
                <div style="background:${CONFIG.UI.COLORS.surface};border-radius:6px;padding:8px;font-size:11px;">
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed ${CONFIG.UI.COLORS.border};">
                        <span>📏 Base Distance (Haversine):</span><strong style="color:${CONFIG.ROBOT.COLORS.info};">${this.lastRouteBreakdown.baseDistance.toFixed(0)}m</strong>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed ${CONFIG.UI.COLORS.border};">
                        <span>🚗 Traffic Penalty:</span><span style="color:${CONFIG.ROBOT.COLORS.error};font-weight:600;">+${this.lastRouteBreakdown.trafficPenalty.toFixed(0)}m</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed ${CONFIG.UI.COLORS.border};">
                        <span>🌧️ Rain Penalty:</span><span style="color:${CONFIG.ROBOT.COLORS.info};font-weight:600;">+${this.lastRouteBreakdown.rainPenalty.toFixed(0)}m</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed ${CONFIG.UI.COLORS.border};">
                        <span>🚧 Obstacle Penalty:</span><span style="color:${CONFIG.ROBOT.COLORS.highlight};font-weight:600;">+${this.lastRouteBreakdown.obstaclePenalty.toFixed(0)}m</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:6px 0 3px 0;padding-top:6px;border-top:2px solid ${CONFIG.ROBOT.COLORS.info};background:${CONFIG.UI.COLORS.surfaceLight};padding:6px;border-radius:4px;">
                        <span style="font-weight:700;">🎯 Total Cost:</span><strong style="color:${CONFIG.ROBOT.COLORS.info};font-size:13px;">${this.lastRouteBreakdown.totalCost.toFixed(0)}m</strong>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0 0 0;padding-top:4px;">
                        <span>⏱ Sim ETA:</span><strong style="color:${CONFIG.UI.COLORS.success};">${this.getEtaText()}</strong>
                    </div>
                </div>
                <div style="margin-top:6px;font-size:9px;color:${CONFIG.UI.COLORS.textLight};">
                    <strong>A* Formula:</strong> f(n) = g(n) + h(n)<br>
                    g(n) = actual cost from start | h(n) = Haversine heuristic to goal
                </div>
            </div>` : `<div style="background:${CONFIG.UI.COLORS.surfaceLight};padding:10px;border-radius:8px;margin:6px 0;text-align:center;font-size:11px;color:${CONFIG.UI.COLORS.textLight};">Waiting for route calculation...</div>`;

        const avgTime = this._calcHistory?.length > 0 ?
            (this._calcHistory.reduce((a, b) => a + b.time, 0) / this._calcHistory.length).toFixed(1) : '0';
        const fastest = this._calcHistory?.length > 0 ?
            Math.min(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';
        const slowest = this._calcHistory?.length > 0 ?
            Math.max(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';

        // 🧠 Memory stats
        const memorySize = Object.keys(this.roadMemory).length;
        const hotRoads = Object.values(this.roadMemory).filter(p => p > 1.4).length;
        const avgMemoryPenalty = memorySize > 0 ?
            (Object.values(this.roadMemory).reduce((a, b) => a + b, 0) / memorySize).toFixed(2) : '1.00';

        return `
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-height:85vh;overflow-y:auto;">
                <div style="font-size:13px;font-weight:700;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;">
                    🤖 ${this.name} <span style="font-size:10px;color:${CONFIG.UI.COLORS.textLight};font-weight:400;">| Computing Engine</span>
                </div>
                
                <div style="background:${this.isRouting ? CONFIG.UI.COLORS.warnLight : this.status === CONFIG.ROBOT.STATUSES.MOVING ? CONFIG.UI.COLORS.successLight : CONFIG.UI.COLORS.surfaceLight};padding:6px 8px;border-radius:6px;margin:6px 0;border-left:4px solid ${this.isRouting ? CONFIG.ROBOT.COLORS.highlight : this.status === CONFIG.ROBOT.STATUSES.MOVING ? CONFIG.ROBOT.COLORS.good : CONFIG.ROBOT.COLORS.neutral};">
                    <div style="font-size:11px;font-weight:600;">State: ${decisionState}</div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px;">
                    <div style="background:${CONFIG.UI.GRADIENTS.surface};padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Speed</div>
                        <div style="font-size:11px;font-weight:700;">${(this.speedMultiplier * 100).toFixed(0)}%</div>
                    </div>
                    <div style="background:${CONFIG.UI.GRADIENTS.surface};padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Battery</div>
                        <div style="font-size:11px;font-weight:700;color:${batteryColor};">${this.battery.toFixed(1)}%</div>
                    </div>
                    <div style="background:${CONFIG.UI.GRADIENTS.surface};padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Drain/s</div>
                        <div style="font-size:11px;font-weight:700;">${this.batteryDrain.toFixed(3)}</div>
                    </div>
                </div>

                ${routeInfo}

                <div style="background:${CONFIG.UI.GRADIENTS.purple};padding:10px;border-radius:8px;margin:8px 0;">
                    <div style="font-weight:700;font-size:11px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                        📊 Calculation History
                        <span style="font-size:9px;color:${CONFIG.UI.COLORS.textLight};font-weight:400;">(last ${Math.min(8, this._calcHistory?.length || 0)})</span>
                    </div>
                    <table style="width:100%;border-collapse:collapse;font-size:10px;background:${CONFIG.UI.COLORS.surface};border-radius:6px;overflow:hidden;">
                        <thead>
                            <tr style="background:${CONFIG.UI.COLORS.purpleDark};color:white;">
                                <th style="padding:5px;text-align:left;padding-left:8px;">⏱ When</th>
                                <th style="padding:5px;text-align:center;">🔢 Nodes</th>
                                <th style="padding:5px;text-align:right;padding-right:8px;">⚡ Time</th>
                            </tr>
                        </thead>
                        <tbody>${calcHistory}</tbody>
                    </table>
                </div>

                <div style="background:${CONFIG.UI.GRADIENTS.success};padding:10px;border-radius:8px;margin:6px 0;">
                    <div style="font-weight:700;font-size:11px;margin-bottom:6px;">📈 Lifetime Performance</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
                        <div style="background:${CONFIG.UI.COLORS.surface};padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Deliveries</div>
                            <div style="font-size:16px;font-weight:700;color:${CONFIG.ROBOT.COLORS.good};">${this.totalDeliveries}</div>
                        </div>
                        <div style="background:${CONFIG.UI.COLORS.surface};padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Distance</div>
                            <div style="font-size:16px;font-weight:700;color:${CONFIG.ROBOT.COLORS.info};">${this.totalDistance.toFixed(0)}m</div>
                        </div>
                        <div style="background:${CONFIG.UI.COLORS.surface};padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:${CONFIG.UI.COLORS.textLight};text-transform:uppercase;">Calculations</div>
                            <div style="font-size:16px;font-weight:700;color:${CONFIG.ROBOT.COLORS.highlight};">${this._calcHistory?.length || 0}</div>
                        </div>
                    </div>
                    <div style="margin-top:6px;background:${CONFIG.UI.COLORS.surface};padding:6px;border-radius:6px;display:flex;justify-content:space-around;font-size:10px;">
                        <div>⚡ Fastest: <strong style="color:${CONFIG.ROBOT.COLORS.good};">${fastest}ms</strong></div>
                        <div>🐌 Slowest: <strong style="color:${CONFIG.ROBOT.COLORS.error};">${slowest}ms</strong></div>
                        <div>📊 Avg: <strong style="color:${CONFIG.UI.COLORS.purpleDark};">${avgTime}ms</strong></div>
                    </div>
                    <div style="margin-top:6px;background:${CONFIG.UI.GRADIENTS.purple};padding:6px;border-radius:6px;">
                        <div style="font-size:9px;font-weight:700;margin-bottom:3px;">🧠 Road Memory (Learning)</div>
                        <div style="display:flex;gap:8px;font-size:10px;">
                            <span>📍 Roads: <strong>${memorySize}</strong></span>
                            <span>🔥 Hot: <strong style="color:${CONFIG.ROBOT.COLORS.error};">${hotRoads}</strong></span>
                            <span>⚖️ Avg: <strong>${avgMemoryPenalty}x</strong></span>
                        </div>
                    </div>
                </div>

                <div style="background:${CONFIG.UI.COLORS.warnLight};padding:8px;border-radius:6px;margin:6px 0;font-size:9px;color:${CONFIG.UI.COLORS.textLight};border-left:3px solid ${CONFIG.ROBOT.COLORS.warn};">
                    <strong>💡 How A* + Learning Works:</strong><br>
                    1. Start node added to open set<br>
                    2. Node with lowest f(n) selected<br>
                    3. Neighbors evaluated with penalties<br>
                    4. <strong>🧠 Robot remembers slow roads → avoids them next time</strong><br>
                    5. Path reconstructed from start to goal<br>
                    6. <strong>Penalties:</strong> 🌧️ Rain ${CONFIG.ROBOT.RAIN_REROUTE_THRESHOLD}x | 🚗 Traffic ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${(CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 2.5).toFixed(1)}x | 🚧 Obstacles ${CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER}-${(CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER * 4).toFixed(1)}x | 🧠 Memory ${CONFIG.ROBOT.EXPERIENCE_PENALTIES.light}-${CONFIG.ROBOT.EXPERIENCE_PENALTIES.heavy}x
                </div>

                <div style="margin:8px 0;">
                    <button onclick="showAStarProcess(${this.id})" style="width:100%;padding:10px;background:${CONFIG.UI.GRADIENTS.info};color:white;border:none;border-radius:8px;font-size:11px;font-weight:700;cursor:pointer;box-shadow:0 2px 8px rgba(26,115,232,${CONFIG.UI.OPACITY.low});">
                        🔬 Show Full A* Calculation Process
                    </button>
                </div>
                <div id="astep-visual-${this.id}" style="display:none;"></div>
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

        // Track calculation history
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
