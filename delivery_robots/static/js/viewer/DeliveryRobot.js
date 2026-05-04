class DeliveryRobot {
    constructor(id, lat, lon, name, color) {
        this.id = id;
        this.lat = lat;
        this.lon = lon;
        this.name = name;
        this.color = color;
        this.speed = CONFIG.ROBOT.DEFAULT_SPEED;
        this.status = CONFIG.ROBOT.STATUSES.IDLE;
        this.currentPath = [];
        this.pathIndex = 0;
        this.marker = null;
        this.pathLine = null;
        this.speedMultiplier = 1;
        this.routeTarget = null;
        this.deliveryPhase = null;
        this.battery = 100;
        this.currentPathLength = 0;
    }

    update() {
        if (this.status === CONFIG.ROBOT.STATUSES.IDLE) return;

        if (!this.currentPath || this.currentPath.length === 0 || this.pathIndex >= this.currentPath.length - 1) {
            return;
        }

        const target = this.currentPath[this.pathIndex + 1];
        const dist = this.distanceTo(target);

        let currentSpeed = this.speed * this.speedMultiplier;
        let lag = (this.backendPathIndex || 0) - this.pathIndex;
        if (lag > 0) {
            currentSpeed *= (1 + lag * 2);
        }

        // Smooth interpolation
        if (dist < currentSpeed) {
            this.lat = target.lat;
            this.lon = target.lon;
            // Only advance if backend has already moved past this target
            if ((this.backendPathIndex || 0) >= this.pathIndex + 1) {
                this.pathIndex++;
            }
        } else {
            const ratio = currentSpeed / dist;
            this.lat += (target.lat - this.lat) * ratio;
            this.lon += (target.lon - this.lon) * ratio;
        }

        // Update marker
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
        }

        // Dynamically trim the path line
        if (this.pathLine && this.currentPath && this.currentPath.length > 0) {
            const remainingPath = [[this.lat, this.lon]];
            for (let i = this.pathIndex + 1; i < this.currentPath.length; i++) {
                remainingPath.push([this.currentPath[i].lat, this.currentPath[i].lon]);
            }
            this.pathLine.setLatLngs(remainingPath);
        }
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
        });
    }

    removeMarker() {
        if (this.marker) {
            this.marker.remove();
            this.marker = null;
        }
        this.clearPathLine();
    }

    updatePopup() {
        let decisionState = CONFIG.UI.STATE_LABELS.IDLE;
        if (this.status !== CONFIG.ROBOT.STATUSES.IDLE) {
            if (this.status === 'moving_to_pickup') decisionState = CONFIG.UI.STATE_LABELS.ROUTING_PICKUP;
            else if (this.status === 'moving_to_dropoff') decisionState = CONFIG.UI.STATE_LABELS.ROUTING_DROPOFF;
            else decisionState = CONFIG.UI.STATE_LABELS.MOVING;
        }

        const content = `
            <div class="robot-popup">
                <div class="popup-title" style="--robot-color: ${this.color}">🤖 ${this.name}</div>
                
                <div class="popup-status-badge ${this.status === CONFIG.ROBOT.STATUSES.MOVING ? 'status-success' : 'status-neutral'}">
                    ${decisionState}
                </div>

                <div class="popup-grid-2">
                    <div class="grid-item"><div class="item-label">Status</div><div class="item-value">${this.status.toUpperCase()}</div></div>
                    <div class="grid-item"><div class="item-label">Battery</div><div class="item-value">${(this.battery || 100).toFixed(1)}%</div></div>
                </div>

                ${this.routeTarget ? `<div class="popup-info-box status-success">🎯 Target: ${this.routeTarget}<br>${(this.currentPathLength || this.currentPath.length) - this.pathIndex} waypoints left</div>` : ''}
            </div>
        `;

        const popup = this.marker.getPopup();
        if (popup) popup.setContent(content);
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

    setPath(path, target = null, phase = null, startIndex = 0) {
        this.currentPath = path;
        this.pathIndex = startIndex;
        this.routeTarget = target;
        this.deliveryPhase = phase;
        this.status = path.length > 0 ? CONFIG.ROBOT.STATUSES.MOVING : CONFIG.ROBOT.STATUSES.IDLE;
        
        if (startIndex > 0 && startIndex < path.length) {
            this.lat = path[startIndex].lat;
            this.lon = path[startIndex].lon;
            if (this.marker) this.marker.setLatLng([this.lat, this.lon]);
        }
        
        this.drawPathLine();
    }
}