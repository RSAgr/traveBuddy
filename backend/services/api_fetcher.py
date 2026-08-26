import hashlib
import math
import random
from datetime import datetime, timezone


BASE_PRICES = {
    "flight": 5200,
    "train": 1800,
    "bus": 1300,
    "hotel": 3200,
}


def _stable_uniform(seed_parts, low, high):
    seed = "|".join(str(part) for part in seed_parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    return rng.uniform(low, high)


def _days_to_departure(constraints, now):
    deadline = constraints.get("deadline", 30)
    try:
        deadline_timestamp = int(deadline)
    except (TypeError, ValueError):
        deadline = 30
        return max(0, deadline)

    if deadline_timestamp > 10_000_000:
        departure = datetime.fromtimestamp(deadline_timestamp, timezone.utc)
        return max(0, math.ceil((departure - now).total_seconds() / 86400))

    return max(0, deadline_timestamp)


def _route_key(constraints):
    return constraints.get("destination") or constraints.get("route") or "default-route"


def _demand_features(constraints, mode, now, poll_cycle=0):
    days_to_departure = _days_to_departure(constraints, now)
    day_of_week = now.weekday()
    month = now.month
    cycle_pressure = 1 + min(poll_cycle, 12) * 0.012
    seasonality_index = 1 + 0.10 * math.sin((month - 1) / 12 * 2 * math.pi)
    weekend_factor = 1.12 if day_of_week >= 5 else 1.0
    urgency_factor = 1 + max(0, 30 - days_to_departure) / 30 * 0.35
    route_demand = _stable_uniform([_route_key(constraints), mode, "route-demand"], 0.88, 1.18)
    demand_index = round(weekend_factor * urgency_factor * route_demand * cycle_pressure, 4)

    return {
        "days_to_departure": days_to_departure,
        "poll_cycle": poll_cycle,
        "day_of_week": day_of_week,
        "month": month,
        "is_weekend": day_of_week >= 5,
        "seasonality_index": round(seasonality_index, 4),
        "demand_index": demand_index,
    }


def _synthetic_price(constraints, mode, now, poll_cycle=0):
    features = _demand_features(constraints, mode, now, poll_cycle)
    base_price = BASE_PRICES[mode]
    mode_multiplier = 1.0 if mode != "hotel" else 0.92
    trend = 1 + 0.025 * math.sin((poll_cycle + len(mode)) / 2)
    noise = _stable_uniform(
        [
            constraints.get("trip_id"),
            _route_key(constraints),
            mode,
            features["days_to_departure"],
            poll_cycle,
        ],
        0.985,
        1.015,
    )
    price = (
        base_price
        * mode_multiplier
        * features["demand_index"]
        * features["seasonality_index"]
        * trend
        * noise
    )
    return int(round(price)), features


def _component(constraints, mode, component_type, now, poll_cycle=0):
    price, features = _synthetic_price(constraints, mode, now, poll_cycle)
    return {
        "type": component_type,
        "mode": mode,
        "price": price,
        "features": features,
    }


def fetch_prices(constraints, poll_cycle=0):
    now = datetime.now(timezone.utc)
    components = []

    if "flight" in constraints["transport_modes"]:
        components.append(_component(constraints, "flight", "transport", now, poll_cycle))

    if "train" in constraints["transport_modes"]:
        components.append(_component(constraints, "train", "transport", now, poll_cycle))

    if "bus" in constraints["transport_modes"]:
        components.append(_component(constraints, "bus", "transport", now, poll_cycle))

    components.append(_component(constraints, "hotel", "stay", now, poll_cycle))

    return components
