import os

from dotenv import load_dotenv

from services.api_fetcher import build_price_features
from services.provider_utils import ProviderError, departure_date, price_amount, request_json


load_dotenv()


def _first_price(value):
    if isinstance(value, dict):
        for key in ("price", "priceBreakdown", "grossPrice", "amount", "total"):
            result = _first_price(value.get(key))
            if result is not None:
                return result
    if isinstance(value, list):
        for item in value:
            result = _first_price(item)
            if result is not None:
                return result
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("INR", "").replace("₹", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _first_name(value):
    if isinstance(value, dict):
        for key in ("name", "hotel_name", "hotelName", "title"):
            if value.get(key):
                return value[key]
        for child in value.values():
            result = _first_name(child)
            if result:
                return result
    if isinstance(value, list):
        for item in value:
            result = _first_name(item)
            if result:
                return result
    return None


def fetch_rapidapi_hotel(constraints, poll_cycle=0):
    api_key = os.getenv("RAPIDAPI_KEY")
    host = os.getenv("RAPIDAPI_HOTEL_HOST", "hotels-com-provider.p.rapidapi.com")
    endpoint = os.getenv("RAPIDAPI_HOTEL_SEARCH_PATH", "/v2/hotels/search")
    if not api_key:
        raise ProviderError("RAPIDAPI_KEY is not configured")

    check_in = departure_date(constraints)
    response = request_json(
        "GET",
        f"https://{host}{endpoint}",
        headers={
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": host,
        },
        params={
            "query": constraints.get("destination", "Goa"),
            "checkin_date": check_in,
            "checkout_date": check_in,
            "adults_number": "1",
            "locale": "en_IN",
            "currency": os.getenv("RAPIDAPI_HOTEL_CURRENCY", "INR"),
        },
        timeout=20,
    )

    price = _first_price(response)
    if price is None:
        raise ProviderError("RapidAPI hotel provider returned no parseable price")

    return {
        "type": "stay",
        "mode": "hotel",
        "price": price_amount(price),
        "provider": "rapidapi_hotels_com_provider",
        "hotel_name": _first_name(response),
        "features": build_price_features(constraints, "hotel", poll_cycle=poll_cycle),
    }
