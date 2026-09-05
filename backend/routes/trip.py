import asyncio
import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from services.contract_service import deploy_contract
from services.langgraph_orchestrator import resume_graph, start_graph
from services.scheduler import run_trip
from store.db import (
    BLOCKCHAIN_REPOSITORY,
    DECISION_REPOSITORY,
    PRICE_OVERRIDE_REPOSITORY,
    PRICE_REPOSITORY,
    TRIPS,
    TRIP_REPOSITORY,
)


load_dotenv()

router = APIRouter()


def _contract_for(user_address):
    if os.getenv("MOCK_TRAVEL_DATA_ENABLED", "true").lower() == "true":
        return {
            "app_id": "mock-app",
            "user_address": user_address or "mock-user",
            "tx_id": "mock-create-tx",
        }

    contract = deploy_contract(user_address)
    return {
        "app_id": contract["app_id"],
        "user_address": user_address,
        "tx_id": contract.get("tx_id"),
    }


@router.post("/create_trip")
async def create_trip(data: dict):
    try:
        if "user_id" not in data or "query" not in data:
            raise HTTPException(status_code=400, detail="Missing user_id or query")

        user_id = data["user_id"]
        query = data["query"]
        user_address = os.getenv("USER_ADDRESS") or data.get("user_address")
        auto_booking = data.get("auto_booking")
        # Accept the flat threshold form as a convenient backward-compatible API option.
        if auto_booking is None and any(key in data for key in ("price_rise_threshold_percent", "max_wait_hours", "booking_deadline")):
            auto_booking = {key: data[key] for key in ("price_rise_threshold_percent", "max_wait_hours", "booking_deadline", "minimum_confidence", "tracked_component_types") if key in data}
            auto_booking["enabled"] = True
        graph_state = start_graph(user_id, query, auto_booking=auto_booking)
        constraints = graph_state["constraints"]

        if graph_state.get("needs_clarification"):
            TRIPS[constraints["trip_id"]] = {
                "constraints": constraints,
                "status": "NEEDS_CLARIFICATION",
                "graph_state": graph_state,
            }
            TRIP_REPOSITORY.save(constraints["trip_id"], constraints, "NEEDS_CLARIFICATION")
            return {
                "trip_id": constraints["trip_id"],
                "status": "NEEDS_CLARIFICATION",
                "clarification_question": graph_state.get("clarification_question"),
                "parsed": constraints,
            }

        TRIPS[constraints["trip_id"]] = {
            "constraints": constraints,
            "status": "ACTIVE",
            "graph_state": graph_state,
            "contract": _contract_for(user_address),
        }
        TRIP_REPOSITORY.save(constraints["trip_id"], constraints, "ACTIVE")
        if graph_state.get("decision"):
            DECISION_REPOSITORY.save(constraints["trip_id"], graph_state["decision"], graph_state.get("ml_prediction"))
        contract = TRIPS[constraints["trip_id"]]["contract"]
        BLOCKCHAIN_REPOSITORY.save(constraints["trip_id"], contract.get("app_id"), contract.get("tx_id"), "MOCK" if contract.get("app_id") == "mock-app" else "DEPLOYED", {"user_address": contract.get("user_address")})
        asyncio.create_task(run_trip(constraints["trip_id"]))

        return {
            "trip_id": constraints["trip_id"],
            "status": "STARTED",
            "parsed": constraints,
            "contract": TRIPS[constraints["trip_id"]]["contract"],
        }

    except Exception as exc:
        print("Error in create_trip:", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/trip/{trip_id}/message")
async def update_trip_from_user(trip_id: str, data: dict):
    trip = TRIPS.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    graph_state = resume_graph(
        trip.get("graph_state", {}),
        user_message=data.get("message", ""),
        approved=data.get("approved"),
    )
    if data.get("auto_booking"):
        graph_state["constraints"]["auto_booking"] = {
            **graph_state["constraints"].get("auto_booking", {}),
            **data["auto_booking"],
        }
    trip["graph_state"] = graph_state
    trip["constraints"] = graph_state["constraints"]

    if graph_state.get("needs_clarification"):
        trip["status"] = "NEEDS_CLARIFICATION"
    elif graph_state.get("requires_human_approval"):
        trip["status"] = "AWAITING_HUMAN_APPROVAL"
    else:
        trip["status"] = "ACTIVE"
        if not trip.get("contract"):
            user_address = os.getenv("USER_ADDRESS") or data.get("user_address")
            trip["contract"] = _contract_for(user_address)
            contract = trip["contract"]
            BLOCKCHAIN_REPOSITORY.save(trip_id, contract.get("app_id"), contract.get("tx_id"), "MOCK" if contract.get("app_id") == "mock-app" else "DEPLOYED", {"user_address": contract.get("user_address")})
        asyncio.create_task(run_trip(trip_id))

    TRIP_REPOSITORY.save(trip_id, trip["constraints"], trip["status"])
    if graph_state.get("decision"):
        DECISION_REPOSITORY.save(trip_id, graph_state["decision"], graph_state.get("ml_prediction"))

    return {
        "trip_id": trip_id,
        "status": trip["status"],
        "constraints": trip["constraints"],
        "clarification_question": graph_state.get("clarification_question"),
        "human_approval_request": graph_state.get("human_approval_request"),
    }


@router.get("/status/{trip_id}")
async def get_trip_status(trip_id: str):
    trip = TRIPS.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    history = PRICE_REPOSITORY.get_history(trip_id)
    latest_snapshot = history[-1] if history else {}
    graph_state = trip.get("graph_state", {})

    return {
        "trip_id": trip_id,
        "status": trip["status"],
        "constraints": trip["constraints"],
        "contract": trip.get("contract"),
        "components": latest_snapshot.get("components", graph_state.get("components", [])),
        "price_history": history,
        "last_decision": trip.get("last_decision") or graph_state.get("decision"),
        "last_ml_prediction": trip.get("last_ml_prediction") or graph_state.get("ml_prediction"),
        "last_checked_at": trip.get("last_checked_at"),
        "booking": trip.get("booking"),
        "error": trip.get("error"),
        "clarification_question": graph_state.get("clarification_question"),
        "human_approval_request": graph_state.get("human_approval_request"),
    }


@router.get("/demo/price-overrides")
async def list_price_overrides(active_only: bool = False):
    return {"overrides": PRICE_OVERRIDE_REPOSITORY.list_overrides(active_only=active_only)}


@router.post("/demo/price-overrides")
async def set_price_override(data: dict):
    try:
        override = PRICE_OVERRIDE_REPOSITORY.upsert(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"override": override}


@router.post("/demo/price-overrides/clear")
async def clear_price_overrides(data: dict | None = None):
    route = (data or {}).get("route")
    updated = PRICE_OVERRIDE_REPOSITORY.clear(route=route)
    return {"disabled_overrides": updated}


@router.post("/demo/trips/{trip_id}/surge-selected")
async def surge_selected_trip_components(trip_id: str, data: dict | None = None):
    trip = TRIPS.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    decision = trip.get("last_decision") or trip.get("graph_state", {}).get("decision") or {}
    selected_components = decision.get("selected_components") or []
    if not selected_components:
        raise HTTPException(status_code=400, detail="No selected components are available yet. Wait for one polling cycle.")

    multiplier = float((data or {}).get("price_multiplier", 1.25))
    route = (data or {}).get("route") or trip.get("constraints", {}).get("destination") or "Puri"
    reason = (data or {}).get("reason") or "Demo selected-combo surge"

    overrides = []
    for component in selected_components:
        if component.get("type") not in {"transport", "stay"}:
            continue
        overrides.append(PRICE_OVERRIDE_REPOSITORY.upsert({
            "route": route,
            "component_name": component["name"],
            "component_type": component.get("type"),
            "mode": component.get("mode"),
            "price_multiplier": multiplier,
            "active": True,
            "reason": reason,
        }))

    return {"overrides": overrides}
