import random

def fetch_prices(constraints):
    components = []

    if "flight" in constraints["transport_modes"]:
        components.append({
            "type": "transport",
            "mode": "flight",
            "price": random.randint(300, 600)
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