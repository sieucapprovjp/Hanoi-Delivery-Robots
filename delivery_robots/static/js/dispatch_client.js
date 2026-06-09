function buildDispatchRobotPayload(robot) {
    return {
        id: robot.id,
        name: robot.name,
        lat: robot.lat,
        lon: robot.lon,
        battery: robot.battery,
        status: robot.status,
        currentLoad: robot.currentLoad,
        capacity: robot.capacity,
        roadMemory: robot.roadMemory,
        routeAlgorithm: robot.routeAlgorithm
    };
}

function buildDispatchRequestPayload(robots, deliveries) {
    return {
        robots: robots.map(buildDispatchRobotPayload),
        deliveries,
        currentTime: Date.now()
    };
}

async function requestDispatchAssignments(robots, deliveries) {
    const data = await postJson(
        CONFIG.API.DISPATCH_ASSIGN,
        buildDispatchRequestPayload(robots, deliveries),
        'Assignment failed'
    );

    return {
        assignments: data.assignments || [],
        explanations: data.explanations || []
    };
}

function buildLatestDecision(assignment, delivery) {
    return {
        robotName: assignment.robotName,
        deliveryId: delivery.id,
        priorityScore: assignment.priorityScore,
        batteryRisk: assignment.batteryRisk,
        totalScore: assignment.totalScore,
        breakdown: assignment.breakdown,
        pickupName: delivery.pickup.name,
        destinationName: delivery.destination.name,
        explanation: assignment.explanation || null
    };
}
