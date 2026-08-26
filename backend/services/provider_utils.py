import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


AIRPORT_CODES = {
    "ahmedabad": "AMD",
    "bengaluru": "BLR",
    "bangalore": "BLR",
    "chennai": "MAA",
    "delhi": "DEL",
    "goa": "GOI",
    "hyderabad": "HYD",
    "jaipur": "JAI",
    "kolkata": "CCU",
    "mumbai": "BOM",
    "pune": "PNQ",
}


STATION_CODES = {
    "ahmedabad": "ADI",
    "bengaluru": "SBC",
    "bangalore": "SBC",
    "chennai": "MAS",
    "delhi": "NDLS",
    "goa": "MAO",
    "hyderabad": "HYB",
    "jaipur": "JP",
    "kolkata": "HWH",
    "mumbai": "CSTM",
    "pune": "PUNE",
}


class ProviderError(Exception):
    pass


def request_json(method, url, headers=None, data=None, params=None, timeout=15):
    if params:
        url = f"{url}?{urlencode(params)}"

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise ProviderError(f"HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise ProviderError(f"Network error: {exc}") from exc


def code_for(value, mapping, default=None):
    if not value:
        return default

    normalized = str(value).strip().lower()
    if normalized in mapping:
        return mapping[normalized]

    raw = str(value).strip().upper()
    return raw if 2 <= len(raw) <= 5 else default


def departure_date(constraints):
    deadline = constraints.get("deadline")
    try:
        deadline_timestamp = int(deadline)
    except (TypeError, ValueError):
        return (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()

    if deadline_timestamp > 10_000_000:
        return datetime.fromtimestamp(deadline_timestamp, timezone.utc).date().isoformat()

    return (datetime.now(timezone.utc) + timedelta(days=deadline_timestamp)).date().isoformat()


def price_amount(value):
    return int(round(float(value)))
