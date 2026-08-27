import asyncio
import os

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from services.contract_service import deploy_contract
from services.langgraph_orchestrator import resume_graph, start_graph
from services.scheduler import run_trip
from store.db import PRICE_REPOSITORY, TRIPS


load_dotenv()

router = APIRouter()


def _contract_for(user_address):
    contract = deploy_contract(user_address)
    return {
        "app_id": contract["app_id"],
        "user_address": user_address,
    }


@router.post("/create_trip")
async def create_trip(data: dict):
    try:
        if "user_id" not in data or "query" not in data:
            raise HTTPException(status_code=400, detail="Missing user_id or query")

        user_id = data["user_id"]
        query = data["query"]
        user_address = os.getenv("USER_ADDRESS") or data.get("user_address")
        graph_state = start_graph(user_id, query)
        constraints = graph_state["constraints"]

        if graph_state.get("needs_clarification"):
            TRIPS[constraints["trip_id"]] = {
                "constraints": constraints,
                "status": "NEEDS_CLARIFICATION",
                "graph_state": graph_state,
            }
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
        asyncio.create_task(run_trip(trip_id))

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
