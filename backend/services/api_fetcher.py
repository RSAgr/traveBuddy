import random

def fetch_prices(constraints):
    components = []

    # Force cab to always trigger for demonstration regardless of LLM logic
    components.append({
        "type": "transport",
        "mode": "cab",
        "price": random.randint(1500, 3500)
    })

    if "train" in constraints["transport_modes"]:
        components.append({
            "type": "transport",
            "mode": "train",
            "price": random.randint(100, 300)
        })

    components.append({
        "type": "stay",
        "mode": "hotel",
        "price": random.randint(200, 500)
    })

    return components