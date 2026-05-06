class DeliveryRobot {
    constructor(id, lat, lon, name, color) {
        this.id = id;
        this.lat = lat;
        this.lon = lon;
        this.name = name;
        this.color = color;
        this.status = CONFIG.ROBOT.STATUSES.IDLE;
        this.currentPath = [];       // node-level coords [{lat,lon},...] — length tracking
        this.geometryPath = [];      // flat geometry coords [{lat,lon},...] — for drawing
        this.segmentGeometry = [];   // [[{lat,lon},...], ...] — per-node-segment for interpolation
        this.pathIndex = 0;
        this.marker = null;
        this.pathLine = null;
        this.speedMultiplier = 1;
        this.routeTarget = null;
        this.deliveryPhase = null;
        this.battery = 100;
        this.currentPathLength = 0;
        this.simElapsedSec = 0;
        this.lastUpdateTime = null;
        this.segmentDuration = 0;
        this._lastPathIndex = -1;
    }

    update() {
        if (this.status === CONFIG.ROBOT.STATUSES.IDLE) return;

        const hasGeometry = this.segmentGeometry && this.segmentGeometry.length > 0;
        const hasPath = this.currentPath && this.currentPath.length > 0;

        if (!hasGeometry && !hasPath) return;
        if (hasGeometry && this.pathIndex >= this.segmentGeometry.length) return;
        if (hasPath && !hasGeometry && this.pathIndex >= this.currentPath.length - 1) return;

        this._updateMovement();
        this._updateMarker();
        this._updatePathLineVisual();
    }

    _updateMovement() {
        // Initialize or reset timer when moving to a new segment
        if (this._lastPathIndex !== this.pathIndex) {
            this._lastPathIndex = this.pathIndex;
        }

        if (!this.lastUpdateTime) this.lastUpdateTime = Date.now();
        const now = Date.now();
        const dtRealMs = now - this.lastUpdateTime;
        this.lastUpdateTime = now;

        const isPaused = window.displayEngine && window.displayEngine.isPaused;

        if (!isPaused) {
            // Get simulation speed to convert real elapsed time to simulation time
            const simSpeed = (window.Alpine && Alpine.store('sim')) ? (Alpine.store('sim').speed || 60) : 60;
            let dtSimSec = (dtRealMs / 1000) * simSpeed * this.speedMultiplier;

            // Handle lag by artificially increasing elapsed time.
            // We only compensate if lag > 1 (i.e. backend is at least 2 nodes ahead),
            // because lag = 1 simply means the backend finished the segment slightly before us.
            const lag = (this.backendPathIndex || 0) - this.pathIndex;
            if (lag > 1) {
                dtSimSec *= (1 + (lag - 1) * 2);
            }
            
            this.simElapsedSec = (this.simElapsedSec || 0) + dtSimSec;
        }

        // Use the segment duration specific to the segment we are currently interpolating
        const duration = (this.backendDurations && this.backendDurations[this.pathIndex] !== undefined)
            ? this.backendDurations[this.pathIndex]
            : this.segmentDuration;

        // Calculate interpolation ratio (t): 0 = segment start, 1 = segment end
        let rawT = duration > 0 ? (this.simElapsedSec || 0) / duration : 1;
        let t = Math.min(1, Math.max(0, rawT));

        // Geometry-aware interpolation: proportional to sub-segment distances
        const segGeo = this.segmentGeometry[this.pathIndex];
        if (segGeo && segGeo.length >= 2) {
            [this.lat, this.lon] = this._interpolateAlongGeometry(segGeo, t);
        } else {
            // Fallback: straight-line interpolation between node coords
            const startNode = this.currentPath[this.pathIndex];
            const target = this.currentPath[this.pathIndex + 1];
            if (startNode && target) {
                this.lat = startNode.lat + (target.lat - startNode.lat) * t;
                this.lon = startNode.lon + (target.lon - startNode.lon) * t;
            }
        }

        // Advance to next node if interpolation is complete AND backend has moved on
        if (t >= 1 && (this.backendPathIndex || 0) >= this.pathIndex + 1) {
            this.pathIndex++;
            
            if (rawT > 0 && duration > 0) {
                // Preserve fractional time overage perfectly by subtracting the consumed duration
                this.simElapsedSec -= duration;
            } else {
                this.simElapsedSec = 0;
            }
        }
    }

    /**
     * Interpolate position along a geometry sub-path proportionally by distance.
     * Since speed is constant within the node segment, t (time ratio) == distance ratio.
     *
     * @param {Array<{lat,lon}>} segGeo - Geometry points for the current node segment
     * @param {number} t - Time/distance ratio in [0, 1]
     * @returns {[number, number]} [lat, lon]
     */
    _interpolateAlongGeometry(segGeo, t) {
        // 1. Build cumulative distance array
        const distances = [0];
        for (let i = 1; i < segGeo.length; i++) {
            distances.push(
                distances[i - 1] + this._haversineM(
                    segGeo[i - 1].lat, segGeo[i - 1].lon,
                    segGeo[i].lat, segGeo[i].lon
                )
            );
        }
        const totalDist = distances[distances.length - 1];

        // Edge case: all points are the same location
        if (totalDist === 0) return [segGeo[0].lat, segGeo[0].lon];

        const targetDist = t * totalDist;

        // 2. Find the sub-segment that contains targetDist
        for (let i = 1; i < segGeo.length; i++) {
            if (distances[i] >= targetDist || i === segGeo.length - 1) {
                this.currentSubSegmentIndex = i;
                const segLen = distances[i] - distances[i - 1];
                const localT = segLen > 0
                    ? (targetDist - distances[i - 1]) / segLen
                    : 1;
                const a = segGeo[i - 1];
                const b = segGeo[i];
                return [
                    a.lat + (b.lat - a.lat) * localT,
                    a.lon + (b.lon - a.lon) * localT,
                ];
            }
        }

        this.currentSubSegmentIndex = segGeo.length - 1;
        // Should never reach here, but return last point as safety
        return [segGeo[segGeo.length - 1].lat, segGeo[segGeo.length - 1].lon];
    }

    /**
     * Haversine distance between two lat/lon points in metres.
     * Pure JS — no external dependency needed.
     */
    _haversineM(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) ** 2
            + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180)
            * Math.sin(dLon / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    /**
     * Returns the index in the flat geometryPath where node `nodeIdx` begins.
     * Used to trim the displayed remaining path correctly.
     *
     * Each segment_geometry[i] has its own point list. When built into the flat
     * geometryPath, junction points are deduplicated (segment[i][-1] == segment[i+1][0]).
     * So the geometry flat index for node i = sum of (seg.length - 1) for seg in [0..i-1].
     */
    _getGeometryIndexForNode(nodeIdx) {
        let idx = 0;
        const limit = Math.min(nodeIdx, this.segmentGeometry.length);
        for (let i = 0; i < limit; i++) {
            idx += this.segmentGeometry[i].length - 1;
        }
        return idx;
    }

    _updateMarker() {
        if (this.marker) {
            this.marker.setLatLng([this.lat, this.lon]);
        }
    }

    _updatePathLineVisual() {
        if (!this.pathLine) return;

        if (this.geometryPath && this.geometryPath.length > 0) {
            const remaining = [[this.lat, this.lon]];

            // Add remaining subnodes from current segment
            const segGeo = this.segmentGeometry[this.pathIndex];
            if (segGeo && this.currentSubSegmentIndex !== undefined) {
                for (let i = this.currentSubSegmentIndex; i < segGeo.length; i++) {
                    remaining.push([segGeo[i].lat, segGeo[i].lon]);
                }
            }

            // Trim geometry path to start from next node boundary
            const geoStartIdx = this._getGeometryIndexForNode(this.pathIndex + 1);
            // Skip the first point of the next segment to avoid duplicate junction point
            for (let i = geoStartIdx + 1; i < this.geometryPath.length; i++) {
                remaining.push([this.geometryPath[i].lat, this.geometryPath[i].lon]);
            }
            this.pathLine.setLatLngs(remaining);
        } else if (this.currentPath && this.currentPath.length > 0) {
            // Fallback: use node coords
            const remaining = [[this.lat, this.lon]];
            for (let i = this.pathIndex + 1; i < this.currentPath.length; i++) {
                remaining.push([this.currentPath[i].lat, this.currentPath[i].lon]);
            }
            this.pathLine.setLatLngs(remaining);
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

        // Prefer geometry path for accurate road-following display
        const pathToDraw = (this.geometryPath && this.geometryPath.length > 1)
            ? this.geometryPath
            : this.currentPath;

        if (pathToDraw.length > 1) {
            const latlngs = pathToDraw.map(p => [p.lat, p.lon]);
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

    setPath(path, geometryPath = [], segmentGeometry = [], target = null, phase = null, startIndex = 0) {
        this.currentPath = path;
        this.geometryPath = geometryPath;
        this.segmentGeometry = segmentGeometry;
        this.pathIndex = startIndex;
        this.routeTarget = target;
        this.deliveryPhase = phase;
        this.status = (path.length > 0 || geometryPath.length > 0) ? CONFIG.ROBOT.STATUSES.MOVING : CONFIG.ROBOT.STATUSES.IDLE;
        this.backendDurations = {}; // Reset durations for new path

        // Reset time-based interpolation
        this._lastPathIndex = -1;
        this.simElapsedSec = 0;
        this.lastUpdateTime = Date.now();

        if (startIndex > 0) {
            if (segmentGeometry.length > 0 && startIndex < segmentGeometry.length) {
                this.lat = segmentGeometry[startIndex][0].lat;
                this.lon = segmentGeometry[startIndex][0].lon;
                if (this.marker) this.marker.setLatLng([this.lat, this.lon]);
            } else if (path.length > 0 && startIndex < path.length) {
                this.lat = path[startIndex].lat;
                this.lon = path[startIndex].lon;
                if (this.marker) this.marker.setLatLng([this.lat, this.lon]);
            }
        }

        this.drawPathLine();
    }
}