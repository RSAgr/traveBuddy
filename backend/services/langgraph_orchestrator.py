from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
import json
import os
import re
import uuid

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from services.decision_engine import evaluate
from services.ml_service import price_ml_service
from services.price_snapshots import snapshot_for
from services.search_tools import (
    search_buses,
    search_flights,
    search_hotels,
    search_local_recommendations,
    search_trains,
)
from store.db import PRICE_REPOSITORY


load_dotenv()
LLM_DISABLED_FOR_SESSION = False


class TravelGraphState(TypedDict, total=False):
    trip_id: str
    user_id: str
    messages: list[dict[str, str]]
    constraints: dict[str, Any]
    status: str
    needs_clarification: bool
    clarification_question: str | None
    proposed_updates: dict[str, Any]
    components: list[dict[str, Any]]
    price_history: list[dict[str, Any]]
    ml_prediction: float | None
    decision: dict[str, Any] | None
    requires_human_approval: bool
    human_approval_request: dict[str, Any] | None
    approved: bool | None
    error: str | None
    resume_existing: bool
    clarification_answered: bool
    optional_clarification_asked: bool


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("LLM response did not include JSON")
    return json.loads(match.group(0))


def _llm_json(prompt, fallback):
    global LLM_DISABLED_FOR_SESSION
    if os.getenv("MOCK_TRAVEL_DATA_ENABLED", "true").lower() == "true":
        return fallback

    if LLM_DISABLED_FOR_SESSION:
        return fallback

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return _extract_json(response.text.strip())
    except Exception as exc:
        print(f"Graph LLM call failed, using fallback: {exc}")
        if "429" in str(exc) or "quota" in str(exc).lower():
            LLM_DISABLED_FOR_SESSION = True
        return fallback


def _days_to_deadline(constraints):
    deadline = constraints.get("deadline")
    if not deadline:
        return None

    try:
        deadline_timestamp = int(deadline)
    except (TypeError, ValueError):
        return None

    if deadline_timestamp <= 10_000_000:
        return deadline_timestamp

    deadline_at = datetime.fromtimestamp(deadline_timestamp, timezone.utc)
    return max(0, round((deadline_at - datetime.now(timezone.utc)).total_seconds() / 86400, 2))


def _normalise_constraints(parsed, state):
    constraints = {
        **state.get("constraints", {}),
        **parsed,
        "trip_id": state["trip_id"],
        "user_id": state["user_id"],
    }
    constraints.setdefault("source", "Ranchi")
    constraints.setdefault("destination", "Puri")
    constraints.setdefault("transport_modes", ["flight", "train", "bus"])
    constraints.setdefault("budget", 10000)
    if constraints.get("booking_timing") == "postpone" and not constraints.get("auto_booking"):
        constraints["auto_booking"] = {
            "enabled": True,
            "strategy": "latest_safe",
            "price_rise_threshold_percent": 12,
            "minimum_confidence": 0.6,
            "booking_deadline": constraints.get("deadline"),
            "tracked_component_types": ["transport", "stay"],
        }
    policy = constraints.get("auto_booking")
    if policy:
        constraints["auto_booking"] = {
            "enabled": bool(policy.get("enabled", True)),
            "strategy": policy.get("strategy", "price_protection"),
            "price_rise_threshold_percent": float(policy.get("price_rise_threshold_percent", 10)),
            "minimum_confidence": float(policy.get("minimum_confidence", 0.5)),
            "max_wait_hours": policy.get("max_wait_hours"),
            "booking_deadline": policy.get("booking_deadline") or constraints.get("deadline"),
            "tracked_component_types": policy.get("tracked_component_types", ["transport", "stay"]),
            "started_at": policy.get("started_at") or datetime.now(timezone.utc).isoformat(),
        }
    return constraints


def _fallback_parse(query):
    lower_query = query.lower()
    modes = []
    for mode in ("flight", "train", "bus"):
        if mode in lower_query:
            modes.append(mode)

    budget_match = re.search(r"(?:under|budget|below|within|rs\.?|inr|₹)\s*(?:rs\.?|inr|₹)?\s*(\d{4,6})", lower_query)
    if not budget_match:
        budget_match = re.search(r"(\d{4,6})(?!-\d{2}-\d{2})", lower_query)
    budget = int(budget_match.group(1)) if budget_match else 10000

    date_match = re.findall(r"20\d{2}-\d{2}-\d{2}", query)
    if date_match:
        deadline = int(datetime.fromisoformat(date_match[-1]).replace(tzinfo=timezone.utc).timestamp())
    else:
        deadline = 7

    parsed = {
        "source": "Ranchi",
        "destination": "Puri" if "puri" in lower_query else "Puri",
        "budget": budget,
        "deadline": deadline,
        "transport_modes": modes or ["flight", "train", "bus"],
    }
    if (
        "postpone booking" in lower_query
        or "postpone as long" in lower_query
        or "latest_safe" in lower_query
        or "as long as safely possible" in lower_query
    ):
        parsed["booking_timing"] = "postpone"
        parsed["auto_booking"] = {
            "enabled": True,
            "strategy": "latest_safe",
            "price_rise_threshold_percent": 12,
            "minimum_confidence": 0.6,
            "booking_deadline": deadline,
            "tracked_component_types": ["transport", "stay"],
        }
    elif "book early" in lower_query:
        parsed["booking_timing"] = "early"
    else:
        parsed["booking_timing"] = "balanced"
    return parsed


def parse_or_update_constraints(state: TravelGraphState):
    if state.get("resume_existing") and state.get("constraints"):
        return {
            "constraints": state["constraints"],
            "status": "CONSTRAINTS_PARSED",
            "needs_clarification": False,
            "clarification_question": None,
        }

    latest_user_message = next(
        (message["content"] for message in reversed(state.get("messages", [])) if message["role"] == "user"),
        "",
    )
    if not latest_user_message and state.get("constraints"):
        return {
            "constraints": state["constraints"],
            "status": "CONSTRAINTS_PARSED",
            "needs_clarification": False,
            "clarification_question": None,
        }

    try:
        from services.ai_parser import parse_query_llm

        parsed = parse_query_llm(latest_user_message)
    except Exception as exc:
        print(f"Graph parser LLM failed, using fallback parser: {exc}")
        parsed = _fallback_parse(latest_user_message)
    constraints = _normalise_constraints(parsed, state)
    return {
        "constraints": constraints,
        "status": "CONSTRAINTS_PARSED",
        "needs_clarification": False,
        "clarification_question": None,
    }


def clarify_constraints(state: TravelGraphState):
    constraints = state["constraints"]
    if state.get("clarification_answered"):
        return {
            "status": "READY_TO_SEARCH",
            "needs_clarification": False,
            "clarification_question": None,
        }

    if state.get("optional_clarification_asked"):
        return {
            "status": "READY_TO_SEARCH",
            "needs_clarification": False,
            "clarification_question": None,
        }

    missing = []
    if not constraints.get("budget"):
        missing.append("budget")
    if not constraints.get("deadline"):
        missing.append("travel date")
    if not constraints.get("transport_modes"):
        missing.append("preferred transport")

    if missing:
        return {
            "status": "NEEDS_CLARIFICATION",
            "needs_clarification": True,
            "clarification_question": f"Please share your {', '.join(missing)} for the Ranchi to Puri trip.",
        }

    if os.getenv("MOCK_TRAVEL_DATA_ENABLED", "true").lower() == "true":
        return {
            "status": "READY_TO_SEARCH",
            "needs_clarification": False,
            "clarification_question": None,
        }

    prompt = f"""
You are a travel planning assistant. Decide whether to ask a concise clarification before searching.
Ask only if flexibility/preferences could materially improve price or comfort.
Return JSON:
{{
  "needs_clarification": true | false,
  "question": "question or empty string"
}}

Constraints: {json.dumps(constraints, default=str)}
Conversation: {json.dumps(state.get("messages", [])[-4:], default=str)}
"""
    result = _llm_json(prompt, {"needs_clarification": False, "question": ""})
    if result.get("needs_clarification"):
        return {
            "status": "NEEDS_CLARIFICATION",
            "needs_clarification": True,
            "clarification_question": result.get("question") or "Are your dates or transport preferences flexible?",
            "optional_clarification_asked": True,
        }

    return {
        "status": "READY_TO_SEARCH",
        "needs_clarification": False,
        "clarification_question": None,
    }


def route_after_clarification(state: TravelGraphState) -> Literal["await_user", "search"]:
    return "await_user" if state.get("needs_clarification") else "search"


def await_user(state: TravelGraphState):
    return {"status": "NEEDS_CLARIFICATION"}


def call_search_tools(state: TravelGraphState):
    constraints = state["constraints"]
    poll_cycle = len(PRICE_REPOSITORY.get_history(state["trip_id"]))
    components = []
    modes = constraints.get("transport_modes", [])

    if "flight" in modes:
        components.extend(search_flights(constraints, poll_cycle))
    if "train" in modes:
        components.extend(search_trains(constraints, poll_cycle))
    if "bus" in modes:
        components.extend(search_buses(constraints, poll_cycle))

    components.extend(search_hotels(constraints, poll_cycle))
    components.extend(search_local_recommendations(constraints, poll_cycle))
    return {"components": components, "status": "SEARCH_COMPLETE"}


def detect_better_flexible_option(state: TravelGraphState):
    constraints = state["constraints"]
    if constraints.get("date_shift_confirmed"):
        return {
            "needs_clarification": False,
            "clarification_question": None,
            "proposed_updates": {},
        }

    current_components = state.get("components", [])
    if not current_components:
        return {}

    previous_day_constraints = {
        **constraints,
        "deadline": max(0, int(constraints.get("deadline", 1)) - 86400)
        if int(constraints.get("deadline", 1)) > 10_000_000
        else max(0, int(constraints.get("deadline", 1)) - 1),
    }
    previous_components = []
    for mode in constraints.get("transport_modes", []):
        if mode == "flight":
            previous_components.extend(search_flights(previous_day_constraints, 0))
        elif mode == "train":
            previous_components.extend(search_trains(previous_day_constraints, 0))
        elif mode == "bus":
            previous_components.extend(search_buses(previous_day_constraints, 0))
    previous_components.extend(search_hotels(previous_day_constraints, 0))

    current_bookable = [c for c in current_components if c["type"] in {"transport", "stay"}]
    previous_bookable = [c for c in previous_components if c["type"] in {"transport", "stay"}]
    current_min = min((c["price"] for c in current_bookable), default=0)
    previous_min = min((c["price"] for c in previous_bookable), default=0)

    if current_min and previous_min and previous_min <= current_min * 0.8:
        return {
            "status": "NEEDS_CLARIFICATION",
            "needs_clarification": True,
            "clarification_question": (
                f"I found options about {round((current_min - previous_min) / current_min * 100)}% "
                "cheaper one day earlier. Can you shift the plan by one day?"
            ),
            "proposed_updates": {"deadline": previous_day_constraints["deadline"], "date_shift_confirmed": True},
            "optional_clarification_asked": True,
        }

    return {"needs_clarification": False, "clarification_question": None, "proposed_updates": {}}


def route_after_flex_check(state: TravelGraphState) -> Literal["await_user", "snapshot"]:
    return "await_user" if state.get("needs_clarification") else "snapshot"


def store_snapshot_and_predict(state: TravelGraphState):
    snapshot = snapshot_for(state["trip_id"], state["constraints"], state["components"])
    PRICE_REPOSITORY.save_snapshot(snapshot)
    price_history = PRICE_REPOSITORY.get_history(state["trip_id"])
    ml_prediction = price_ml_service.predict_next_price(price_history)
    return {
        "price_history": price_history,
        "ml_prediction": ml_prediction,
        "status": "PRICE_SNAPSHOT_STORED",
    }


def decide_and_validate(state: TravelGraphState):
    if state.get("approved") and state.get("human_approval_request"):
        approved_decision = {
            **state["human_approval_request"],
            "decision": "BOOK",
            "reason": f"Human approved booking. {state['human_approval_request'].get('reason', '')}".strip(),
            "requires_human_approval": False,
        }
        return {
            "decision": approved_decision,
            "requires_human_approval": False,
            "human_approval_request": None,
            "status": "DECISION_READY",
        }

    decision = evaluate(
        state["constraints"],
        state["components"],
        state["price_history"],
        ml_prediction=state.get("ml_prediction"),
    )
    return {
        "decision": decision,
        "requires_human_approval": decision.get("requires_human_approval", False),
        "human_approval_request": decision if decision.get("requires_human_approval") else None,
        "status": "DECISION_READY",
    }


def route_after_decision(state: TravelGraphState) -> Literal["human_approval", "done"]:
    if state.get("requires_human_approval"):
        return "human_approval"
    return "done"


def request_human_approval(state: TravelGraphState):
    return {"status": "AWAITING_HUMAN_APPROVAL"}


def finish_graph(state: TravelGraphState):
    return {"status": "READY_TO_BOOK" if state.get("decision", {}).get("decision") == "BOOK" else "WAITING"}


def build_travel_graph():
    graph = StateGraph(TravelGraphState)
    graph.add_node("parse_or_update_constraints", parse_or_update_constraints)
    graph.add_node("clarify_constraints", clarify_constraints)
    graph.add_node("await_user", await_user)
    graph.add_node("call_search_tools", call_search_tools)
    graph.add_node("detect_better_flexible_option", detect_better_flexible_option)
    graph.add_node("store_snapshot_and_predict", store_snapshot_and_predict)
    graph.add_node("decide_and_validate", decide_and_validate)
    graph.add_node("request_human_approval", request_human_approval)
    graph.add_node("finish_graph", finish_graph)

    graph.add_edge(START, "parse_or_update_constraints")
    graph.add_edge("parse_or_update_constraints", "clarify_constraints")
    graph.add_conditional_edges(
        "clarify_constraints",
        route_after_clarification,
        {"await_user": "await_user", "search": "call_search_tools"},
    )
    graph.add_edge("call_search_tools", "detect_better_flexible_option")
    graph.add_conditional_edges(
        "detect_better_flexible_option",
        route_after_flex_check,
        {"await_user": "await_user", "snapshot": "store_snapshot_and_predict"},
    )
    graph.add_edge("store_snapshot_and_predict", "decide_and_validate")
    graph.add_conditional_edges(
        "decide_and_validate",
        route_after_decision,
        {"human_approval": "request_human_approval", "done": "finish_graph"},
    )
    graph.add_edge("await_user", END)
    graph.add_edge("request_human_approval", END)
    graph.add_edge("finish_graph", END)
    return graph.compile()


travel_graph = build_travel_graph()


def start_graph(user_id, query, trip_id=None, auto_booking=None):
    trip_id = trip_id or str(uuid.uuid4())
    state = {
        "trip_id": trip_id,
        "user_id": user_id,
        "messages": [{"role": "user", "content": query}],
        "status": "STARTED",
        "constraints": {"auto_booking": auto_booking} if auto_booking else {},
    }
    return travel_graph.invoke(state)


def resume_graph(state, user_message=None, approved=None):
    messages = list(state.get("messages", []))
    if user_message:
        messages.append({"role": "user", "content": user_message})

    constraints = dict(state.get("constraints", {}))
    if user_message:
        nights_match = re.search(r"(\d+)\s*nights?", user_message.lower())
        days_match = re.search(r"(\d+)\s*days?", user_message.lower())
        if nights_match:
            constraints["nights"] = int(nights_match.group(1))
        if days_match:
            constraints["trip_days"] = int(days_match.group(1))

    if user_message and state.get("proposed_updates") and any(
        word in user_message.lower() for word in ["yes", "ok", "sure", "shift", "flexible"]
    ):
        constraints.update(state["proposed_updates"])

    next_state = {
        **state,
        "messages": messages,
        "constraints": constraints,
        "approved": approved,
        "resume_existing": True,
        "clarification_answered": bool(user_message),
        "needs_clarification": False,
        "clarification_question": None,
    }
    return travel_graph.invoke(next_state)
