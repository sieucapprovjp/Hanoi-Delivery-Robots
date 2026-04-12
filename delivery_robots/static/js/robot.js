// Simple working robot
class DeliveryRobot {
    constructor(id, lat, lon, name, color) {
        this.id = id;
        this.lat = lat;
        this.lon = lon;
        this.name = name;
        this.color = color;
        this.speed = 0.000010;
        this.battery = 100;
        this.batteryDrain = 0.0065;
        this.capacity = 10;
        this.currentLoad = 0;
        this.status = 'idle';
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

        // 🧠 Road memory system (Q-learning lite)
        this.roadMemory = {};
        this.memoryDecay = 0.995;
        this._frameCount = 0;
    }

    recordRoadExperience(fromLat, fromLon, toLat, toLon, speedMultiplier) {
        const key = `${fromLat.toFixed(4)},${fromLon.toFixed(4)}->${toLat.toFixed(4)},${toLon.toFixed(4)}`;
        const currentPenalty = this.roadMemory[key] || 1.0;
        const experiencedPenalty = speedMultiplier < 0.3 ? 1.8 : speedMultiplier < 0.6 ? 1.3 : 0.95;
        this.roadMemory[key] = currentPenalty * 0.7 + experiencedPenalty * 0.3;
    }

    decayMemory() {
        for (const key in this.roadMemory) {
            this.roadMemory[key] = this.roadMemory[key] * this.memoryDecay + 1.0 * (1 - this.memoryDecay);
            if (Math.abs(this.roadMemory[key] - 1.0) < 0.01) delete this.roadMemory[key];
        }
    }

    update() {
        if (this.status !== 'moving') return;

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
            this.totalDistance += this.speed * this.speedMultiplier * 111000; // to meters
        }

        // Battery
        const rainPenalty = mapManager.getRainPenaltyAt(this.lat, this.lon);
        this.battery -= this.batteryDrain * rainPenalty;
        
        // Check traffic
        const traffic = mapManager.getTrafficAt(this.lat, this.lon);
        this.speedMultiplier = Math.max(0.08, (0.55 * (1 - traffic * 0.65)) / rainPenalty);

        // 🧠 Record road experience for learning
        this._frameCount++;
        if (this.pathIndex + 1 < this.currentPath.length && this._frameCount % 30 === 0) {
            const from = this.currentPath[this.pathIndex];
            const to = this.currentPath[this.pathIndex + 1];
            this.recordRoadExperience(from.lat, from.lon, to.lat, to.lon, this.speedMultiplier);
        }
        // Decay memory every ~5 seconds (300 frames at 60fps)
        if (this._frameCount % 300 === 0) this.decayMemory();

        this.maybeReroute(traffic, rainPenalty);

        // Update marker
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
            if (this.marker.isPopupOpen()) this.updatePopup();
        }

        // Check if need charging
        if (this.battery < 20 && this.status === 'moving' && !this.isRouting && this.routeMode !== 'charging') {
            this.goCharge();
        }

        // Check if arrived at charging
        if (this.status === 'moving' && this.chargingStation) {
            const distToCharge = this.distanceTo(this.chargingStation);
            if (distToCharge < 0.0005) {
                this.startCharging();
            }
        }
    }

    async arriveAtWaypoint() {
        if (this.routeMode === 'charging' && this.chargingStation) {
            this.startCharging();
            return;
        }

        if (this.currentDelivery && this.deliveryPhase === 'to_pickup') {
            this.deliveryPhase = 'to_dropoff';
            this.routeTarget = {
                lat: this.currentDelivery.destination.lat,
                lon: this.currentDelivery.destination.lon
            };
            logEvent(`📍 ${this.name} picked up order #${this.currentDelivery.id}`);
            addDispatchInsight(`${this.name} completed pickup and is now committing to the final dropoff leg.`, 'good');
            await this.buildRouteToTarget(this.currentDelivery.destination.lat, this.currentDelivery.destination.lon);
            return;
        }

        if (this.currentDelivery && this.deliveryPhase === 'to_dropoff') {
            this.currentLoad--;
            this.totalDeliveries++;
            logEvent(`✅ ${this.name} completed delivery #${this.currentDelivery.id}`);
            mapManager.clearDeliveryMarkers(this.currentDelivery.id);
            this.currentDelivery = null;
        }

        this.status = 'idle';
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
        this.resumeAfterCharge = this.routeMode === 'delivery' && !!this.currentDelivery;
        this.chargingStation = station;
        mapManager.occupyChargingSpot(station);

        try {
            this.routeMode = 'charging';
            this.routeTarget = { lat: station.lat, lon: station.lon };
            this.routeDeliveryId = null;
            await this.buildRouteToTarget(station.lat, station.lon);
            logEvent(`⚡ ${this.name} → ${station.name}`);
            addDispatchInsight(`${this.name} is diverting to nearest charger ${station.name} because battery dropped below 20%.`, 'warn');
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
        this.status = 'charging';
        logEvent(`🔌 ${this.name} charging`);
        
        const charge = setInterval(() => {
            this.battery += 8;
            if (this.battery >= 90) {
                this.battery = 90;
                clearInterval(charge);
                if (this.chargingStation) {
                    mapManager.releaseChargingSpot(this.chargingStation);
                    this.chargingStation = null;
                }
                logEvent(`⚡ ${this.name} charged and ready`);
                this.finishCharging();
            }
        }, 700);
    }

    async assignDelivery(delivery) {
        if (this.isRouting) return false;

        this.isRouting = true;
        this.currentDelivery = delivery;
        this.currentLoad++;
        this.deliveryPhase = 'to_pickup';
        mapManager.showDeliveryMarkers(delivery);

        try {
            this.routeMode = 'delivery';
            this.routeDeliveryId = delivery.id;
            this.routeTarget = { lat: delivery.pickup.lat, lon: delivery.pickup.lon };
            this.lastRerouteAt = Date.now();
            await this.buildRouteToTarget(delivery.pickup.lat, delivery.pickup.lon);

            logEvent(`📦 ${this.name} → ${delivery.pickup.name} → ${delivery.destination.name}`);
            addDispatchInsight(`${this.name} selected a low-cost route that balances distance with current rain and congestion exposure.`, 'neutral');
            return true;
        } catch (error) {
            this.currentDelivery = null;
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
            `<div style="margin:4px 0;padding:5px;background:#f8f9fa;border-radius:6px;"><div style="font-size:10px;color:#5f6368;">📦 Order #${this.currentDelivery.id}</div><div style="font-size:11px;">${this.deliveryPhase === 'pickup' ? '🔵 Going to pickup' : '🔴 Going to deliver'}</div></div>` : 
            '<div style="font-size:11px;color:#5f6368;">No delivery</div>';

        const destInfo = this.routeTarget ? 
            `<div style="margin:4px 0;padding:5px;background:#e8f5e9;border-radius:6px;font-size:11px;">🎯 ${this.routeTarget.lat.toFixed(4)}, ${this.routeTarget.lon.toFixed(4)}<br>${this.currentPath.length - this.pathIndex} waypoints left</div>` : '';

        const batteryColor = this.battery > 60 ? '#34a853' : this.battery > 30 ? '#fbbc04' : '#ea4335';
        
        // Current decision state
        let decisionState = '⏸ Idle - Waiting for assignment';
        if (this.status === 'moving') {
            if (this.routeMode === 'charging') decisionState = '🔋 Navigating to charging station';
            else if (this.deliveryPhase === 'to_pickup') decisionState = '📦 Routing to pickup location';
            else if (this.deliveryPhase === 'to_dropoff') decisionState = '🚚 Routing to delivery destination';
            else decisionState = '🔄 Moving to waypoint';
        }
        if (this.isRouting) decisionState = '🧠 Recalculating route...';
        if (this.battery < 20 && this.status !== 'charging') decisionState = '⚠️ Low battery - seeking charger';

        const content = `<div style="min-width:240px;font-family:'Segoe UI',Arial,sans-serif;max-height:80vh;overflow-y:auto;">
            <div style="font-size:13px;font-weight:700;color:${this.color};margin-bottom:4px;">🤖 ${this.name}</div>
            
            <div style="margin:4px 0;padding:5px;background:${this.isRouting ? '#fff3e0' : this.status === 'moving' ? '#e8f5e9' : '#f8f9fa'};border-radius:6px;font-size:11px;border-left:3px solid ${this.isRouting ? '#ff9800' : this.status === 'moving' ? '#34a853' : '#9e9e9e'};">
                <div style="font-weight:600;">${decisionState}</div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin:4px 0;">
                <div style="padding:4px;background:#f8f9fa;border-radius:4px;text-align:center;"><div style="font-size:8px;color:#5f6368;">Speed</div><div style="font-size:11px;font-weight:600;">${(this.speedMultiplier*100).toFixed(0)}%</div></div>
                <div style="padding:4px;background:#f8f9fa;border-radius:4px;text-align:center;"><div style="font-size:8px;color:#5f6368;">Battery</div><div style="font-size:11px;font-weight:600;color:${batteryColor};">${this.battery.toFixed(1)}%</div></div>
                <div style="padding:4px;background:#f8f9fa;border-radius:4px;text-align:center;"><div style="font-size:8px;color:#5f6368;">Drain</div><div style="font-size:11px;font-weight:600;">${this.batteryDrain.toFixed(3)}/s</div></div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:4px 0;">
                <div style="padding:4px;background:#f8f9fa;border-radius:4px;text-align:center;"><div style="font-size:8px;color:#5f6368;">Completed</div><div style="font-size:14px;font-weight:700;color:#34a853;">${this.totalDeliveries}</div></div>
                <div style="padding:4px;background:#f8f9fa;border-radius:4px;text-align:center;"><div style="font-size:8px;color:#5f6368;">Distance</div><div style="font-size:14px;font-weight:700;color:#1a73e8;">${this.totalDistance.toFixed(0)}m</div></div>
            </div>

            ${destInfo}${deliveryInfo}
        </div>`;

        const popup = this.marker.getPopup();
        if (popup) popup.setContent(content);
    }

    getComputingDetails() {
        const batteryColor = this.battery > 60 ? '#34a853' : this.battery > 30 ? '#fbbc04' : '#ea4335';
        
        let decisionState = '⏸ Idle';
        if (this.status === 'moving') {
            if (this.routeMode === 'charging') decisionState = '🔋 Charging';
            else if (this.deliveryPhase === 'to_pickup') decisionState = '📦 To Pickup';
            else if (this.deliveryPhase === 'to_dropoff') decisionState = '🚚 To Dropoff';
            else decisionState = '🔄 Moving';
        }
        if (this.isRouting) decisionState = '🧠 Rerouting';
        if (this.battery < 20) decisionState = '⚠️ Low Battery';

        const calcHistory = this._calcHistory && this._calcHistory.length > 0 ?
            this._calcHistory.slice(-8).reverse().map(c => {
                const ago = ((Date.now() - c.timestamp) / 1000).toFixed(1);
                const color = c.time < 30 ? '#34a853' : c.time < 80 ? '#fbbc04' : '#ea4335';
                return `<tr style="border-bottom:1px solid #e0e0e0;">
                    <td style="padding:3px;color:#5f6368;">${ago}s</td>
                    <td style="padding:3px;text-align:center;">${c.nodes}</td>
                    <td style="padding:3px;text-align:right;color:${color};font-weight:600;">${c.time.toFixed(1)}ms</td>
                </tr>`;
            }).join('') : '<tr><td colspan="3" style="padding:6px;text-align:center;color:#5f6368;">Waiting...</td></tr>';

        const routeInfo = this.lastRouteBreakdown ?
            `<div style="background:linear-gradient(135deg,#e3f2fd,#bbdefb);padding:10px;border-radius:8px;margin:6px 0;">
                <div style="font-weight:700;font-size:11px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                    🧠 A* Route Cost Breakdown
                </div>
                <div style="background:white;border-radius:6px;padding:8px;font-size:11px;">
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed #e0e0e0;">
                        <span>📏 Base Distance (Haversine):</span><strong style="color:#1a73e8;">${this.lastRouteBreakdown.baseDistance.toFixed(0)}m</strong>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed #e0e0e0;">
                        <span>🚗 Traffic Penalty:</span><span style="color:#ea4335;font-weight:600;">+${this.lastRouteBreakdown.trafficPenalty.toFixed(0)}m</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:3px 0;padding:3px 0;border-bottom:1px dashed #e0e0e0;">
                        <span>🌧️ Rain Penalty:</span><span style="color:#4285f4;font-weight:600;">+${this.lastRouteBreakdown.rainPenalty.toFixed(0)}m</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin:6px 0 3px 0;padding-top:6px;border-top:2px solid #1a73e8;background:#f8f9fa;padding:6px;border-radius:4px;">
                        <span style="font-weight:700;">🎯 Total Cost:</span><strong style="color:#1a73e8;font-size:13px;">${this.lastRouteBreakdown.totalCost.toFixed(0)}m</strong>
                    </div>
                </div>
                <div style="margin-top:6px;font-size:9px;color:#5f6368;">
                    <strong>A* Formula:</strong> f(n) = g(n) + h(n)<br>
                    g(n) = actual cost from start | h(n) = Haversine heuristic to goal
                </div>
            </div>` : '<div style="background:#f8f9fa;padding:10px;border-radius:8px;margin:6px 0;text-align:center;font-size:11px;color:#5f6368;">Waiting for route calculation...</div>';

        const avgTime = this._calcHistory?.length > 0 ? 
            (this._calcHistory.reduce((a,b) => a + b.time, 0) / this._calcHistory.length).toFixed(1) : '0';
        const fastest = this._calcHistory?.length > 0 ? 
            Math.min(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';
        const slowest = this._calcHistory?.length > 0 ? 
            Math.max(...this._calcHistory.map(c => c.time)).toFixed(1) : '0';

        // 🧠 Memory stats
        const memorySize = Object.keys(this.roadMemory).length;
        const hotRoads = Object.values(this.roadMemory).filter(p => p > 1.4).length;
        const avgMemoryPenalty = memorySize > 0 ?
            (Object.values(this.roadMemory).reduce((a,b) => a+b, 0) / memorySize).toFixed(2) : '1.00';

        return `
            <div style="font-family:'Segoe UI',Arial,sans-serif;max-height:85vh;overflow-y:auto;">
                <div style="font-size:15px;font-weight:700;color:${this.color};margin-bottom:8px;padding-bottom:6px;border-bottom:3px solid ${this.color};display:flex;align-items:center;gap:8px;">
                    🤖 ${this.name} <span style="font-size:10px;color:#5f6368;font-weight:400;">| Computing Engine</span>
                </div>
                
                <div style="background:${this.isRouting ? '#fff3e0' : this.status === 'moving' ? '#e8f5e9' : '#f8f9fa'};padding:6px 8px;border-radius:6px;margin:6px 0;border-left:4px solid ${this.isRouting ? '#ff9800' : this.status === 'moving' ? '#34a853' : '#9e9e9e'};">
                    <div style="font-size:11px;font-weight:600;">State: ${decisionState}</div>
                </div>

                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin:6px 0;">
                    <div style="background:linear-gradient(135deg,#f8f9fa,#e8eaed);padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Speed</div>
                        <div style="font-size:13px;font-weight:700;">${(this.speedMultiplier*100).toFixed(0)}%</div>
                    </div>
                    <div style="background:linear-gradient(135deg,#f8f9fa,#e8eaed);padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Battery</div>
                        <div style="font-size:13px;font-weight:700;color:${batteryColor};">${this.battery.toFixed(1)}%</div>
                    </div>
                    <div style="background:linear-gradient(135deg,#f8f9fa,#e8eaed);padding:6px;border-radius:6px;text-align:center;">
                        <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Drain/s</div>
                        <div style="font-size:13px;font-weight:700;">${this.batteryDrain.toFixed(3)}</div>
                    </div>
                </div>

                ${routeInfo}

                <div style="background:linear-gradient(135deg,#f3e5f5,#e1bee7);padding:10px;border-radius:8px;margin:8px 0;">
                    <div style="font-weight:700;font-size:11px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">
                        📊 Calculation History
                        <span style="font-size:9px;color:#5f6368;font-weight:400;">(last ${Math.min(8, this._calcHistory?.length || 0)})</span>
                    </div>
                    <table style="width:100%;border-collapse:collapse;font-size:10px;background:white;border-radius:6px;overflow:hidden;">
                        <thead>
                            <tr style="background:#7b1fa2;color:white;">
                                <th style="padding:5px;text-align:left;padding-left:8px;">⏱ When</th>
                                <th style="padding:5px;text-align:center;">🔢 Nodes</th>
                                <th style="padding:5px;text-align:right;padding-right:8px;">⚡ Time</th>
                            </tr>
                        </thead>
                        <tbody>${calcHistory}</tbody>
                    </table>
                </div>

                <div style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9);padding:10px;border-radius:8px;margin:6px 0;">
                    <div style="font-weight:700;font-size:11px;margin-bottom:6px;">📈 Lifetime Performance</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;">
                        <div style="background:white;padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Deliveries</div>
                            <div style="font-size:16px;font-weight:700;color:#34a853;">${this.totalDeliveries}</div>
                        </div>
                        <div style="background:white;padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Distance</div>
                            <div style="font-size:16px;font-weight:700;color:#1a73e8;">${this.totalDistance.toFixed(0)}m</div>
                        </div>
                        <div style="background:white;padding:6px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#5f6368;text-transform:uppercase;">Calculations</div>
                            <div style="font-size:16px;font-weight:700;color:#ff9800;">${this._calcHistory?.length || 0}</div>
                        </div>
                    </div>
                    <div style="margin-top:6px;background:white;padding:6px;border-radius:6px;display:flex;justify-content:space-around;font-size:10px;">
                        <div>⚡ Fastest: <strong style="color:#34a853;">${fastest}ms</strong></div>
                        <div>🐌 Slowest: <strong style="color:#ea4335;">${slowest}ms</strong></div>
                        <div>📊 Avg: <strong style="color:#9c27b0;">${avgTime}ms</strong></div>
                    </div>
                    <div style="margin-top:6px;background:linear-gradient(135deg,#ede7f6,#d1c4e9);padding:6px;border-radius:6px;">
                        <div style="font-size:9px;font-weight:700;margin-bottom:3px;">🧠 Road Memory (Learning)</div>
                        <div style="display:flex;gap:8px;font-size:10px;">
                            <span>📍 Roads: <strong>${memorySize}</strong></span>
                            <span>🔥 Hot: <strong style="color:#ea4335;">${hotRoads}</strong></span>
                            <span>⚖️ Avg: <strong>${avgMemoryPenalty}×</strong></span>
                        </div>
                    </div>
                </div>

                <div style="background:#fff8e1;padding:8px;border-radius:6px;margin:6px 0;font-size:9px;color:#5f6368;border-left:3px solid #ffc107;">
                    <strong>💡 How A* + Learning Works:</strong><br>
                    1. Start node added to open set<br>
                    2. Node with lowest f(n) selected<br>
                    3. Neighbors evaluated with penalties<br>
                    4. <strong>🧠 Robot remembers slow roads → avoids them next time</strong><br>
                    5. Path reconstructed from start to goal<br>
                    6. <strong>Penalties:</strong> 🌧️ Rain 2× | 🚗 Traffic 1.5-4× | 🚧 Obstacles 5-50× | 🧠 Memory 0.95-1.8×
                </div>

                <div style="margin:8px 0;">
                    <button onclick="showAStarProcess(${this.id})" style="width:100%;padding:10px;background:linear-gradient(135deg,#1a73e8,#1557b0);color:white;border:none;border-radius:8px;font-size:11px;font-weight:700;cursor:pointer;box-shadow:0 2px 8px rgba(26,115,232,0.3);">
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
                weight: 3,
                opacity: 0.5,
                dashArray: '8, 8'
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
        return this.status === 'moving' ? `Moving (${(this.speedMultiplier*100).toFixed(0)}%)` : this.status;
    }

    estimateBatteryRisk(routeCostMeters) {
        const projectedDrain = (routeCostMeters / 1000) * 4.5;
        return Math.max(0, projectedDrain - this.battery * 0.35);
    }

    async maybeReroute(traffic, rainPenalty) {
        if (this.isRouting || this.status !== 'moving' || !this.routeTarget) return;
        if (this.pathIndex >= this.currentPath.length - 2) return;
        if (Date.now() - this.lastRerouteAt < 5500) return;
        if (this.routeMode === 'charging') return;
        if (traffic < 0.45 && rainPenalty < 2) return;

        this.isRouting = true;
        this.lastRerouteAt = Date.now();

        try {
            const rebuilt = await this.buildRouteToTarget(this.routeTarget.lat, this.routeTarget.lon);

            if (rebuilt) {
                if (typeof simulation !== 'undefined' && simulation) {
                    simulation.totalReroutes++;
                }
                logEvent(`↺ ${this.name} rerouted around ${traffic >= 0.45 ? 'traffic' : 'rain'}`);
                addDispatchInsight(
                    `${this.name} rerouted to avoid ${traffic >= 0.45 ? 'heavy traffic buildup' : 'high rain cost'} while preserving the shortest viable path.`,
                    'warn'
                );
            }
        } catch (error) {
            console.error(error);
        } finally {
            this.isRouting = false;
        }
    }

    async buildRouteToTarget(targetLat, targetLon) {
        const startTime = performance.now();
        const route = await pathfindingManager.getRoute(this.lat, this.lon, targetLat, targetLon, this.roadMemory);
        const calcTime = performance.now() - startTime;
        
        if (!route.path || route.path.length <= 1) return false;

        this.currentPath = route.path;
        this.lastRouteBreakdown = pathfindingManager.estimateRouteCost(route);
        this.pathIndex = 0;
        this.status = 'moving';
        this.drawPathLine();
        
        // Track calculation history
        this._calcHistory.push({
            time: calcTime,
            nodes: route.path.length,
            timestamp: Date.now()
        });
        if (this._calcHistory.length > 20) this._calcHistory = this._calcHistory.slice(-20);
        
        return true;
    }

    async finishCharging() {
        if (this.resumeAfterCharge && this.currentDelivery) {
            this.resumeAfterCharge = false;
            this.routeMode = 'delivery';

            if (this.deliveryPhase === 'to_pickup') {
                this.routeTarget = {
                    lat: this.currentDelivery.pickup.lat,
                    lon: this.currentDelivery.pickup.lon
                };
                addDispatchInsight(`${this.name} resumed its interrupted pickup after charging.`, 'good');
                await this.buildRouteToTarget(this.currentDelivery.pickup.lat, this.currentDelivery.pickup.lon);
                return;
            }

            if (this.deliveryPhase === 'to_dropoff') {
                this.routeTarget = {
                    lat: this.currentDelivery.destination.lat,
                    lon: this.currentDelivery.destination.lon
                };
                addDispatchInsight(`${this.name} resumed its interrupted dropoff after charging.`, 'good');
                await this.buildRouteToTarget(this.currentDelivery.destination.lat, this.currentDelivery.destination.lon);
                return;
            }
        }

        this.status = 'idle';
        this.currentPath = [];
        this.pathIndex = 0;
        this.routeMode = null;
        this.routeTarget = null;
        this.clearPathLine();
    }
}
