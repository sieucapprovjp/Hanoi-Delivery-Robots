// Simple working robot
class DeliveryRobot {
    constructor(id, lat, lon, name, color) {
        this.id = id;
        this.lat = lat;
        this.lon = lon;
        this.name = name;
        this.color = color;
        this.speed = 0.000016; // closer to real sidewalk robot pacing
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
        this.speedMultiplier = Math.max(0.08, (0.55 * (1 - traffic * 0.65)) / rainPenalty); // rain doubles traversal cost
        this.maybeReroute(traffic, rainPenalty);

        // Update marker
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
            if (this.marker.isPopupOpen()) {
                this.updatePopup();
            }
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

        // Initialize with simple popup, update on click
        this.marker.bindPopup('Loading...');
        
        // Click handler to show detailed info
        this.marker.on('click', () => {
            this.updatePopup();
            this.marker.openPopup();
        });
    }

    updatePopup() {
        const deliveryInfo = this.currentDelivery ? 
            `<div style="margin: 8px 0; padding: 8px; background: #f8f9fa; border-radius: 6px;">
                <div style="font-size: 11px; color: #5f6368; margin-bottom: 4px;">📦 Current Delivery</div>
                <div style="font-size: 12px; font-weight: 600;">Order #${this.currentDelivery.id}</div>
                <div style="font-size: 11px; margin-top: 4px;">
                    ${this.deliveryPhase === 'pickup' ? '🔵 Going to pickup' : '🔴 Going to deliver'}
                </div>
            </div>` : 
            '<div style="margin: 8px 0; padding: 8px; background: #f8f9fa; border-radius: 6px; font-size: 12px; color: #5f6368;">No active delivery</div>';

        const destinationInfo = this.routeTarget ? 
            `<div style="margin: 8px 0; padding: 8px; background: #e8f5e9; border-radius: 6px;">
                <div style="font-size: 11px; color: #5f6368; margin-bottom: 4px;">🎯 Destination</div>
                <div style="font-size: 12px; font-weight: 600;">${this.routeTarget.lat.toFixed(5)}, ${this.routeTarget.lon.toFixed(5)}</div>
                <div style="font-size: 11px; margin-top: 4px;">${this.currentPath.length - this.pathIndex} waypoints remaining</div>
            </div>` : '';

        const batteryRisk = this.estimateBatteryRisk(this.totalDistance);
        const batteryColor = this.battery > 60 ? '#34a853' : this.battery > 30 ? '#fbbc04' : '#ea4335';
        
        const decisionInfo = this.lastRouteBreakdown ? 
            `<div style="margin: 8px 0; padding: 8px; background: #e3f2fd; border-radius: 6px;">
                <div style="font-size: 11px; color: #5f6368; margin-bottom: 4px;">🧠 Decision Making</div>
                <div style="font-size: 11px; line-height: 1.6;">
                    <div>Base distance: <strong>${this.lastRouteBreakdown.baseDistance.toFixed(0)}m</strong></div>
                    <div>Traffic penalty: <strong style="color: #ea4335;">+${this.lastRouteBreakdown.trafficPenalty.toFixed(0)}m</strong></div>
                    <div>Rain penalty: <strong style="color: #4285f4;">+${this.lastRouteBreakdown.rainPenalty.toFixed(0)}m</strong></div>
                    <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #bbdefb;">
                        Total cost: <strong>${this.lastRouteBreakdown.totalCost.toFixed(0)}m</strong>
                    </div>
                </div>
            </div>` : '';

        const popupContent = `
            <div style="min-width: 220px; font-family: 'Segoe UI', Arial, sans-serif;">
                <div style="font-size: 14px; font-weight: 700; color: ${this.color}; margin-bottom: 8px;">🤖 ${this.name}</div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
                    <div style="padding: 6px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                        <div style="font-size: 10px; color: #5f6368;">Status</div>
                        <div style="font-size: 12px; font-weight: 600;">${this.status}</div>
                    </div>
                    <div style="padding: 6px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                        <div style="font-size: 10px; color: #5f6368;">Speed</div>
                        <div style="font-size: 12px; font-weight: 600;">${(this.speedMultiplier * 100).toFixed(0)}%</div>
                    </div>
                </div>

                <div style="margin: 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-size: 11px; color: #5f6368;">🔋 Battery</span>
                        <span style="font-size: 13px; font-weight: 700; color: ${batteryColor};">${this.battery.toFixed(1)}%</span>
                    </div>
                    <div style="width: 100%; height: 6px; background: #dadce0; border-radius: 3px; overflow: hidden;">
                        <div style="width: ${this.battery}%; height: 100%; background: ${batteryColor}; border-radius: 3px; transition: width 0.3s;"></div>
                    </div>
                    <div style="font-size: 10px; color: #5f6368; margin-top: 4px;">Risk: ${batteryRisk.toFixed(1)}% drain projected</div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
                    <div style="padding: 6px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                        <div style="font-size: 10px; color: #5f6368;">Deliveries</div>
                        <div style="font-size: 14px; font-weight: 700; color: #34a853;">${this.totalDeliveries}</div>
                    </div>
                    <div style="padding: 6px; background: #f8f9fa; border-radius: 6px; text-align: center;">
                        <div style="font-size: 10px; color: #5f6368;">Distance</div>
                        <div style="font-size: 14px; font-weight: 700; color: #1a73e8;">${this.totalDistance.toFixed(0)}m</div>
                    </div>
                </div>

                ${destinationInfo}
                ${deliveryInfo}
                ${decisionInfo}
            </div>
        `;

        // Update popup content using correct Leaflet API
        const popup = this.marker.getPopup();
        if (popup) {
            popup.setContent(popupContent);
        }
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
        const route = await pathfindingManager.getRoute(this.lat, this.lon, targetLat, targetLon);
        if (!route.path || route.path.length <= 1) return false;

        this.currentPath = route.path;
        this.lastRouteBreakdown = pathfindingManager.estimateRouteCost(route);
        this.pathIndex = 0;
        this.status = 'moving';
        this.drawPathLine();
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
