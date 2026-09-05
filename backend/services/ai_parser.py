# def parse_query(query: str):
#     # TODO: Replace with LLM
#     return {
#         "destination": "Goa",
#         "budget": 10000,
#         "deadline": 1716144000,
#         "transport_modes": ["flight", "train"]
#     }

import json
from datetime import datetime, timedelta
    
def build_prompt(query: str):
    return f"""
You are a travel planning parser.

Extract structured information from the user query.

Return ONLY valid JSON in this format:
{{
  "destination": string,
  "budget": integer,
  "deadline_days_from_now": integer,
  "transport_modes": list of ["flight", "train", "bus"],
  "booking_timing": "balanced" | "early" | "postpone",
  "auto_booking": {{"enabled": boolean, "price_rise_threshold_percent": number, "max_wait_hours": number, "minimum_confidence": number}}
}}

Rules:
- If transport not specified → include all
- Convert relative time (like "next weekend") into days from now
- Budget must be integer
- No explanation, only JSON
- Set booking_timing to "postpone" when the user wants to wait/postpone booking as long as possible
- Include auto_booking when the user asks for price-rise protection, auto-booking, or postponing booking safely
- For postpone booking, set auto_booking enabled=true, price_rise_threshold_percent=12, minimum_confidence=0.6

User Query:
{query}
"""

# def llm_call(prompt: str):
#     # Replace with actual Gemini SDK
    

import json
import re
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv


def extract_json(text: str):
    """
    Extract JSON object from LLM response (handles markdown, extra text)
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("No JSON found in response")

load_dotenv()

def parse_query_llm(query: str):
    if os.getenv("MOCK_TRAVEL_DATA_ENABLED", "true").lower() == "true":
        raise ValueError("MOCK_TRAVEL_DATA_ENABLED is true")

    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is not configured")

    import google.generativeai as genai

    #genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    genai.configure(api_key=os.getenv("AIzaSyAdKiRABlAIQzpVQ17DKE8q31IHy3_kGmQ"))
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = build_prompt(query)

    response = model.generate_content(prompt)

    # Gemini can return multiple parts; safest extraction:
    raw_text = response.text.strip()

    try:
        # 🔹 Step 1: Extract pure JSON
        json_str = extract_json(raw_text)

        # 🔹 Step 2: Parse
        data = json.loads(json_str)

        # 🔹 Step 3: Validate + defaults
        destination = data.get("destination") or "Puri"

        budget = int(data.get("budget") or 10000)

        days = int(data.get("deadline_days_from_now") or 7)
        if days < 0 or days > 366:
            days = 7
        deadline = datetime.now() + timedelta(days=days)

        transport_modes = data.get("transport_modes") or ["flight", "train", "bus"]

        # Ensure it's a list
        if not isinstance(transport_modes, list):
            transport_modes = ["flight", "train", "bus"]

        parsed = {
            "destination": destination,
            "budget": budget,
            "deadline": int(deadline.timestamp()),
            "transport_modes": transport_modes,
            "booking_timing": data.get("booking_timing") or "balanced",
        }
        if data.get("auto_booking"):
            parsed["auto_booking"] = data["auto_booking"]
        return parsed

    except Exception as e:
        print("❌ LLM parsing failed:", e)
        print("Raw response:", raw_text)

        # 🔹 Strong fallback
        return {
            "destination": "Goa",
            "budget": 10000,
            "deadline": int((datetime.now() + timedelta(days=7)).timestamp()),
            "transport_modes": ["flight", "train"]
        }
