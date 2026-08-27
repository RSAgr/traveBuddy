from datetime import datetime, timezone


def route_for(constraints):
    return constraints.get("destination") or constraints.get("route") or "default-route"


def snapshot_for(trip_id, constraints, components):
    bookable_components = [
        component
        for component in components
        if component["type"] in {"transport", "stay"}
    ]
    total_cost = sum(component["price"] for component in bookable_components)
    transport_modes = [component["mode"] for component in components if component["type"] == "transport"]
    primary_component = next((component for component in components if component["type"] == "transport"), components[0])
    features = primary_component.get("features", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id,
        "route": route_for(constraints),
        "destination": constraints.get("destination", route_for(constraints)),
        "transport_type": "+".join(transport_modes) or primary_component["mode"],
        "current_price": total_cost,
        "days_to_departure": features.get("days_to_departure"),
        "features": features,
        "components": components,
    }
