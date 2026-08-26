from copy import deepcopy

from services.api_fetcher import build_price_features, fetch_synthetic_prices


PURI_TRAVEL_CATALOG = {
    "route": {
        "source": "Ranchi",
        "destination": "Puri",
        "distance_km": 565,
        "best_season": "October to February",
        "notes": "Popular pilgrimage and beach route with higher demand around weekends and Rath Yatra season.",
    },
    "flights": [
        {
            "name": "IndiGo Ranchi to Bhubaneswar Saver",
            "operator": "IndiGo",
            "route": "IXR -> BBI, cab transfer to Puri",
            "departure_time": "08:20",
            "arrival_time": "12:45",
            "duration": "4h 25m including transfer",
            "stops": 1,
            "base_price": 5200,
            "baggage": "15kg check-in, 7kg cabin",
            "refund_policy": "Partially refundable",
            "comfort_score": 8.1,
            "reliability_score": 8.6,
        },
        {
            "name": "Air India Express Ranchi to Bhubaneswar Flex",
            "operator": "Air India Express",
            "route": "IXR -> BBI, cab transfer to Puri",
            "departure_time": "15:10",
            "arrival_time": "20:05",
            "duration": "4h 55m including transfer",
            "stops": 1,
            "base_price": 6100,
            "baggage": "15kg check-in, 7kg cabin",
            "refund_policy": "Refundable with fee",
            "comfort_score": 8.4,
            "reliability_score": 8.2,
        },
    ],
    "trains": [
        {
            "name": "Tapaswini Express",
            "operator": "Indian Railways",
            "train_number": "18451",
            "route": "RNC -> PURI",
            "departure_time": "16:00",
            "arrival_time": "06:10",
            "duration": "14h 10m",
            "class": "3A",
            "base_price": 1450,
            "availability": "GNWL with frequent confirmation",
            "comfort_score": 7.4,
            "reliability_score": 8.0,
        },
        {
            "name": "Puri Garib Rath",
            "operator": "Indian Railways",
            "train_number": "12832",
            "route": "RNC -> PURI",
            "departure_time": "21:05",
            "arrival_time": "11:20",
            "duration": "14h 15m",
            "class": "3A Economy",
            "base_price": 980,
            "availability": "Limited seats on weekends",
            "comfort_score": 6.9,
            "reliability_score": 7.7,
        },
    ],
    "buses": [
        {
            "name": "Ranchi to Puri AC Sleeper",
            "operator": "Royal Cruiser",
            "route": "Ranchi -> Cuttack -> Puri",
            "departure_time": "18:30",
            "arrival_time": "08:30",
            "duration": "14h",
            "seat_type": "AC Sleeper",
            "base_price": 1250,
            "amenities": ["Charging point", "Blanket", "Water bottle"],
            "comfort_score": 6.8,
            "reliability_score": 7.1,
        },
        {
            "name": "Ranchi to Puri Volvo Semi-Sleeper",
            "operator": "Shyamoli Paribahan",
            "route": "Ranchi -> Bhubaneswar -> Puri",
            "departure_time": "20:00",
            "arrival_time": "10:15",
            "duration": "14h 15m",
            "seat_type": "AC Semi-Sleeper",
            "base_price": 1550,
            "amenities": ["Wi-Fi", "Charging point", "Reading light"],
            "comfort_score": 7.3,
            "reliability_score": 7.4,
        },
    ],
    "hotels": [
        {
            "name": "Hotel Golden Tree Puri",
            "area": "Sea Beach Road",
            "base_price": 3600,
            "rating": 4.2,
            "amenities": ["Sea view", "Breakfast", "Wi-Fi", "Restaurant"],
            "distance_to_beach_km": 0.2,
            "distance_to_temple_km": 2.8,
            "cancellation": "Free cancellation until 24h before check-in",
        },
        {
            "name": "Mayfair Heritage Puri",
            "area": "Chakra Tirtha Road",
            "base_price": 7600,
            "rating": 4.6,
            "amenities": ["Pool", "Spa", "Beach access", "Breakfast"],
            "distance_to_beach_km": 0.1,
            "distance_to_temple_km": 3.4,
            "cancellation": "Partially refundable",
        },
        {
            "name": "Naren Palace Puri",
            "area": "Baliapanda",
            "base_price": 2400,
            "rating": 3.9,
            "amenities": ["Wi-Fi", "Parking", "Family rooms"],
            "distance_to_beach_km": 0.7,
            "distance_to_temple_km": 2.1,
            "cancellation": "Non-refundable saver rate",
        },
    ],
    "restaurants": [
        {
            "name": "Wildgrass Restaurant",
            "cuisine": "Odia, Seafood, Indian",
            "area": "VIP Road",
            "price_for_two": 900,
            "rating": 4.3,
            "must_try": ["Chingudi malai", "Dalma", "Pakhala"],
        },
        {
            "name": "Chung Wah",
            "cuisine": "Chinese, Indian",
            "area": "Grand Road",
            "price_for_two": 650,
            "rating": 4.0,
            "must_try": ["Fried rice", "Chilli chicken"],
        },
        {
            "name": "Honey Bee Bakery and Pizzeria",
            "cuisine": "Bakery, Pizza, Cafe",
            "area": "CT Road",
            "price_for_two": 700,
            "rating": 4.1,
            "must_try": ["Wood-fired pizza", "Brownie"],
        },
    ],
    "activities": [
        {
            "name": "Jagannath Temple",
            "category": "Pilgrimage",
            "estimated_cost": 0,
            "duration": "2h",
            "best_time": "Early morning",
        },
        {
            "name": "Puri Beach",
            "category": "Beach",
            "estimated_cost": 0,
            "duration": "2h",
            "best_time": "Sunrise or evening",
        },
        {
            "name": "Konark Sun Temple day trip",
            "category": "Heritage",
            "estimated_cost": 1800,
            "duration": "6h",
            "best_time": "Morning",
        },
    ],
}


MODE_TO_CATALOG_KEY = {
    "flight": "flights",
    "train": "trains",
    "bus": "buses",
}


def _is_puri_route(constraints):
    destination = str(constraints.get("destination", "")).lower()
    source = str(constraints.get("origin") or constraints.get("source") or "ranchi").lower()
    return "puri" in destination and ("ranchi" in source or not source)


def _price_with_features(option, constraints, mode, poll_cycle):
    features = build_price_features(constraints, mode, poll_cycle=poll_cycle)
    price = int(round(option["base_price"] * features["demand_index"] * features["seasonality_index"]))
    return price, features


def _transport_component(option, constraints, mode, poll_cycle):
    price, features = _price_with_features(option, constraints, mode, poll_cycle)
    component = deepcopy(option)
    component.update({
        "type": "transport",
        "mode": mode,
        "price": price,
        "provider": "mock_puri_catalog",
        "features": features,
    })
    return component


def _hotel_component(option, constraints, poll_cycle):
    price, features = _price_with_features(option, constraints, "hotel", poll_cycle)
    component = deepcopy(option)
    component.update({
        "type": "stay",
        "mode": "hotel",
        "price": price,
        "provider": "mock_puri_catalog",
        "features": features,
    })
    return component


def _restaurant_component(option):
    component = deepcopy(option)
    component.update({
        "type": "restaurant",
        "mode": "restaurant",
        "price": option["price_for_two"],
        "provider": "mock_puri_catalog",
    })
    return component


def _activity_component(option):
    component = deepcopy(option)
    component.update({
        "type": "activity",
        "mode": "activity",
        "price": option["estimated_cost"],
        "provider": "mock_puri_catalog",
    })
    return component


def fetch_puri_mock_prices(constraints, poll_cycle=0):
    if not _is_puri_route(constraints):
        return fetch_synthetic_prices(constraints, poll_cycle=poll_cycle)

    components = []
    requested_modes = constraints.get("transport_modes", ["flight", "train", "bus"])

    for mode in requested_modes:
        catalog_key = MODE_TO_CATALOG_KEY.get(mode)
        if catalog_key:
            components.extend(
                _transport_component(option, constraints, mode, poll_cycle)
                for option in PURI_TRAVEL_CATALOG[catalog_key]
            )

    components.extend(
        _hotel_component(option, constraints, poll_cycle)
        for option in PURI_TRAVEL_CATALOG["hotels"]
    )
    components.extend(
        _restaurant_component(option)
        for option in PURI_TRAVEL_CATALOG["restaurants"]
    )
    components.extend(
        _activity_component(option)
        for option in PURI_TRAVEL_CATALOG["activities"]
    )
    return components
