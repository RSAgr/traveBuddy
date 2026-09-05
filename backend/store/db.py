"""PostgreSQL repositories for durable application records.

Live LangGraph state intentionally remains in ``TRIPS``. It contains messages and
intermediate graph values and is not a database concern.
"""
import json
import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


TRIPS = {}  # Ephemeral workflow state only; do not persist graph state here.


class Database:
    def __init__(self):
        self._pool = None

    @contextmanager
    def connection(self):
        url = os.getenv("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required for persistent travel data.")
        if self._pool is None:
            self._pool = ConnectionPool(url, min_size=1, max_size=int(os.getenv("DATABASE_POOL_MAX_SIZE", "5")), kwargs={"row_factory": dict_row})
        with self._pool.connection() as connection:
            yield connection

    def close(self):
        if self._pool:
            self._pool.close()
            self._pool = None


DATABASE = Database()


def _json(value):
    return json.dumps(value if value is not None else {}, default=str)


class PriceRepository:
    def save_snapshot(self, snapshot):
        features = snapshot.get("features", {})
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO price_snapshots (trip_id, route, source, destination, transport_type, current_price, observed_at, days_to_departure, demand_index, seasonality_index, features, components) VALUES (%(trip_id)s, %(route)s, %(source)s, %(destination)s, %(transport_type)s, %(current_price)s, %(observed_at)s, %(days_to_departure)s, %(demand_index)s, %(seasonality_index)s, %(features)s::jsonb, %(components)s::jsonb)""", {**snapshot, "observed_at": snapshot.get("timestamp"), "source": snapshot.get("source"), "demand_index": features.get("demand_index"), "seasonality_index": features.get("seasonality_index"), "features": _json(features), "components": _json(snapshot.get("components", []))})
            conn.commit()
        return snapshot

    def get_history(self, trip_id):
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT trip_id, route, source, destination, transport_type, current_price, observed_at, days_to_departure, features, components FROM price_snapshots WHERE trip_id = %s ORDER BY observed_at, id", (trip_id,))
            return [{"timestamp": row["observed_at"].isoformat(), "trip_id": row["trip_id"], "route": row["route"], "source": row["source"], "destination": row["destination"], "transport_type": row["transport_type"], "current_price": float(row["current_price"]), "days_to_departure": row["days_to_departure"], "features": row["features"], "components": row["components"]} for row in cur.fetchall()]

    def all_snapshots(self):
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT trip_id, route, transport_type, current_price, days_to_departure, features FROM price_snapshots ORDER BY observed_at")
            return [{"trip_id": r["trip_id"], "route": r["route"], "transport_type": r["transport_type"], "current_price": float(r["current_price"]), "days_to_departure": r["days_to_departure"], "features": r["features"]} for r in cur.fetchall()]


class PriceOverrideRepository:
    def list_overrides(self, active_only=False):
        query = "SELECT id, route, component_name, component_type, mode, price, price_multiplier, active, reason, updated_at FROM price_overrides"
        params = ()
        if active_only:
            query += " WHERE active = true"
        query += " ORDER BY route, component_type, mode, component_name"
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return [
                {
                    **row,
                    "price": float(row["price"]) if row["price"] is not None else None,
                    "price_multiplier": float(row["price_multiplier"]) if row["price_multiplier"] is not None else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in cur.fetchall()
            ]

    def active_for_route(self, route):
        route_key = route or "Puri"
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT route, component_name, component_type, mode, price, price_multiplier, reason
                FROM price_overrides
                WHERE active = true AND lower(route) = lower(%s)
                """,
                (route_key,),
            )
            return {
                row["component_name"]: {
                    "route": row["route"],
                    "component_name": row["component_name"],
                    "component_type": row["component_type"],
                    "mode": row["mode"],
                    "price": float(row["price"]) if row["price"] is not None else None,
                    "price_multiplier": float(row["price_multiplier"]) if row["price_multiplier"] is not None else None,
                    "reason": row["reason"],
                }
                for row in cur.fetchall()
            }

    def upsert(self, data):
        if not data.get("component_name"):
            raise ValueError("component_name is required")
        if data.get("price") is None and data.get("price_multiplier") is None:
            raise ValueError("price or price_multiplier is required")
        route = data.get("route") or "Puri"
        active = data.get("active", True)
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO price_overrides
                    (route, component_name, component_type, mode, price, price_multiplier, active, reason)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (route, component_name)
                DO UPDATE SET
                    component_type = EXCLUDED.component_type,
                    mode = EXCLUDED.mode,
                    price = EXCLUDED.price,
                    price_multiplier = EXCLUDED.price_multiplier,
                    active = EXCLUDED.active,
                    reason = EXCLUDED.reason,
                    updated_at = now()
                RETURNING id, route, component_name, component_type, mode, price, price_multiplier, active, reason, updated_at
                """,
                (
                    route,
                    data["component_name"],
                    data.get("component_type"),
                    data.get("mode"),
                    data.get("price"),
                    data.get("price_multiplier"),
                    active,
                    data.get("reason"),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return {
                **row,
                "price": float(row["price"]) if row["price"] is not None else None,
                "price_multiplier": float(row["price_multiplier"]) if row["price_multiplier"] is not None else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

    def clear(self, route=None):
        with DATABASE.connection() as conn, conn.cursor() as cur:
            if route:
                cur.execute("UPDATE price_overrides SET active = false, updated_at = now() WHERE lower(route) = lower(%s)", (route,))
            else:
                cur.execute("UPDATE price_overrides SET active = false, updated_at = now()")
            count = cur.rowcount
            conn.commit()
            return count


class TripRepository:
    def save(self, trip_id, constraints, status, itinerary=None):
        try:
            deadline = int(constraints.get("deadline"))
        except (TypeError, ValueError):
            deadline = None
        departure = deadline if deadline and deadline > 10_000_000 else None
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO trips (id, user_id, source, destination, departure_at, budget, preferences, itinerary, status) VALUES (%s, %s, %s, %s, to_timestamp(%s), %s, %s::jsonb, %s::jsonb, %s) ON CONFLICT (id) DO UPDATE SET source=EXCLUDED.source, destination=EXCLUDED.destination, departure_at=EXCLUDED.departure_at, budget=EXCLUDED.budget, preferences=EXCLUDED.preferences, itinerary=COALESCE(EXCLUDED.itinerary, trips.itinerary), status=EXCLUDED.status, updated_at=now()""", (trip_id, constraints.get("user_id"), constraints.get("source"), constraints.get("destination"), departure, constraints.get("budget"), _json(constraints), _json(itinerary) if itinerary else None, status))
            conn.commit()


class DecisionRepository:
    def save(self, trip_id, decision, prediction=None):
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO booking_decisions (trip_id, predicted_price, decision, confidence, trend, reasoning, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)", (trip_id, prediction, decision.get("decision"), decision.get("confidence"), decision.get("trend"), decision.get("reason"), _json(decision)))
            conn.commit()


class BlockchainRepository:
    def save(self, trip_id, app_id=None, transaction_id=None, status="CREATED", metadata=None):
        with DATABASE.connection() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO blockchain_deployments (trip_id, algorand_app_id, transaction_id, status, metadata) VALUES (%s, %s, %s, %s, %s::jsonb)", (trip_id, str(app_id) if app_id is not None else None, transaction_id, status, _json(metadata)))
            conn.commit()


PRICE_REPOSITORY = PriceRepository()
PRICE_OVERRIDE_REPOSITORY = PriceOverrideRepository()
TRIP_REPOSITORY = TripRepository()
DECISION_REPOSITORY = DecisionRepository()
BLOCKCHAIN_REPOSITORY = BlockchainRepository()
