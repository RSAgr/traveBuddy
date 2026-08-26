import asyncio
from services.api_fetcher import fetch_prices
from services.decision_engine import evaluate
from services.ml_service import price_ml_service
from services.booking_executor import execute_booking
from store.db import PRICE_REPOSITORY, TRIPS
from services.contract_service import call_app
from dotenv import load_dotenv
from datetime import datetime, timezone
load_dotenv()


def _route_for(constraints):
    return constraints.get("destination") or constraints.get("route") or "default-route"


def _snapshot_for(trip_id, constraints, components):
    bookable_components = [
        component
        for component in components
        if component["type"] in {"transport", "stay"}
    ]
    total_cost = sum(c["price"] for c in bookable_components)
    transport_modes = [c["mode"] for c in components if c["type"] == "transport"]
    primary_component = next((c for c in components if c["type"] == "transport"), components[0])
    features = primary_component.get("features", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id,
        "route": _route_for(constraints),
        "destination": constraints.get("destination", _route_for(constraints)),
        "transport_type": "+".join(transport_modes) or primary_component["mode"],
        "current_price": total_cost,
        "days_to_departure": features.get("days_to_departure"),
        "features": features,
        "components": components,
    }


async def run_trip(trip_id):
    PRICE_REPOSITORY.clear_trip(trip_id)

    try:
        while True:
            trip = TRIPS[trip_id]
            constraints = trip["constraints"]
            poll_cycle = len(PRICE_REPOSITORY.get_history(trip_id))

            components = fetch_prices(constraints, poll_cycle=poll_cycle)

            snapshot = _snapshot_for(trip_id, constraints, components)
            PRICE_REPOSITORY.save_snapshot(snapshot)
            price_history = PRICE_REPOSITORY.get_history(trip_id)
            ml_prediction = price_ml_service.predict_next_price(price_history)

            decision = evaluate(
                constraints,
                components,
                price_history,
                ml_prediction=ml_prediction,
            )
            trip["last_decision"] = decision
            trip["last_ml_prediction"] = ml_prediction
            trip["last_checked_at"] = datetime.now(timezone.utc).isoformat()

            app_id = trip["contract"]["app_id"]
            user_address = trip["contract"]["user_address"]

            if decision["decision"] == "BOOK":
                call_app(app_id, user_address, [b"approve"])
                selected_components = decision.get("selected_components") or components
                execute_booking(trip_id, selected_components)
                trip["status"] = "BOOKED"
                trip["booking"] = {
                    "components": selected_components,
                    "cost": decision.get("cost"),
                    "decision": decision,
                    "ml_prediction": ml_prediction,
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                }
                break

            await asyncio.sleep(5)  # polling interval
    except Exception as exc:
        trip = TRIPS.get(trip_id)
        if trip is not None:
            trip["status"] = "FAILED"
            trip["error"] = str(exc)
            trip["failed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Trip monitor failed for {trip_id}: {exc}")
