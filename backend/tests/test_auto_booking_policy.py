import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.decision_engine import BOOK, WAIT, evaluate


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)
COMPONENTS = [
    {"type": "transport", "mode": "flight", "price": 40},
    {"type": "stay", "mode": "hotel", "price": 50},
]


def history(*prices):
    return [
        {"trip_id": "trip-1", "current_price": price, "timestamp": NOW.isoformat()}
        for price in prices
    ]


def constraints(**policy):
    return {
        "budget": 200,
        "transport_modes": ["flight"],
        "auto_booking": {
            "enabled": True,
            "price_rise_threshold_percent": 10,
            "minimum_confidence": 0.4,
            "started_at": NOW.isoformat(),
            **policy,
        },
    }


class AutoBookingPolicyTests(unittest.TestCase):
    def test_wait_below_price_rise_threshold(self):
        decision = evaluate(constraints(), COMPONENTS, history(100, 100), ml_prediction=109, now=NOW)
        self.assertEqual(decision["decision"], WAIT)
        self.assertIsNone(decision["policy_trigger"])

    def test_books_when_threshold_and_confidence_are_met(self):
        decision = evaluate(constraints(), COMPONENTS, history(100, 100), ml_prediction=110, now=NOW)
        self.assertEqual(decision["decision"], BOOK)
        self.assertEqual(decision["policy_trigger"], "predicted_price_rise")

    def test_waits_when_confidence_is_too_low(self):
        decision = evaluate(constraints(minimum_confidence=0.8), COMPONENTS, history(100, 100), ml_prediction=115, now=NOW)
        self.assertEqual(decision["decision"], WAIT)
        self.assertIn("confidence", decision["reason"])

    def test_books_when_max_wait_expires(self):
        decision = evaluate(constraints(max_wait_hours=1, started_at=(NOW - timedelta(hours=2)).isoformat()), COMPONENTS, history(100), ml_prediction=100, now=NOW)
        self.assertEqual(decision["decision"], BOOK)
        self.assertEqual(decision["policy_trigger"], "max_wait")

    def test_books_when_booking_deadline_is_reached(self):
        decision = evaluate(constraints(booking_deadline=(NOW - timedelta(minutes=1)).isoformat()), COMPONENTS, history(100), ml_prediction=100, now=NOW)
        self.assertEqual(decision["decision"], BOOK)
        self.assertEqual(decision["policy_trigger"], "booking_deadline")


if __name__ == "__main__":
    unittest.main()
