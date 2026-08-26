import os

from dotenv import load_dotenv

from services.api_fetcher import build_price_features
from services.provider_utils import AIRPORT_CODES, ProviderError, code_for, departure_date, price_amount, request_json


load_dotenv()

DUFFEL_BASE_URL = "https://api.duffel.com"


def fetch_duffel_flight(constraints, poll_cycle=0):
    token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not token:
        raise ProviderError("DUFFEL_ACCESS_TOKEN is not configured")

    origin = os.getenv("DUFFEL_ORIGIN_AIRPORT_CODE") or code_for(
        constraints.get("origin") or constraints.get("source"),
        AIRPORT_CODES,
        default="BLR",
    )
    destination = code_for(constraints.get("destination"), AIRPORT_CODES)
    if not origin or not destination:
        raise ProviderError("Duffel flight search needs origin and destination airport codes")

    response = request_json(
        "POST",
        f"{DUFFEL_BASE_URL}/air/offer_requests",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Duffel-Version": os.getenv("DUFFEL_VERSION", "v2"),
        },
        params={"return_offers": "true"},
        data={
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date(constraints),
                    }
                ],
                "passengers": [{"type": "adult"}],
                "cabin_class": os.getenv("DUFFEL_CABIN_CLASS", "economy"),
            }
        },
        timeout=25,
    )
    offers = response.get("data", {}).get("offers", [])
    if not offers:
        raise ProviderError("Duffel returned no flight offers")

    offer = min(offers, key=lambda item: float(item["total_amount"]))
    return {
        "type": "transport",
        "mode": "flight",
        "price": price_amount(offer["total_amount"]),
        "provider": "duffel",
        "provider_offer_id": offer.get("id"),
        "currency": offer.get("total_currency"),
        "features": build_price_features(constraints, "flight", poll_cycle=poll_cycle),
    }
