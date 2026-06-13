// Robot movement, routing, charging, and local road-memory behavior.
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
        this.currentDeliveryAlgorithm = null;
        this.deliveryQueue = [];
        this.routeSequence = [];
        this.currentSequenceIndex = 0;
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

        // Lightweight road-memory model used to discourage repeatedly slow edges.
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
            this.totalDistance += this.speed * this.speedMultiplier * CONFIG.ROBOT.METERS_PER_DEGREE;
        }

        const rainPenalty = mapManager.getRainPenaltyAt(this.lat, this.lon);
        this.battery -= this.batteryDrain * rainPenalty;

        const traffic = mapManager.getTrafficAt(this.lat, this.lon);
        this.speedMultiplier = Math.max(
            CONFIG.ROBOT.MIN_SPEED_MULTIPLIER,
            (CONFIG.ROBOT.BASE_SPEED_MULTIPLIER * (1 - traffic * CONFIG.ROBOT.TRAFFIC_IMPACT_FACTOR)) / rainPenalty
        );

        this._frameCount++;
        if (this.pathIndex + 1 < this.currentPath.length && this._frameCount % CONFIG.ROBOT.FRAME_COUNT_RECORD_MEMORY === 0) {
            const from = this.currentPath[this.pathIndex];
            const to = this.currentPath[this.pathIndex + 1];
            this.recordRoadExperience(from.lat, from.lon, to.lat, to.lon, this.speedMultiplier);
        }
        if (this._frameCount % CONFIG.ROBOT.FRAME_COUNT_DECAY_MEMORY === 0) this.decayMemory();

        this.maybeReroute(traffic, rainPenalty);

        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
            if (this.marker.isPopupOpen()) this.updatePopup();
        }

        if (this.battery < CONFIG.ROBOT.BATTERY_LOW_THRESHOLD && this.status === CONFIG.ROBOT.STATUSES.MOVING && !this.isRouting && this.routeMode !== CONFIG.ROBOT.ROUTE_MODES.CHARGING) {
            this.goCharge();
        }

        if (this.status === CONFIG.ROBOT.STATUSES.MOVING && this.chargingStation) {
            const distToCharge = this.distanceTo(this.chargingStation);
            if (distToCharge < CONFIG.ROBOT.CHARGING_ARRIVAL_THRESHOLD) {
                this.startCharging();
            }
        }
    }

    getDeliveryById(deliveryId) {
        return this.deliveryQueue.find(delivery => String(delivery.id) === String(deliveryId)) || null;
    }

    getCurrentRouteStop() {
        return this.routeSequence[this.currentSequenceIndex] || null;
    }

    setDeliveryStopTarget(stop) {
        this.currentDelivery = this.getDeliveryById(stop.deliveryId);
        this.deliveryPhase = stop.type === 'pickup'
            ? CONFIG.ROBOT.PHASES.TO_PICKUP
            : CONFIG.ROBOT.PHASES.TO_DROPOFF;
        this.routeMode = CONFIG.ROBOT.ROUTE_MODES.DELIVERY;
        this.routeDeliveryId = stop.deliveryId;
        this.routeTarget = { lat: stop.lat, lon: stop.lon };
    }

    finishDeliveryRoute() {
        this.status = CONFIG.ROBOT.STATUSES.IDLE;
        this.currentPath = [];
        this.pathIndex = 0;
        this.currentDelivery = null;
        this.deliveryQueue = [];
        this.routeSequence = [];
        this.currentSequenceIndex = 0;
        this.currentLoad = 0;
        this.routeMode = null;
        this.routeDeliveryId = null;
        this.routeTarget = null;
        this.deliveryPhase = null;
        this.clearPathLine();
    }

    async advanceToNextSequenceStop() {
        const nextStop = this.getCurrentRouteStop();
        if (!nextStop) {
            this.finishDeliveryRoute();
            return;
        }

        this.setDeliveryStopTarget(nextStop);
        await this.buildRouteToTarget(nextStop.lat, nextStop.lon);
    }

    async handleRouteSequenceArrival() {
        const stop = this.getCurrentRouteStop();
        if (!stop) {
            this.finishDeliveryRoute();
            return;
        }

        const delivery = this.getDeliveryById(stop.deliveryId);
        if (stop.type === 'pickup') {
            logEvent(`📍 ${this.name} picked up order #${stop.deliveryId}`);
            addDispatchInsight(
                `${this.name} reached pickup #${stop.deliveryId} in its VRP sequence.`,
                CONFIG.UI.LOG_LEVELS.SUCCESS
            );
        }

        if (stop.type === 'dropoff') {
            this.currentLoad = Math.max(0, this.currentLoad - 1);
            this.totalDeliveries++;
            if (typeof simulation !== 'undefined' && simulation && typeof simulation.recordDeliveryCompleted === 'function') {
                simulation.recordDeliveryCompleted(this.currentDeliveryAlgorithm || this.routeAlgorithm);
            }
            logEvent(`✅ ${this.name} completed delivery #${stop.deliveryId}`);
            mapManager.clearDeliveryMarkers(stop.deliveryId);
            this.deliveryQueue = this.deliveryQueue.filter(item => String(item.id) !== String(stop.deliveryId));
        }

        this.currentSequenceIndex++;
        if (this.currentSequenceIndex < this.routeSequence.length) {
            await this.advanceToNextSequenceStop();
            return;
        }

        if (delivery) {
            this.currentDelivery = delivery;
        }
        this.currentDeliveryAlgorithm = null;
        this.finishDeliveryRoute();
    }

    async arriveAtWaypoint() {
        if (this.isRouting) return;
        this.isRouting = true;

        try {
            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.CHARGING && this.chargingStation) {
                this.startCharging();
                return;
            }

            if (this.routeMode === CONFIG.ROBOT.ROUTE_MODES.DELIVERY && this.routeSequence.length > 0) {
                await this.handleRouteSequenceArrival();
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
        this.resumeAfterCharge = (
            this.routeMode === CONFIG.ROBOT.ROUTE_MODES.DELIVERY
            && (this.routeSequence.length > 0 || !!this.currentDelivery)
        );
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

    buildDefaultRouteSequence(delivery) {
        return [
            {
                stopId: `P${delivery.id}`,
                type: 'pickup',
                deliveryId: delivery.id,
                lat: delivery.pickup.lat,
                lon: delivery.pickup.lon,
                name: delivery.pickup.name,
                category: delivery.pickup.category
            },
            {
                stopId: `D${delivery.id}`,
                type: 'dropoff',
                deliveryId: delivery.id,
                lat: delivery.destination.lat,
                lon: delivery.destination.lon,
                name: delivery.destination.name,
                category: delivery.destination.category
            }
        ];
    }

    async assignDelivery(delivery, precalculatedRoute = null, precalculatedBreakdown = null, assignment = null, deliveryBatch = null) {
        if (this.isRouting) return false;

        this.isRouting = true;
        const batch = deliveryBatch?.length ? deliveryBatch : [delivery];
        this.deliveryQueue = batch;
        this.routeSequence = assignment?.orderSequence?.length
            ? assignment.orderSequence
            : this.buildDefaultRouteSequence(delivery);
        this.currentSequenceIndex = 0;
        const firstStop = this.getCurrentRouteStop();
        if (!firstStop) {
            this.deliveryQueue = [];
            this.routeSequence = [];
            this.currentSequenceIndex = 0;
            this.isRouting = false;
            return false;
        }

        this.currentDelivery = firstStop ? this.getDeliveryById(firstStop.deliveryId) : delivery;
        this.currentDeliveryAlgorithm = this.routeAlgorithm;
        this.currentLoad += batch.length;
        batch.forEach(item => mapManager.showDeliveryMarkers(item));

        try {
            this.setDeliveryStopTarget(firstStop);
            this.lastRerouteAt = Date.now();
            const routed = await this.buildRouteToTarget(
                firstStop.lat,
                firstStop.lon,
                precalculatedRoute,
                precalculatedBreakdown
            );
            if (!routed) {
                throw new Error(`No route to first stop #${firstStop.deliveryId}`);
            }

            const orderList = batch.map(item => `#${item.id}`).join(', ');
            logEvent(`📦 ${this.name} accepted ${batch.length} order(s): ${orderList}`);
            addDispatchInsight(
                `${this.name} accepted ${batch.length} order(s) with ${this.routeSequence.length} VRP stops.`,
                CONFIG.UI.LOG_LEVELS.NEUTRAL
            );
            return true;
        } catch (error) {
            this.currentDelivery = null;
            this.currentDeliveryAlgorithm = null;
            this.deliveryQueue = [];
            this.routeSequence = [];
            this.currentSequenceIndex = 0;
            this.currentLoad = Math.max(0, this.currentLoad - batch.length);
            batch.forEach(item => mapManager.clearDeliveryMarkers(item.id));
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
                className: 'robot-marker',
                html: `
                    <div class="robot-marker-icon" style="--robot-color: ${this.color}">
                        <div class="robot-marker-avatar">🤖</div>
                    </div>
                `,
                iconSize: [44, 44],
                iconAnchor: [22, 22]
            }),
            zIndexOffset: 1000
        }).addTo(map);

        this.marker.bindPopup(CONFIG.UI.TEXT.LOADING.POPUP);
        this.marker.on('click', () => {
            this.updatePopup();
            this.marker.openPopup();
            
            const store = Alpine.store('sim');
            if (store) {
                store.computing.robotId = this.id;
                store.computing.details = this.getComputingDetails();
            }
        });
    }

    updatePopup() {
        const popup = this.marker.getPopup();
        if (popup) popup.setContent(renderRobotPopup(this));
    }

    getComputingDetails() {
        return renderRobotComputingDetails(this);
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

    estimateWeightedPathCost(path) {
        if (!path || path.length < 2) return Infinity;

        let cost = 0;
        for (let i = 0; i < path.length - 1; i++) {
            const from = path[i];
            const to = path[i + 1];
            const distance = mapManager.distance(from.lat, from.lon, to.lat, to.lon);
            const midpoint = {
                lat: (from.lat + to.lat) / 2,
                lon: (from.lon + to.lon) / 2
            };
            const trafficPenalty = 1 + mapManager.getTrafficAt(midpoint.lat, midpoint.lon) * CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER;
            const rainPenalty = mapManager.getRainPenaltyAt(midpoint.lat, midpoint.lon);
            cost += distance * trafficPenalty * rainPenalty;
        }
        return cost;
    }

    estimateRemainingRouteCost() {
        if (!this.currentPath || this.currentPath.length <= this.pathIndex + 1) return Infinity;

        return this.estimateWeightedPathCost([
            { lat: this.lat, lon: this.lon },
            ...this.currentPath.slice(this.pathIndex + 1)
        ]);
    }

    isBacktrackingRoute(path) {
        if (!path || path.length < 2 || this.pathIndex <= 0) return false;

        const previousPoint = this.currentPath[this.pathIndex - 1];
        if (!previousPoint) return false;

        const nextPoint = path[1];
        return mapManager.distance(
            nextPoint.lat,
            nextPoint.lon,
            previousPoint.lat,
            previousPoint.lon
        ) <= CONFIG.ROBOT.REROUTE_BACKTRACK_DISTANCE_METERS;
    }

    evaluateRerouteCandidate(route, breakdown) {
        const currentCost = this.estimateRemainingRouteCost();
        const candidateCost = breakdown.totalCost || this.estimateWeightedPathCost(route.path);

        if (!Number.isFinite(currentCost) || !Number.isFinite(candidateCost)) {
            return { accepted: true, currentCost, candidateCost, improvementRatio: 1 };
        }

        const improvementRatio = (currentCost - candidateCost) / currentCost;
        const isBacktracking = this.isBacktrackingRoute(route.path);
        const accepted = (
            improvementRatio >= CONFIG.ROBOT.REROUTE_MIN_IMPROVEMENT_RATIO
            && !isBacktracking
        );

        return { accepted, currentCost, candidateCost, improvementRatio, isBacktracking };
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
            const startTime = performance.now();
            const route = await pathfindingManager.getRoute(
                this.lat,
                this.lon,
                this.routeTarget.lat,
                this.routeTarget.lon,
                this.roadMemory,
                this.routeAlgorithm
            );
            const breakdown = pathfindingManager.estimateRouteCost(route);
            const decision = this.evaluateRerouteCandidate(route, breakdown);

            if (!decision.accepted) {
                addDispatchInsight(
                    `${this.name} kept current route: alternative was ${decision.isBacktracking ? 'a backtrack' : 'not cheaper enough'} (${decision.candidateCost.toFixed(0)} vs ${decision.currentCost.toFixed(0)} cost).`,
                    CONFIG.UI.LOG_LEVELS.NEUTRAL
                );
                return;
            }

            const rebuilt = this.applyRoute(route, breakdown, performance.now() - startTime);

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
        const breakdown = precalculatedBreakdown || pathfindingManager.estimateRouteCost(route);

        return this.applyRoute(route, breakdown, calcTime);
    }

    applyRoute(route, breakdown, calcTime) {
        if (!route.path || route.path.length === 0) return false;

        this.currentPath = route.path;
        this.lastRouteBreakdown = breakdown;
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
        if (this.resumeAfterCharge && this.routeSequence.length > 0) {
            this.resumeAfterCharge = false;
            this.routeMode = CONFIG.ROBOT.ROUTE_MODES.DELIVERY;
            const nextStop = this.getCurrentRouteStop();
            if (nextStop) {
                this.setDeliveryStopTarget(nextStop);
                addDispatchInsight(
                    `${this.name} resumed VRP stop ${this.currentSequenceIndex + 1}/${this.routeSequence.length} after charging.`,
                    CONFIG.UI.LOG_LEVELS.SUCCESS
                );
                await this.buildRouteToTarget(nextStop.lat, nextStop.lon);
                return;
            }
        }

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
