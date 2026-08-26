import logging
from datetime import datetime, timezone
from typing import Any

from store.db import NOTIFICATIONS

logger = logging.getLogger(__name__)


def _append_notification(trip_id: str, notification: dict[str, Any]) -> None:
    notifications = NOTIFICATIONS.setdefault(trip_id, [])
    notifications.append(notification)


def record_notification(trip_id: str, message: str, level: str = "info", event_type: str | None = None) -> dict[str, Any]:
    notification = {
        "trip_id": trip_id,
        "level": level,
        "message": message,
        "event_type": event_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_notification(trip_id, notification)
    logger.info("Notification recorded for trip_id=%s: %s", trip_id, message)
    return notification


def handle_trip_event(event: dict[str, Any]) -> None:
    event_type = event.get("event_type")
    payload = event.get("payload") or {}
    trip_id = payload.get("trip_id")

    if not trip_id:
        return

    if event_type == "trip.created":
        user_id = payload.get("user_id", "unknown user")
        app_id = payload.get("app_id", "unknown app")
        record_notification(
            trip_id,
            f"Trip {trip_id} is now queued for monitoring for user {user_id} (app_id={app_id}).",
            level="info",
            event_type=event_type,
        )
    elif event_type == "trip.booked":
        commit_tx_id = payload.get("commit_tx_id", "unknown")
        release_tx_id = payload.get("release_tx_id", "unknown")
        record_notification(
            trip_id,
            f"Trip {trip_id} was booked successfully. Commit tx: {commit_tx_id}, release tx: {release_tx_id}.",
            level="success",
            event_type=event_type,
        )
    else:
        record_notification(
            trip_id,
            f"Received unsupported event type: {event_type}",
            level="warning",
            event_type=event_type,
        )


def get_notifications(trip_id: str) -> list[dict[str, Any]]:
    return NOTIFICATIONS.get(trip_id, [])