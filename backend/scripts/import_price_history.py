import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from store.db import PRICE_REPOSITORY


def main():
    parser = argparse.ArgumentParser(description="Import ML-ready historical prices into PostgreSQL.")
    parser.add_argument("csv_path")
    args = parser.parse_args()
    with open(args.csv_path, newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            numeric = ("poll_cycle", "demand_index", "seasonality_index", "day_of_week", "month")
            features = {key: float(row[key]) for key in numeric}
            features["is_weekend"] = row["is_weekend"].lower() == "true"
            PRICE_REPOSITORY.save_snapshot({
                "trip_id": row["trip_id"], "route": row["route"], "destination": row["route"],
                "transport_type": row["transport_type"], "current_price": float(row["current_price"]),
                "days_to_departure": float(row["days_to_departure"]),
                "timestamp": datetime.now(timezone.utc).isoformat(), "features": features, "components": [],
            })
    print("Historical price data imported.")


if __name__ == "__main__":
    main()
