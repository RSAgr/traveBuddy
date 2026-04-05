from dotenv import load_dotenv
load_dotenv()


def evaluate(constraints, components, price_history):
    budget = constraints["budget"]

    # Generate combinations
    transport_options = [c for c in components if c["type"] == "transport"]
    stay = [c for c in components if c["type"] == "stay"][0]

    best_cost = float("inf")
    best_combo = None

    for t in transport_options:
        total = t["price"] + stay["price"]

        if total < best_cost:
            best_cost = total
            best_combo = [t, stay]

    # Rule check
    if best_cost > budget:
        return {"decision": "WAIT"}

    # Heuristic: simple trend
    if len(price_history) >= 3:
        if price_history[-1] > price_history[-2]:
            return {"decision": "EXECUTE", "cost": best_cost}

    return {"decision": "WAIT"}