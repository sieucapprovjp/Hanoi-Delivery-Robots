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
    }

    update() {
        if (this.status !== CONFIG.ROBOT.STATUSES.MOVING) return;

        if (this.currentPath.length === 0 || this.pathIndex >= this.currentPath.length - 1) {
            this.status = CONFIG.ROBOT.STATUSES.IDLE;
            return;
        }

        const target = this.currentPath[this.pathIndex + 1];
        const dist = this.distanceTo(target);

        // Smooth interpolation
        if (dist < this.speed * this.speedMultiplier) {
            this.lat = target.lat;
            this.lon = target.lon;
            this.pathIndex++;

            if (this.pathIndex >= this.currentPath.length - 1) {
                this.status = CONFIG.ROBOT.STATUSES.IDLE;
            }
        } else {
            const ratio = (this.speed * this.speedMultiplier) / dist;
            this.lat += (target.lat - this.lat) * ratio;
            this.lon += (target.lon - this.lon) * ratio;
        }

        // Update marker
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
            if (this.marker.isPopupOpen()) this.updatePopup();
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
        if (this.status === CONFIG.ROBOT.STATUSES.MOVING) {
            if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_PICKUP) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_PICKUP;
            else if (this.deliveryPhase === CONFIG.ROBOT.PHASES.TO_DROPOFF) decisionState = CONFIG.UI.STATE_LABELS.ROUTING_DROPOFF;
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
                    <div class="grid-item"><div class="item-label">Position</div><div class="item-value">${this.lat.toFixed(4)}, ${this.lon.toFixed(4)}</div></div>
                </div>

                ${this.routeTarget ? `<div class="popup-info-box status-success">🎯 Target: ${this.routeTarget.lat.toFixed(4)}, ${this.routeTarget.lon.toFixed(4)}<br>${this.currentPath.length - this.pathIndex} waypoints left</div>` : ''}
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

    setPath(path, target = null, phase = null) {
        this.currentPath = path;
        this.pathIndex = 0;
        this.routeTarget = target;
        this.deliveryPhase = phase;
        this.status = path.length > 0 ? CONFIG.ROBOT.STATUSES.MOVING : CONFIG.ROBOT.STATUSES.IDLE;
        this.drawPathLine();
    }
}