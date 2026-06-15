// Leaflet map facade for base layers, overlays, and local graph helpers.
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

        this.streets = CONFIG.DATA.STREETS;

        this.intersections = CONFIG.DATA.INTERSECTIONS;

        this.roadGraph = new Map();
        this.buildRoadGraph();
    }

    initializeMap() {
        this.map = L.map('map').setView(CONFIG.MAP.INITIAL_VIEW, CONFIG.MAP.INITIAL_ZOOM);
        window.map = this.map;

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
            L.polyline(latlngs, {
                color: colors[street.type] || CONFIG.UI.COLORS.background,
                weight: street.type === 'main' ? CONFIG.UI.WEIGHTS.thick + 1 : CONFIG.UI.WEIGHTS.thin,
                opacity: CONFIG.UI.OPACITY.full - 0.1
            }).addTo(this.map).bindTooltip(street.name);
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

}
