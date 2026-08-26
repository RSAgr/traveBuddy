import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.api_fetcher import fetch_synthetic_prices
from services.ml_service import price_ml_service


DESTINATIONS = ["Goa", "Mumbai", "Delhi", "Bengaluru", "Jaipur", "Kolkata"]
TRANSPORT_SETS = [
    ["flight"],
    ["train"],
    ["bus"],
    ["flight", "train"],
    ["train", "bus"],
    ["flight", "train", "bus"],
]


def _snapshot_for(trip_id, constraints, components):
    total_cost = sum(component["price"] for component in components)
    transport_modes = [component["mode"] for component in components if component["type"] == "transport"]
    primary_component = next(
        (component for component in components if component["type"] == "transport"),
        components[0],
    )
    features = primary_component.get("features", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id,
        "route": constraints["destination"],
        "destination": constraints["destination"],
        "transport_type": "+".join(transport_modes) or primary_component["mode"],
        "current_price": total_cost,
        "days_to_departure": features.get("days_to_departure"),
        "features": features,
        "components": components,
    }


def build_synthetic_history(samples=500):
    history = []
    base_time = datetime.now(timezone.utc)

    for index in range(samples):
        destination = DESTINATIONS[index % len(DESTINATIONS)]
        transport_modes = TRANSPORT_SETS[index % len(TRANSPORT_SETS)]
        days_from_now = 3 + index % 60
        deadline = int((base_time + timedelta(days=days_from_now)).timestamp())
        trip_id = f"synthetic-trip-{index:05d}"
        constraints = {
            "trip_id": trip_id,
            "user_id": "synthetic-user",
            "destination": destination,
            "budget": 2500 + (index % 12) * 750,
            "deadline": deadline,
            "transport_modes": transport_modes,
        }

        for poll_cycle in range(8):
            components = fetch_synthetic_prices(constraints, poll_cycle=poll_cycle)
            history.append(_snapshot_for(trip_id, constraints, components))

    return history


def write_training_csv(history, output_path):
    rows = price_ml_service.prepare_training_rows(history)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate ML-ready synthetic TraveBuddy price data.")
    parser.add_argument("--samples", type=int, default=500, help="Number of synthetic trips to simulate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/synthetic_price_history.csv"),
        help="CSV output path relative to backend/.",
    )
    args = parser.parse_args()

    history = build_synthetic_history(samples=args.samples)
    rows = write_training_csv(history, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
