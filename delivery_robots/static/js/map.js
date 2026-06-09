// Hanoi Map - Simple working version
class HanoiMap {
    constructor() {
        this.map = null;
        this.chargingStations = [];
        this.trafficJams = [];
        this.roadblocks = [];
        this.showDebugRoads = false;
        this.trafficLayers = [];
        this.trafficRefreshHandle = null;
        this.rainZones = [];
        this.rainLayers = [];
        this.rainOverlayEnabled = false;
        this.deliveryMarkers = new Map();
        this.hubLayers = [];

        // Predefined street paths (real Hoan Kiem streets)
        this.streets = CONFIG.DATA.STREETS;

        // Key intersections (connect points)
        this.intersections = CONFIG.DATA.INTERSECTIONS;

        this.roadGraph = new Map();
        this.buildRoadGraph();
    }

    initializeMap() {
        this.map = L.map('map').setView(CONFIG.MAP.INITIAL_VIEW, CONFIG.MAP.INITIAL_ZOOM);
        window.map = this.map; // Expose for weather/traffic controls

        L.tileLayer(CONFIG.MAP.TILE_LAYER_URL, {
            maxZoom: CONFIG.MAP.MAX_ZOOM,
            attribution: CONFIG.MAP.ATTRIBUTION
        }).addTo(this.map);

        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        this.drawStreets();
        this.setupChargingStations();
        this.loadWeather();
        this.startTraffic();

        console.log('✓ Map ready');
    }

    drawStreets() {
        if (!this.showDebugRoads) return;

        const colors = CONFIG.MAP.STREET_COLORS;

        this.streets.forEach(street => {
            const latlngs = street.points.map(p => [p[0], p[1]]);
            const colors = CONFIG.MAP.STREET_COLORS;
            L.polyline(latlngs, {
                color: colors[street.type] || CONFIG.UI.COLORS.background,
                weight: street.type === 'main' ? CONFIG.UI.WEIGHTS.thick + 1 : CONFIG.UI.WEIGHTS.markerSmall,
                opacity: CONFIG.UI.OPACITY.full - 0.1
            }).addTo(this.map).bindTooltip(street.name);
        });
    }

    async setupChargingStations() {
        let locations = CONFIG.DATA.CHARGING_STATIONS;
        try {
            const res = await fetch(CONFIG.API.CHARGING_STATIONS);
            if (res.ok) {
                const data = await res.json();
                if (Array.isArray(data.stations) && data.stations.length > 0) {
                    locations = data.stations;
                }
            }
        } catch (error) {
            console.warn('Failed to load charging stations from API, fallback to static config.', error);
        }

        locations.forEach(loc => {
            const station = {
                id: loc.id,
                lat: loc.lat, lon: loc.lon,
                name: loc.name, totalSpots: loc.spots, availableSpots: loc.spots,
                marker: null
            };

            station.marker = L.marker([loc.lat, loc.lon], {
                draggable: true,
                icon: L.divIcon({
                    className: 'charging-station-marker',
                    html: `<div class="charging-station-inner">⚡</div>`,
                    iconSize: [CONFIG.UI.RADII.markerLarge * 6, CONFIG.UI.RADII.markerLarge * 6], 
                    iconAnchor: [CONFIG.UI.RADII.markerLarge * 3, CONFIG.UI.RADII.markerLarge * 3]
                })
            }).addTo(this.map);

            station.marker.on('dragend', async (event) => {
                const latLng = event.target.getLatLng();
                const nextLat = latLng.lat;
                const nextLon = latLng.lng;
                station.lat = nextLat;
                station.lon = nextLon;

                if (!station.id) return;
                try {
                    const response = await fetch(`${CONFIG.API.CHARGING_STATIONS}/${station.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ lat: nextLat, lon: nextLon })
                    });
                    if (!response.ok) {
                        throw new Error(`Failed to save charging station #${station.id}`);
                    }
                } catch (error) {
                    console.error(error);
                }
            });

            this.chargingStations.push(station);
        });
    }

    async reloadChargingStations() {
        this.chargingStations.forEach(station => {
            if (station.marker) {
                station.marker.remove();
            }
        });
        this.chargingStations = [];
        await this.setupChargingStations();
    }

    enableRainOverlay() {
        if (this.rainOverlayEnabled) return;

        const style = document.createElement('style');
        style.textContent = `
            @keyframes rain { 0% { background-position: 0% 0%; } 100% { background-position: 20% 100%; } }
            #map::after {
                content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
                background: repeating-linear-gradient(170deg, rgba(174,194,224,0.1) 0px, rgba(174,194,224,0.15) 2px, transparent 2px, transparent 8px);
                animation: rain 0.5s linear infinite; pointer-events: none; z-index: 1000;
            }
        `;
        document.head.appendChild(style);
        this.rainOverlayEnabled = true;
    }

    async loadWeather() {
        this.enableRainOverlay();

        if (typeof pathfindingManager === 'undefined' || !pathfindingManager) {
            return;
        }

        try {
            const weather = await pathfindingManager.getWeather();
            this.rainZones = weather.rainZones || [];
            this.renderRainZones();
        } catch (error) {
            console.error('Weather load failed', error);
        }
    }

    renderRainZones() {
        this.rainLayers.forEach(layer => layer.remove());
        this.rainLayers = [];

        this.rainZones.forEach(zone => {
            const halo = L.circle([zone.center.lat, zone.center.lon], {
                radius: zone.radius,
                color: CONFIG.MAP.RAIN_COLORS.halo,
                weight: 2,
                opacity: 0.45,
                fillColor: CONFIG.MAP.RAIN_COLORS.fill,
                fillOpacity: 0.12
            }).addTo(this.map);

            const core = L.circle([zone.center.lat, zone.center.lon], {
                radius: zone.radius * CONFIG.MAP.RAIN_ZONES_CORE_SCALE,
                color: CONFIG.MAP.RAIN_COLORS.core,
                weight: 1,
                opacity: 0.3,
                fillColor: CONFIG.MAP.RAIN_COLORS.halo,
                fillOpacity: 0.12
            }).addTo(this.map).bindTooltip(`🌧 ${zone.name} rain x${zone.multiplier.toFixed(1)}`);

            this.rainLayers.push(halo, core);
        });
    }

    startTraffic() {
        this.refreshTraffic();
        this.trafficRefreshHandle = setInterval(() => this.refreshTraffic(), CONFIG.UI.TRAFFIC_REFRESH_INTERVAL_MS);
    }

    async refreshTraffic() {
        if (typeof pathfindingManager === 'undefined' || !pathfindingManager) {
            return;
        }

        try {
            const traffic = await pathfindingManager.getTraffic();
            this.trafficJams = traffic.roads;
            this.renderTraffic();
        } catch (error) {
            console.error('Traffic refresh failed', error);
        }
    }

    renderTraffic() {
        this.trafficLayers.forEach(layer => layer.remove());
        this.trafficLayers = [];

        this.trafficJams.forEach(road => {
            road.segments.forEach(segment => {
                const latlngs = segment.points.map(point => [point[0], point[1]]);
                const core = L.polyline(latlngs, {
                    color: segment.severity > 0.55 ? CONFIG.MAP.TRAFFIC_COLORS.heavy : CONFIG.MAP.TRAFFIC_COLORS.moderate,
                    weight: segment.severity > 0.55 ? 5 : 4,
                    opacity: 0.85,
                    lineCap: 'round',
                    dashArray: '10, 10'
                }).addTo(this.map).bindTooltip(`${road.name} traffic ${(segment.severity * 100).toFixed(0)}%`);

                this.trafficLayers.push(core);
            });
        });
    }

    startRoadblocks() {
        this.roadblocks = [];
    }

    buildRoadGraph() {
        this.roadGraph.clear();

        this.streets.forEach(street => {
            for (let i = 0; i < street.points.length; i++) {
                const [lat, lon] = street.points[i];
                const key = this.pointKey(lat, lon);

                if (!this.roadGraph.has(key)) {
                    this.roadGraph.set(key, {
                        key,
                        lat,
                        lon,
                        neighbors: []
                    });
                }

                if (i === 0) continue;

                const [prevLat, prevLon] = street.points[i - 1];
                const prevKey = this.pointKey(prevLat, prevLon);
                const distance = this.distance(lat, lon, prevLat, prevLon);

                this.roadGraph.get(key).neighbors.push({
                    key: prevKey,
                    distance
                });
                this.roadGraph.get(prevKey).neighbors.push({
                    key,
                    distance
                });
            }
        });
    }

    pointKey(lat, lon) {
        return `${lat.toFixed(6)},${lon.toFixed(6)}`;
    }

    getNearestGraphNode(lat, lon) {
        let nearestNode = null;
        let minDist = Infinity;

        this.roadGraph.forEach(node => {
            const dist = this.distance(lat, lon, node.lat, node.lon);
            if (dist < minDist) {
                minDist = dist;
                nearestNode = node;
            }
        });

        return nearestNode;
    }

    snapToRoad(lat, lon) {
        const node = this.getNearestGraphNode(lat, lon);
        if (!node) {
            return { lat, lon };
        }

        return { lat: node.lat, lon: node.lon };
    }

    findShortestPath(startKey, endKey) {
        if (!this.roadGraph.has(startKey) || !this.roadGraph.has(endKey)) {
            return [];
        }

        const distances = new Map();
        const previous = new Map();
        const unvisited = new Set(this.roadGraph.keys());

        this.roadGraph.forEach((_, key) => distances.set(key, Infinity));
        distances.set(startKey, 0);

        while (unvisited.size > 0) {
            let currentKey = null;
            let currentDistance = Infinity;

            unvisited.forEach(key => {
                const dist = distances.get(key);
                if (dist < currentDistance) {
                    currentDistance = dist;
                    currentKey = key;
                }
            });

            if (!currentKey || currentDistance === Infinity) break;

            unvisited.delete(currentKey);

            if (currentKey === endKey) break;

            const currentNode = this.roadGraph.get(currentKey);
            currentNode.neighbors.forEach(neighbor => {
                if (!unvisited.has(neighbor.key)) return;
                if (this.isRoadBlocked(currentNode, this.roadGraph.get(neighbor.key))) return;

                const trafficPenalty = this.getSegmentTrafficPenalty(currentNode, this.roadGraph.get(neighbor.key));
                const candidateDistance = currentDistance + neighbor.distance * trafficPenalty;

                if (candidateDistance < distances.get(neighbor.key)) {
                    distances.set(neighbor.key, candidateDistance);
                    previous.set(neighbor.key, currentKey);
                }
            });
        }

        const path = [];
        let currentKey = endKey;

        if (startKey !== endKey && !previous.has(endKey)) {
            return [];
        }

        while (currentKey) {
            const node = this.roadGraph.get(currentKey);
            path.unshift({ lat: node.lat, lon: node.lon });
            currentKey = previous.get(currentKey);
        }

        return path;
    }

    getSegmentTrafficPenalty(fromNode, toNode) {
        const midpoint = {
            lat: (fromNode.lat + toNode.lat) / 2,
            lon: (fromNode.lon + toNode.lon) / 2
        };
        const traffic = this.getTrafficAt(midpoint.lat, midpoint.lon);
        return 1 + traffic * CONFIG.MAP.TRAFFIC_PENALTY_MULTIPLIER;
    }

    isRoadBlocked(fromNode, toNode) {
        return this.roadblocks.some(block => {
            const midpointLat = (fromNode.lat + toNode.lat) / 2;
            const midpointLon = (fromNode.lon + toNode.lon) / 2;
            return this.distance(midpointLat, midpointLon, block.lat, block.lon) < CONFIG.MAP.ROADBLOCK_DISTANCE_THRESHOLD;
        });
    }

    // Get path between two points using the road graph
    getRoute(fromLat, fromLon, toLat, toLon) {
        const startNode = this.getNearestGraphNode(fromLat, fromLon);
        const endNode = this.getNearestGraphNode(toLat, toLon);

        if (!startNode || !endNode) {
            return [{ lat: fromLat, lon: fromLon }, { lat: toLat, lon: toLon }];
        }

        const graphPath = this.findShortestPath(startNode.key, endNode.key);

        if (graphPath.length === 0) {
            return [{ lat: fromLat, lon: fromLon }, { lat: toLat, lon: toLon }];
        }

        return graphPath.filter((point, index, points) => {
            if (index === 0) return true;
            const previous = points[index - 1];
            return previous.lat !== point.lat || previous.lon !== point.lon;
        });
    }

    snapToStreet(lat, lon) {
        let nearest = { lat, lon };
        let minDist = Infinity;

        this.streets.forEach(street => {
            street.points.forEach(point => {
                const dist = this.distance(lat, lon, point[0], point[1]);
                if (dist < minDist) {
                    minDist = dist;
                    nearest = { lat: point[0], lon: point[1] };
                }
            });
        });

        return nearest;
    }

    getTrafficAt(lat, lon) {
        let traffic = 0;
        this.trafficJams.forEach(road => {
            road.segments.forEach(segment => {
                const [[startLat, startLon], [endLat, endLon]] = segment.points;
                const dist = this.distanceToSegment(lat, lon, startLat, startLon, endLat, endLon);
                const radius = CONFIG.MAP.TRAFFIC_RADIUS;

                if (dist < radius) {
                    traffic = Math.max(traffic, segment.severity * (1 - dist / radius));
                }
            });
        });
        return traffic;
    }

    getRainPenaltyAt(lat, lon) {
        let penalty = 1;

        this.rainZones.forEach(zone => {
            const dist = this.distance(lat, lon, zone.center.lat, zone.center.lon);
            if (dist < zone.radius) {
                penalty = Math.max(penalty, zone.multiplier);
            }
        });

        return penalty;
    }

    distanceToSegment(lat, lon, startLat, startLon, endLat, endLon) {
        const originLat = (lat + startLat + endLat) / 3;
        const metersPerDegLat = CONFIG.MAP.METERS_PER_DEGREE;
        const metersPerDegLon = CONFIG.MAP.METERS_PER_DEGREE * Math.cos(originLat * Math.PI / 180);

        const px = lon * metersPerDegLon;
        const py = lat * metersPerDegLat;
        const ax = startLon * metersPerDegLon;
        const ay = startLat * metersPerDegLat;
        const bx = endLon * metersPerDegLon;
        const by = endLat * metersPerDegLat;

        const abx = bx - ax;
        const aby = by - ay;
        const abLenSq = abx * abx + aby * aby;

        if (abLenSq === 0) {
            return Math.hypot(px - ax, py - ay);
        }

        const t = Math.max(0, Math.min(1, ((px - ax) * abx + (py - ay) * aby) / abLenSq));
        const closestX = ax + t * abx;
        const closestY = ay + t * aby;
        return Math.hypot(px - closestX, py - closestY);
    }

    distance(lat1, lon1, lat2, lon2) {
        const R = CONFIG.MAP.EARTH_RADIUS_METERS;
        const φ1 = lat1 * Math.PI / 180;
        const φ2 = lat2 * Math.PI / 180;
        return R * Math.acos(
            Math.sin(φ1) * Math.sin(φ2) +
            Math.cos(φ1) * Math.cos(φ2) * Math.cos((lon2 - lon1) * Math.PI / 180)
        );
    }

    occupyChargingSpot(station) {
        if (station && station.availableSpots > 0) {
            station.availableSpots--;
            return true;
        }
        return false;
    }

    releaseChargingSpot(station) {
        if (station) station.availableSpots++;
    }

    showDeliveryMarkers(delivery) {
        this.clearDeliveryMarkers(delivery.id);

        const pickupMarker = L.marker([delivery.pickup.lat, delivery.pickup.lon], {
            icon: L.divIcon({
                className: 'delivery-pin-icon',
                html: `
                    <div class="delivery-pin pickup">
                        <div class="delivery-pin-badge">${delivery.theme?.pickupIcon || 'P'}</div>
                        <div class="delivery-pin-name">${delivery.pickup.name}</div>
                    </div>
                `,
                iconSize: [120, 40],
                iconAnchor: [24, 34]
            })
        }).addTo(this.map);

        const dropoffMarker = L.marker([delivery.destination.lat, delivery.destination.lon], {
            icon: L.divIcon({
                className: 'delivery-pin-icon',
                html: `
                    <div class="delivery-pin dropoff">
                        <div class="delivery-pin-badge">${delivery.theme?.dropoffIcon || 'D'}</div>
                        <div class="delivery-pin-name">${delivery.destination.name}</div>
                    </div>
                `,
                iconSize: [120, 40],
                iconAnchor: [24, 34]
            })
        }).addTo(this.map);

        this.deliveryMarkers.set(delivery.id, { pickupMarker, dropoffMarker });
    }

    clearDeliveryMarkers(deliveryId) {
        const markers = this.deliveryMarkers.get(deliveryId);
        if (!markers) return;

        markers.pickupMarker?.remove();
        markers.dropoffMarker?.remove();
        this.deliveryMarkers.delete(deliveryId);
    }

    clearAllDeliveryMarkers() {
        Array.from(this.deliveryMarkers.keys()).forEach(deliveryId => this.clearDeliveryMarkers(deliveryId));
    }

    drawHubs(hubs) {
        this.hubLayers.forEach(layer => layer.remove());
        this.hubLayers = [];

        hubs.forEach(hub => {
            const marker = L.marker([hub.lat, hub.lon], {
                icon: L.divIcon({
                    className: 'hub-marker',
                    html: `<div class="hub-marker-inner">🧠</div>`,
                    iconSize: [34, 34],
                    iconAnchor: [17, 17]
                })
            }).addTo(this.map).bindPopup(`<strong>${hub.name}</strong><br>Optimized with k-means`);

            const ring = L.circle([hub.lat, hub.lon], {
                radius: CONFIG.MAP.HUB_RING_RADIUS,
                color: CONFIG.MAP.HUB_COLOR,
                weight: CONFIG.MAP.HUB_RING_WEIGHT,
                opacity: CONFIG.MAP.HUB_RING_OPACITY,
                fillColor: CONFIG.MAP.HUB_COLOR,
                fillOpacity: CONFIG.MAP.HUB_FILL_OPACITY
            }).addTo(this.map);

            this.hubLayers.push(marker, ring);
        });
    }
}
