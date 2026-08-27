from services.api_fetcher import fetch_prices


def search_flights(constraints, poll_cycle=0):
    flight_constraints = {
        **constraints,
        "transport_modes": ["flight"],
    }
    return [
        component
        for component in fetch_prices(flight_constraints, poll_cycle=poll_cycle)
        if component["mode"] == "flight"
    ]


def search_trains(constraints, poll_cycle=0):
    train_constraints = {
        **constraints,
        "transport_modes": ["train"],
    }
    return [
        component
        for component in fetch_prices(train_constraints, poll_cycle=poll_cycle)
        if component["mode"] == "train"
    ]


def search_buses(constraints, poll_cycle=0):
    bus_constraints = {
        **constraints,
        "transport_modes": ["bus"],
    }
    return [
        component
        for component in fetch_prices(bus_constraints, poll_cycle=poll_cycle)
        if component["mode"] == "bus"
    ]


def search_hotels(constraints, poll_cycle=0):
    return [
        component
        for component in fetch_prices(constraints, poll_cycle=poll_cycle)
        if component["type"] == "stay"
    ]


def search_local_recommendations(constraints, poll_cycle=0):
    return [
        component
        for component in fetch_prices(constraints, poll_cycle=poll_cycle)
        if component["type"] in {"restaurant", "activity"}
    ]
