import random

def fetch_prices(constraints):
    components = []

    if "flight" in constraints["transport_modes"]:
        components.append({
            "type": "transport",
            "mode": "flight",
            "price": random.randint(3000, 6000)
        })

    if "train" in constraints["transport_modes"]:
        components.append({
            "type": "transport",
            "mode": "train",
            "price": random.randint(1000, 3000)
        })

    components.append({
        "type": "stay",
        "mode": "hotel",
        "price": random.randint(2000, 5000)
    })

    return components