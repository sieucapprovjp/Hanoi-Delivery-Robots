HanoiMap.prototype.setupChargingStations = async function () {
    let locations = CONFIG.DATA.CHARGING_STATIONS;
    try {
        const data = await getJson(CONFIG.API.CHARGING_STATIONS, null, 'Charging stations request failed');
        if (Array.isArray(data.stations) && data.stations.length > 0) {
            locations = data.stations;
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
                html: '<div class="charging-station-inner">⚡</div>',
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
                await putJson(`${CONFIG.API.CHARGING_STATIONS}/${station.id}`, { lat: nextLat, lon: nextLon }, `Failed to save charging station #${station.id}`);
            } catch (error) {
                console.error(error);
            }
        });

        this.chargingStations.push(station);
    });
};

HanoiMap.prototype.reloadChargingStations = async function () {
    this.chargingStations.forEach(station => {
        if (station.marker) {
            station.marker.remove();
        }
    });
    this.chargingStations = [];
    await this.setupChargingStations();
};
