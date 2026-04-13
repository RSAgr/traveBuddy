from fastapi import APIRouter, HTTPException
import asyncio

from services.ai_parser import parse_query_llm
from services.constraint_service import create_constraints
from services.scheduler import run_trip
from services.contract_service import deploy_contract
from store.db import TRIPS
import os
#user_address = os.getenv("USER_ADDRESS") # if geeting issue in passing user address from request, you can set it here for testing

router = APIRouter()
from dotenv import load_dotenv
load_dotenv()

@router.get("/status/{trip_id}")
async def get_trip_status(trip_id: str):
    if trip_id not in TRIPS:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TRIPS[trip_id]

@router.post("/create_trip")
async def create_trip(data: dict):
    try:
        # 🔹 Step 1: Validate input
        if "user_id" not in data or "query" not in data:
            raise HTTPException(status_code=400, detail="Missing user_id or query")

        user_id = data["user_id"]
        query = data["query"]
        #user_address = data["user_address"] 
        user_address = os.getenv("USER_ADDRESS")
        if not user_address:
            raise HTTPException(status_code=400, detail="Missing user_address (request or USER_ADDRESS env)")
        booking_receiver_address = data.get("booking_receiver_address") or os.getenv("BOOKING_RECEIVER_ADDRESS") or user_address
        print(f"User Address: {user_address}")
        #user_address = "DUmmt"

        # 🔹 Step 2: Parse using LLM
        parsed = parse_query_llm(query)

        # 🔹 Step 3: Create constraints
        constraints = create_constraints(user_id, parsed)

        # 🔹 Step 4: Lock funds (blockchain stub)
        # contract = lock_funds(user_id, constraints["budget"])

        contract = deploy_contract(
            user_address=user_address,
            budget=constraints["budget"],
            trip_id=constraints["trip_id"],
            receiver_address=booking_receiver_address,
            deadline=constraints["deadline"],
        )
        #contract = {"app_id": 12345}

        # 🔹 Step 5: Store state
        TRIPS[constraints["trip_id"]] = {
            "constraints": constraints,
            "status": "ACTIVE",
            "contract": {
                "app_id": contract["app_id"],
                "app_address": contract["app_address"],
                "create_tx_id": contract["create_tx_id"],
                "lock_tx_id": contract["lock_tx_id"],
                "lock_amount": contract["lock_amount"],
                "user_address": user_address,
                "receiver_address": contract["receiver_address"],
            }
        }

        # 🔹 Step 6: Start async monitoring
        asyncio.create_task(
            run_trip(constraints["trip_id"])
        )

        # 🔹 Step 7: Response
        return {
            "trip_id": constraints["trip_id"],
            "status": "STARTED",
            "parsed": parsed,  # useful for debugging
            "contract": {
                "app_id": contract["app_id"],
                "app_address": contract["app_address"],
                "create_tx_id": contract["create_tx_id"],
                "lock_tx_id": contract["lock_tx_id"],
                "lock_amount": contract["lock_amount"],
                "user_address": user_address,
                "receiver_address": contract["receiver_address"],
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error in create_trip:", e)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
