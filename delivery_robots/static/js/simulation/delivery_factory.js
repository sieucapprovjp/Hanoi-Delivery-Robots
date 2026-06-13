function weightedPick(weights) {
    const entries = Object.entries(weights);
    const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
    let target = Math.random() * total;

    for (const [category, weight] of entries) {
        target -= weight;
        if (target <= 0) return category;
    }

    return entries[entries.length - 1][0];
}

function randomLocationForCategory(locations, category, excludeName = null) {
    const matches = locations.filter(location => location.category === category && location.name !== excludeName);
    const pool = matches.length > 0 ? matches : locations.filter(location => location.name !== excludeName);
    return pool[Math.floor(Math.random() * pool.length)];
}

function createDelivery(locations, id) {
    const pickupCategory = weightedPick(CONFIG.SIMULATION.PICKUP_WEIGHTS);
    const pickup = randomLocationForCategory(locations, pickupCategory);
    let dropoffCategory = weightedPick(CONFIG.SIMULATION.DROPOFF_WEIGHTS);
    let destination = randomLocationForCategory(locations, dropoffCategory, pickup.name);

    if (destination.name === pickup.name) {
        dropoffCategory = CONFIG.SIMULATION.CATEGORIES.RESIDENTIAL;
        destination = randomLocationForCategory(locations, dropoffCategory, pickup.name);
    }

    return {
        id,
        pickup,
        destination,
        status: CONFIG.SIMULATION.DELIVERY_STATUSES.PENDING,
        createdAt: Date.now(),
        theme: {
            pickupCategory,
            dropoffCategory,
            pickupIcon: pickup.icon,
            dropoffIcon: destination.icon
        },
    };
}

function buildDeliveryLogPayload(delivery) {
    return {
        deliveryId: delivery.id,
        pickupLat: delivery.pickup.lat,
        pickupLon: delivery.pickup.lon,
        pickupName: delivery.pickup.name,
        pickupCategory: delivery.pickup.category,
        dropoffLat: delivery.destination.lat,
        dropoffLon: delivery.destination.lon,
        dropoffName: delivery.destination.name,
        dropoffCategory: delivery.destination.category,
        createdAt: delivery.createdAt
    };
}
