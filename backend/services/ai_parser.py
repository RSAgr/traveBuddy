# def parse_query(query: str):
#     # TODO: Replace with LLM
#     return {
#         "destination": "Goa",
#         "budget": 10000,
#         "deadline": 1716144000,
#         "transport_modes": ["cab", "train"]
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
  "transport_modes": list of ["cab", "train", "bus"]
}}

If any field is missing or unclear, do write a best guess or use defaults

Rules:
- If transport not specified → include all
- Convert relative time (like "next weekend") into days from now
- Budget must be integer
- No explanation, only JSON

User Query:
{query}
"""

# def llm_call(prompt: str):
#     # Replace with actual Gemini SDK
    

import json
import re
from datetime import datetime, timedelta
import google.generativeai as genai
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

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print("Gemini API Key loaded:", os.getenv("GEMINI_API_KEY"))


model = genai.GenerativeModel("gemini-2.5-flash")

def parse_query_llm(query: str):
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
        destination = data.get("destination", "Unknown")

        budget = int(data.get("budget", 1000))

        days = int(data.get("deadline_days_from_now", 7))
        deadline = datetime.now() + timedelta(days=days)

        transport_modes = data.get("transport_modes", ["cab", "train", "bus"])

        # Ensure it's a list
        if not isinstance(transport_modes, list):
            transport_modes = ["cab", "train", "bus"]

        return {
            "destination": destination,
            "budget": budget,
            "deadline": int(deadline.timestamp()),
            "transport_modes": transport_modes
        }

    except Exception as e:
        print("❌ LLM parsing failed:", e)
        print("Raw response:", raw_text)

        # Strong fallback
        return {
            "destination": "Nowhere",
            "budget": 1000,
            "deadline": int((datetime.now() + timedelta(days=7)).timestamp()),
            "transport_modes": ["cab", "train"]
        }