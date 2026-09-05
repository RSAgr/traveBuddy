from datetime import datetime, timezone


def route_for(constraints):
    return constraints.get("destination") or constraints.get("route") or "default-route"


def _monitored_components(components, tracked_types, tracked_names):
    if tracked_names:
        named_components = [
            component
            for component in components
            if component["type"] in tracked_types and component.get("name") in tracked_names
        ]
        if named_components:
            return named_components

    if {"transport", "stay"}.issubset(tracked_types):
        transport_options = [component for component in components if component["type"] == "transport"]
        stays = [component for component in components if component["type"] == "stay"]
        if transport_options and stays:
            return [
                min(transport_options, key=lambda component: component["price"]),
                min(stays, key=lambda component: component["price"]),
            ]

    return [component for component in components if component["type"] in tracked_types]


def snapshot_for(trip_id, constraints, components):
    policy = constraints.get("auto_booking") or {}
    tracked_types = set(policy.get("tracked_component_types", ["transport", "stay"]))
    tracked_names = set(policy.get("tracked_component_names", []))
    bookable_components = _monitored_components(components, tracked_types, tracked_names)
    # Keep legacy full-trip monitoring if an invalid/empty selection was supplied.
    if not bookable_components:
        bookable_components = [component for component in components if component["type"] in {"transport", "stay"}]
    total_cost = sum(component["price"] for component in bookable_components)
    transport_modes = [component["mode"] for component in components if component["type"] == "transport"]
    primary_component = next((component for component in components if component["type"] == "transport"), components[0])
    features = {
        **primary_component.get("features", {}),
        "tracked_component_types": sorted(tracked_types),
        "monitored_component_names": [component.get("name") for component in bookable_components],
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id,
        "source": constraints.get("source"),
        "route": route_for(constraints),
        "destination": constraints.get("destination", route_for(constraints)),
        "transport_type": "+".join(transport_modes) or primary_component["mode"],
        "current_price": total_cost,
        "days_to_departure": features.get("days_to_departure"),
        "features": features,
        "components": components,
    }
