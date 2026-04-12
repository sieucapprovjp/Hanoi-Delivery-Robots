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
        this.deliveryMarkers = new Map();
        this.trafficRoads = [
            {
                name: 'Le Thai To',
                points: [[21.0240,105.8480],[21.0250,105.8486],[21.0260,105.8492],[21.0270,105.8498],[21.0280,105.8504],[21.0290,105.8509],[21.0300,105.8513]],
                severity: 0.9,
                radius: 28
            },
            {
                name: 'Dinh Tien Hoang',
                points: [[21.0300,105.8513],[21.0310,105.8517],[21.0320,105.8521],[21.0330,105.8525],[21.0340,105.8529],[21.0355,105.8532]],
                severity: 0.75,
                radius: 28
            },
            {
                name: 'Hai Ba Trung',
                points: [[21.0220,105.8510],[21.0240,105.8515],[21.0260,105.8520],[21.0280,105.8525],[21.0300,105.8530]],
                severity: 0.65,
                radius: 32
            }
        ];
        
        // Predefined street paths (real Hoan Kiem streets)
        this.streets = [
            { name: "Phố Lê Thái Tổ", points: [[21.0240,105.8480],[21.0250,105.8486],[21.0260,105.8492],[21.0270,105.8498],[21.0280,105.8504],[21.0290,105.8509],[21.0300,105.8513]], type: "main" },
            { name: "Phố Đinh Tiên Hoàng", points: [[21.0300,105.8513],[21.0310,105.8517],[21.0320,105.8521],[21.0330,105.8525],[21.0340,105.8529],[21.0355,105.8532]], type: "main" },
            { name: "Phố Tràng Tiền", points: [[21.0240,105.8480],[21.0243,105.8492],[21.0247,105.8505],[21.0252,105.8518],[21.0256,105.8530]], type: "main" },
            { name: "Phố Hàng Khay", points: [[21.0256,105.8530],[21.0262,105.8534],[21.0270,105.8538],[21.0278,105.8543],[21.0285,105.8548]], type: "main" },
            { name: "Phố Hai Bà Trưng", points: [[21.0220,105.8510],[21.0240,105.8515],[21.0260,105.8520],[21.0280,105.8525],[21.0300,105.8530]], type: "main" },
            { name: "Phố Lý Thường Kiệt", points: [[21.0210,105.8500],[21.0230,105.8505],[21.0250,105.8510],[21.0270,105.8515],[21.0290,105.8520]], type: "main" },
            { name: "Phố Hàng Đào", points: [[21.0300,105.8530],[21.0310,105.8528],[21.0320,105.8526],[21.0330,105.8524],[21.0340,105.8522],[21.0350,105.8520]], type: "secondary" },
            { name: "Phố Hàng Ngang", points: [[21.0305,105.8538],[21.0315,105.8536],[21.0325,105.8534],[21.0335,105.8532],[21.0345,105.8530]], type: "secondary" },
            { name: "Phố Đồng Xuân", points: [[21.0345,105.8530],[21.0350,105.8525],[21.0353,105.8519],[21.0355,105.8516]], type: "secondary" },
            { name: "Phố Bà Triệu", points: [[21.0220,105.8510],[21.0230,105.8513],[21.0240,105.8515],[21.0250,105.8517],[21.0260,105.8520]], type: "secondary" }
        ];

        // Key intersections (connect points)
        this.intersections = [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Lake", connections: [0,1,3] },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien", connections: [1,2] },
            { lat: 21.0265, lon: 105.8505, name: "Hang Bai", connections: [2] },
            { lat: 21.0275, lon: 105.8520, name: "Dinh Tien Hoang", connections: [0] }
        ];

        this.roadGraph = new Map();
        this.buildRoadGraph();
    }

    initializeMap() {
        this.map = L.map('map').setView([21.0285, 105.8542], 16);
        window.map = this.map; // Expose for weather/traffic controls

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(this.map);

        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        this.drawStreets();
        this.setupChargingStations();
        this.loadWeather();
        this.startTraffic();
        this.startRoadblocks();

        console.log('✓ Map ready');
    }

    drawStreets() {
        if (!this.showDebugRoads) return;

        const colors = { main: '#ffa94d', secondary: '#ffd43b', residential: '#e9ecef' };
        
        this.streets.forEach(street => {
            const latlngs = street.points.map(p => [p[0], p[1]]);
            L.polyline(latlngs, {
                color: colors[street.type] || '#e9ecef',
                weight: street.type === 'main' ? 6 : 4,
                opacity: 0.9
            }).addTo(this.map).bindTooltip(street.name);
        });
    }

    setupChargingStations() {
        const locations = [
            { lat: 21.0285, lon: 105.8542, name: "Hoan Kiem Hub", spots: 3 },
            { lat: 21.0355, lon: 105.8516, name: "Dong Xuan", spots: 2 },
            { lat: 21.0240, lon: 105.8480, name: "Trang Tien", spots: 2 },
            { lat: 21.0220, lon: 105.8510, name: "Ly Thuong Kiet", spots: 2 },
            { lat: 21.0300, lon: 105.8530, name: "Hang Ngang", spots: 2 },
            { lat: 21.0275, lon: 105.8520, name: "Opera House", spots: 2 }
        ];

        locations.forEach(loc => {
            const station = {
                lat: loc.lat, lon: loc.lon,
                name: loc.name, totalSpots: loc.spots, availableSpots: loc.spots,
                marker: null
            };

            station.marker = L.marker([loc.lat, loc.lon], {
                icon: L.divIcon({
                    html: `<div style="width:40px;height:40px;background:#34a853;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;border:3px solid white;">⚡</div>`,
                    iconSize: [40, 40], iconAnchor: [20, 20]
                })
            }).addTo(this.map);

            this.chargingStations.push(station);
        });
    }

    enableRainOverlay() {
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
                color: '#4dabf7',
                weight: 2,
                opacity: 0.45,
                fillColor: '#74c0fc',
                fillOpacity: 0.12
            }).addTo(this.map);

            const core = L.circle([zone.center.lat, zone.center.lon], {
                radius: zone.radius * 0.62,
                color: '#228be6',
                weight: 1,
                opacity: 0.3,
                fillColor: '#4dabf7',
                fillOpacity: 0.12
            }).addTo(this.map).bindTooltip(`🌧 ${zone.name} rain x${zone.multiplier.toFixed(1)}`);

            this.rainLayers.push(halo, core);
        });
    }

    startTraffic() {
        this.refreshTraffic();
        this.trafficRefreshHandle = setInterval(() => this.refreshTraffic(), 3500);
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
                    color: segment.severity > 0.55 ? '#ff6b6b' : '#ff922b',
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
        // 1 roadblock
        this.roadblocks = [
            { lat: 21.0270, lon: 105.8515, reason: "Construction" }
        ];

        this.roadblocks.forEach(rb => {
            L.marker([rb.lat, rb.lon], {
                icon: L.divIcon({
                    html: `<div style="width:36px;height:36px;background:#ff6b6b;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;border:3px solid white;">🚧</div>`,
                    iconSize: [36, 36], iconAnchor: [18, 18]
                })
            }).addTo(this.map).bindPopup(`<strong>🚧 Roadblock</strong><br>${rb.reason}`);
        });
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
        return 1 + traffic * 2;
    }

    isRoadBlocked(fromNode, toNode) {
        return this.roadblocks.some(block => {
            const midpointLat = (fromNode.lat + toNode.lat) / 2;
            const midpointLon = (fromNode.lon + toNode.lon) / 2;
            return this.distance(midpointLat, midpointLon, block.lat, block.lon) < 35;
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
                const radius = 26;

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
        const metersPerDegLat = 111320;
        const metersPerDegLon = 111320 * Math.cos(originLat * Math.PI / 180);

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
        const R = 6371e3;
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
}
