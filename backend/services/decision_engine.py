import json
import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from services.itinerary_builder import build_booking_itinerary


load_dotenv()

BOOK = "BOOK"
WAIT = "WAIT"


def _best_bookable_combo(components):
    transport_options = [component for component in components if component["type"] == "transport"]
    stays = [component for component in components if component["type"] == "stay"]

    if not transport_options or not stays:
        return None, float("inf")

    stay = min(stays, key=lambda component: component["price"])
    best_transport = min(transport_options, key=lambda component: component["price"])
    return [best_transport, stay], best_transport["price"] + stay["price"]


def _days_until_deadline(constraints):
    deadline = constraints.get("deadline")
    if deadline is None:
        return None

    try:
        deadline_timestamp = int(deadline)
    except (TypeError, ValueError):
        return None

    if deadline_timestamp <= 10_000_000:
        return max(0, deadline_timestamp)

    deadline_at = datetime.fromtimestamp(deadline_timestamp, timezone.utc)
    seconds_remaining = (deadline_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, round(seconds_remaining / 86400, 2))


def _price_trend(price_history):
    if len(price_history) < 2:
        return {
            "direction": "unknown",
            "change": 0,
            "confidence": 0.2,
        }

    latest = price_history[-1]["current_price"]
    previous = price_history[-2]["current_price"]
    change = latest - previous
    direction = "rising" if change > 0 else "falling" if change < 0 else "flat"
    confidence = min(0.9, 0.45 + abs(change) / max(latest, 1))

    return {
        "direction": direction,
        "change": change,
        "confidence": round(confidence, 2),
    }


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM decision did not include JSON")
    return json.loads(match.group(0))


def _fallback_decision(best_cost, budget, ml_signal, days_until_deadline):
    if best_cost > budget:
        return {
            "decision": WAIT,
            "reason": "Best available option exceeds the user's budget.",
            "confidence": 1.0,
            "requires_human_approval": False,
        }

    predicted_price = ml_signal.get("predicted_next_price")
    current_price = ml_signal.get("current_price")
    near_deadline = days_until_deadline is not None and days_until_deadline <= 2
    predicted_rising = (
        predicted_price is not None
        and current_price is not None
        and predicted_price > current_price
        and ml_signal.get("confidence", 0) >= 0.45
    )
    well_under_budget = best_cost <= budget * 0.9
    should_book = near_deadline or predicted_rising or well_under_budget

    return {
        "decision": BOOK if should_book else WAIT,
        "reason": "Fallback decision based on budget fit, deadline, and ML price trend.",
        "confidence": 0.55,
        "requires_human_approval": False,
    }


def _llm_decision(constraints, components, price_history, ml_signal, best_cost, days_until_deadline):
    if os.getenv("MOCK_TRAVEL_DATA_ENABLED", "true").lower() == "true":
        return _fallback_decision(best_cost, constraints["budget"], ml_signal, days_until_deadline)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_decision(best_cost, constraints["budget"], ml_signal, days_until_deadline)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
You are TraveBuddy's decision engine. Return ONLY valid JSON matching:
{{
  "decision": "BOOK" | "WAIT",
  "reason": "short explanation",
  "confidence": 0.0,
  "requires_human_approval": true | false
}}

Strict rules:
- Never choose BOOK if total booking cost exceeds the user's budget.
- Never choose BOOK if it violates mandatory user preferences or allowed transport modes.
- Consider ML predictions probabilistically, not as certainty.
- Become more conservative near the deadline: if a valid option is within budget and time is almost gone, prefer BOOK over risky waiting.
- Set requires_human_approval to false for normal in-budget bookings. Use true only when constraints are ambiguous or there is unusual risk.
- You do not control payments, smart contracts, blockchain commits, or fund release. You only recommend BOOK or WAIT.

Context:
User constraints/preferences: {json.dumps(constraints, default=str)}
Current prices/components: {json.dumps(components, default=str)}
Best valid current cost: {best_cost}
Budget: {constraints["budget"]}
Days until deadline: {days_until_deadline}
Recent price history: {json.dumps(price_history[-6:], default=str)}
ML signal: {json.dumps(ml_signal, default=str)}
"""
    response = model.generate_content(prompt)
    decision = _extract_json(response.text.strip())

    return {
        "decision": decision.get("decision", WAIT),
        "reason": decision.get("reason", "LLM decision returned no reason."),
        "confidence": float(decision.get("confidence", 0.0)),
        "requires_human_approval": bool(decision.get("requires_human_approval", False)),
    }


def _with_itinerary(decision, constraints, components):
    selected_components = decision.get("selected_components")
    if selected_components:
        decision["itinerary"] = build_booking_itinerary(
            constraints,
            selected_components,
            components,
        )
    return decision


def _validate_decision(llm_decision, constraints, components, best_combo, best_cost):
    hard_failures = []
    allowed_modes = set(constraints.get("transport_modes", []))
    selected_modes = {
        component["mode"]
        for component in best_combo or []
        if component["type"] == "transport"
    }

    if best_combo is None:
        hard_failures.append("No complete transport and stay option is available.")

    if best_cost > constraints["budget"]:
        hard_failures.append("Best available option exceeds the user's budget.")

    if allowed_modes and not selected_modes.issubset(allowed_modes):
        hard_failures.append("Selected transport violates mandatory transport preferences.")

    if llm_decision.get("requires_human_approval"):
        return _with_itinerary({
            **llm_decision,
            "decision": WAIT,
            "reason": f"Human approval required before booking: {llm_decision['reason']}",
            "validated": True,
            "hard_constraint_failures": hard_failures,
            "selected_components": best_combo,
            "cost": best_cost,
        }, constraints, components)

    if llm_decision["decision"] == BOOK and hard_failures:
        return _with_itinerary({
            "decision": WAIT,
            "reason": "LLM recommended booking, but deterministic hard constraints failed: "
            + "; ".join(hard_failures),
            "confidence": 1.0,
            "requires_human_approval": False,
            "validated": True,
            "hard_constraint_failures": hard_failures,
            "selected_components": best_combo,
            "cost": best_cost,
        }, constraints, components)

    return _with_itinerary({
        **llm_decision,
        "validated": True,
        "hard_constraint_failures": hard_failures,
        "selected_components": best_combo,
        "cost": best_cost,
    }, constraints, components)


def evaluate(constraints, components, price_history, ml_prediction=None):
    best_combo, best_cost = _best_bookable_combo(components)
    trend = _price_trend(price_history)
    current_price = price_history[-1]["current_price"] if price_history else None
    days_until_deadline = _days_until_deadline(constraints)
    ml_signal = {
        "predicted_next_price": ml_prediction,
        "current_price": current_price,
        "trend": trend["direction"],
        "trend_change": trend["change"],
        "confidence": trend["confidence"],
    }

    try:
        decision = _llm_decision(
            constraints,
            components,
            price_history,
            ml_signal,
            best_cost,
            days_until_deadline,
        )
    except Exception as exc:
        decision = _fallback_decision(best_cost, constraints["budget"], ml_signal, days_until_deadline)
        decision["reason"] = f"{decision['reason']} LLM unavailable: {exc}"

    return _validate_decision(decision, constraints, components, best_combo, best_cost)
