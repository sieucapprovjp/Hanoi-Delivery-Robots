HanoiMap.prototype.showDeliveryMarkers = function (delivery) {
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
            iconSize: [36, 36],
            iconAnchor: [18, 18]
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
            iconSize: [36, 36],
            iconAnchor: [18, 18]
        })
    }).addTo(this.map);

    this.deliveryMarkers.set(delivery.id, { pickupMarker, dropoffMarker });
};

HanoiMap.prototype.clearDeliveryMarkers = function (deliveryId) {
    const markers = this.deliveryMarkers.get(deliveryId);
    if (!markers) return;

    markers.pickupMarker?.remove();
    markers.dropoffMarker?.remove();
    this.deliveryMarkers.delete(deliveryId);
};

HanoiMap.prototype.clearAllDeliveryMarkers = function () {
    Array.from(this.deliveryMarkers.keys()).forEach(deliveryId => this.clearDeliveryMarkers(deliveryId));
};

HanoiMap.prototype.drawHubs = function (hubs) {
    this.hubLayers.forEach(layer => layer.remove());
    this.hubLayers = [];

    hubs.forEach(hub => {
        const marker = L.marker([hub.lat, hub.lon], {
            icon: L.divIcon({
                className: 'hub-marker',
                html: '<div class="hub-marker-inner">🧠</div>',
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
};
