import asyncio
from services.langgraph_orchestrator import resume_graph
from services.booking_executor import execute_booking
from store.db import PRICE_REPOSITORY, TRIPS
from services.contract_service import call_app
from dotenv import load_dotenv
from datetime import datetime, timezone
load_dotenv()


async def run_trip(trip_id):
    PRICE_REPOSITORY.clear_trip(trip_id)

    try:
        while True:
            trip = TRIPS[trip_id]
            graph_state = resume_graph(trip.get("graph_state", {}))
            trip["graph_state"] = graph_state
            trip["constraints"] = graph_state["constraints"]

            if graph_state.get("needs_clarification"):
                trip["status"] = "NEEDS_CLARIFICATION"
                break

            if graph_state.get("requires_human_approval"):
                trip["status"] = "AWAITING_HUMAN_APPROVAL"
                break

            components = graph_state.get("components", [])
            decision = graph_state.get("decision") or {"decision": "WAIT"}
            ml_prediction = graph_state.get("ml_prediction")
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
