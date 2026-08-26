import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Awaitable, Callable, Optional

from dotenv import load_dotenv

from store.db import TRIPS
from services.notification_service import handle_trip_event

load_dotenv()

logger = logging.getLogger(__name__)

try:
    kafka_module = import_module("aiokafka")
    AIOKafkaConsumer = kafka_module.AIOKafkaConsumer
    AIOKafkaProducer = kafka_module.AIOKafkaProducer
except Exception:  # pragma: no cover - optional dependency fallback
    AIOKafkaConsumer = None
    AIOKafkaProducer = None


@dataclass(frozen=True)
class KafkaSettings:
    bootstrap_servers: str
    topic: str
    group_id: str
    enabled: bool


def load_kafka_settings() -> KafkaSettings:
    enabled = os.getenv("KAFKA_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.getenv("KAFKA_TRIP_EVENTS_TOPIC", "travebuddy.trip.events")
    group_id = os.getenv("KAFKA_GROUP_ID", "travebuddy-trip-workers")

    return KafkaSettings(
        bootstrap_servers=bootstrap_servers,
        topic=topic,
        group_id=group_id,
        enabled=enabled,
    )


class KafkaService:
    def __init__(self, settings: Optional[KafkaSettings] = None):
        self.settings = settings or load_kafka_settings()
        self._producer = None
        self._consumer = None
        self._consumer_task: Optional[asyncio.Task] = None
        self._active_trip_tasks: dict[str, asyncio.Task] = {}

    @property
    def enabled(self) -> bool:
        return self.settings.enabled and AIOKafkaProducer is not None and AIOKafkaConsumer is not None

    async def start(self) -> None:
        if not self.enabled:
            logger.info("Kafka disabled or unavailable; using local fallback execution")
            return

        if self._producer is not None:
            return

        self._producer = AIOKafkaProducer(bootstrap_servers=self.settings.bootstrap_servers)
        await self._producer.start()

        self._consumer = AIOKafkaConsumer(
            self.settings.topic,
            bootstrap_servers=self.settings.bootstrap_servers,
            group_id=self.settings.group_id,
            enable_auto_commit=True,
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("Kafka started on %s", self.settings.bootstrap_servers)

    async def stop(self) -> None:
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish_trip_event(self, event_type: str, payload: dict[str, Any]) -> bool:
        if not self.enabled or self._producer is None:
            return False

        event = {
            "event_type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        message = json.dumps(event).encode("utf-8")
        await self._producer.send_and_wait(self.settings.topic, message)
        return True

    async def _consume_loop(self) -> None:
        if self._consumer is None:
            return

        try:
            async for message in self._consumer:
                try:
                    event = json.loads(message.value.decode("utf-8"))
                except Exception as exc:
                    logger.exception("Failed to decode Kafka event: %s", exc)
                    continue

                await self._handle_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Kafka consumer loop stopped: %s", exc)

    async def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("event_type")
        payload = event.get("payload") or {}

        handle_trip_event(event)

        if event_type == "trip.created":
            await self._handle_trip_created(payload)
        elif event_type == "trip.booked":
            self._handle_trip_booked(payload)

    async def _handle_trip_created(self, payload: dict[str, Any]) -> None:
        trip_id = payload.get("trip_id")
        if not trip_id:
            logger.warning("Kafka trip.created event missing trip_id")
            return

        if trip_id in self._active_trip_tasks and not self._active_trip_tasks[trip_id].done():
            return

        if trip_id not in TRIPS:
            logger.warning("Trip %s was published before state was stored", trip_id)
            return

        from services.scheduler import run_trip

        self._active_trip_tasks[trip_id] = asyncio.create_task(run_trip(trip_id))
        logger.info("Started trip monitor from Kafka event for trip_id=%s", trip_id)

    def _handle_trip_booked(self, payload: dict[str, Any]) -> None:
        trip_id = payload.get("trip_id")
        if not trip_id:
            return

        trip = TRIPS.get(trip_id)
        if trip is not None:
            trip["status"] = "BOOKED"
        logger.info("Processed trip.booked event for trip_id=%s", trip_id)


_kafka_service: Optional[KafkaService] = None


def configure_kafka_service(service: KafkaService) -> None:
    global _kafka_service
    _kafka_service = service


def get_kafka_service() -> Optional[KafkaService]:
    return _kafka_service


async def publish_trip_event(event_type: str, payload: dict[str, Any]) -> bool:
    service = get_kafka_service()
    if service is None:
        return False

    try:
        return await service.publish_trip_event(event_type, payload)
    except Exception as exc:
        logger.exception("Kafka publish failed for %s: %s", event_type, exc)
        return False