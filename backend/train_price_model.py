import argparse
import csv
from pathlib import Path

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from services.ml_service import MODEL_PATH, price_ml_service
from store.db import PRICE_REPOSITORY


def _load_rows(input_path):
    with input_path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def _coerce_rows(rows):
    numeric_columns = [
        "current_price",
        "days_to_departure",
        "poll_cycle",
        "demand_index",
        "seasonality_index",
        "day_of_week",
        "month",
    ]
    for row in rows:
        for column in numeric_columns:
            row[column] = float(row[column])
        row["is_weekend"] = row["is_weekend"] == "True"
    return rows


def train_offline(input_path=Path("data/synthetic_price_history.csv"), model_path=MODEL_PATH, database=False):
    if database:
        rows = price_ml_service.prepare_training_rows(PRICE_REPOSITORY.all_snapshots())
    else:
        rows = _coerce_rows(_load_rows(input_path))
    if not rows:
        print("No historical price snapshots available yet.")
        return None

    feature_columns = price_ml_service.feature_columns
    target_column = price_ml_service.target_column
    features = [[row[column] for column in feature_columns] for row in rows]
    targets = [row[target_column] for row in rows]

    categorical_features = [0, 1]
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ],
        remainder="passthrough",
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "regressor",
                HistGradientBoostingRegressor(
                    learning_rate=0.07,
                    max_iter=300,
                    l2_regularization=0.01,
                    random_state=42,
                ),
            ),
        ]
    )

    train_features, test_features, train_targets, test_targets = train_test_split(
        features,
        targets,
        test_size=0.2,
        random_state=42,
    )
    model.fit(train_features, train_targets)
    predictions = model.predict(test_features)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    model_summary = {
        "training_rows": len(rows),
        "model": "HistGradientBoostingRegressor",
        "mean_absolute_error": round(mean_absolute_error(test_targets, predictions), 2),
        "r2_score": round(r2_score(test_targets, predictions), 4),
        "model_path": str(model_path),
        "features": feature_columns,
    }
    print(model_summary)
    return model_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the TraveBuddy price prediction model.")
    parser.add_argument("--input", type=Path, default=Path("data/synthetic_price_history.csv"))
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--database", action="store_true", help="Train from durable PostgreSQL price history.")
    args = parser.parse_args()
    train_offline(input_path=args.input, model_path=args.model_path, database=args.database)
