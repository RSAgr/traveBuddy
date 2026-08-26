import os

from dotenv import load_dotenv

from services.api_fetcher import build_price_features, fetch_synthetic_prices
from services.provider_utils import STATION_CODES, ProviderError, code_for, request_json


load_dotenv()

INDIAN_RAIL_BASE_URL = "http://indianrailapi.com/api/v2"


def fetch_indian_rail_train(constraints, poll_cycle=0):
    api_key = os.getenv("INDIAN_RAIL_API_KEY")
    if not api_key:
        raise ProviderError("INDIAN_RAIL_API_KEY is not configured")

    source = os.getenv("INDIAN_RAIL_SOURCE_STATION_CODE") or code_for(
        constraints.get("origin") or constraints.get("source"),
        STATION_CODES,
        default="SBC",
    )
    destination = code_for(constraints.get("destination"), STATION_CODES)
    if not source or not destination:
        raise ProviderError("Indian Rail search needs source and destination station codes")

    response = request_json(
        "GET",
        f"{INDIAN_RAIL_BASE_URL}/TrainBetweenStation/apikey/{api_key}/From/{source}/To/{destination}",
        timeout=15,
    )
    trains = response.get("Trains", [])
    if response.get("ResponseCode") != "200" or not trains:
        raise ProviderError(response.get("Message") or "Indian Rail returned no trains")

    train = trains[0]
    synthetic_train = next(
        component
        for component in fetch_synthetic_prices(constraints, poll_cycle)
        if component["mode"] == "train"
    )
    synthetic_train.update({
        "provider": "indian_rail_api",
        "train_number": train.get("TrainNo"),
        "train_name": train.get("TrainName"),
        "departure_time": train.get("DepartureTime"),
        "arrival_time": train.get("ArrivalTime"),
        "travel_time": train.get("TravelTime"),
        "train_type": train.get("TrainType"),
        "features": build_price_features(constraints, "train", poll_cycle=poll_cycle),
    })
    return synthetic_train
