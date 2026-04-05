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
        print(f"User Address: {user_address}")
        #user_address = "DUmmt"

        # 🔹 Step 2: Parse using LLM
        parsed = parse_query_llm(query)

        # 🔹 Step 3: Create constraints
        constraints = create_constraints(user_id, parsed)

        # 🔹 Step 4: Lock funds (blockchain stub)
        # contract = lock_funds(user_id, constraints["budget"])
        
        contract = deploy_contract(user_address) # this line is causing the internal server error
        #contract = {"app_id": 12345}

        # 🔹 Step 5: Store state
        TRIPS[constraints["trip_id"]] = {
            "constraints": constraints,
            "status": "ACTIVE",
            "contract": {
                "app_id": contract["app_id"],
                "user_address": user_address
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
                "user_address": user_address
            }
        }

    except Exception as e:
        print("❌ Error in create_trip:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")