from pathlib import Path


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "price_model.joblib"


class PriceMLService:
    feature_columns = [
        "route",
        "transport_type",
        "days_to_departure",
        "poll_cycle",
        "demand_index",
        "seasonality_index",
        "day_of_week",
        "month",
        "is_weekend",
    ]

    target_column = "current_price"

    def __init__(self, model_path=MODEL_PATH):
        self.model_path = Path(model_path)
        self.model = None
        self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            return

        try:
            import joblib

            self.model = joblib.load(self.model_path)
        except Exception as exc:
            print(f"Price model could not be loaded: {exc}")
            self.model = None

    def predict_next_price(self, history):
        if not history:
            return None

        if self.model is not None:
            rows = self.prepare_training_rows([history[-1]])
            next_row = dict(rows[0])
            next_row["poll_cycle"] = next_row["poll_cycle"] + 1
            features = [[next_row[column] for column in self.feature_columns]]
            return round(float(self.model.predict(features)[0]), 2)

        recent = history[-3:]
        observed_prices = [record["current_price"] for record in recent]
        return round(sum(observed_prices) / len(observed_prices), 2)

    def prepare_training_rows(self, history):
        rows = []
        for record in history:
            rows.append({
                "trip_id": record["trip_id"],
                "route": record["route"],
                "transport_type": record["transport_type"],
                "current_price": record["current_price"],
                "days_to_departure": record["days_to_departure"],
                "poll_cycle": record["features"]["poll_cycle"],
                "demand_index": record["features"]["demand_index"],
                "seasonality_index": record["features"]["seasonality_index"],
                "day_of_week": record["features"]["day_of_week"],
                "month": record["features"]["month"],
                "is_weekend": record["features"]["is_weekend"],
            })
        return rows


price_ml_service = PriceMLService()
