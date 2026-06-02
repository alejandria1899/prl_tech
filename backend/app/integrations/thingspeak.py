from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.models import Device, Sensor, SensorReading


class ThingSpeakConfigError(ValueError):
    pass


def fetch_feeds(channel_id: int, read_api_key: str, results: int) -> list[dict[str, Any]]:
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
    response = requests.get(url, params={"api_key": read_api_key, "results": results}, timeout=15)
    response.raise_for_status()
    payload = response.json()
    feeds = payload.get("feeds", [])
    if not isinstance(feeds, list):
        return []
    return feeds


def sync_thingspeak_device(
    db: Session,
    *,
    device_code: str,
    channel_id: int,
    read_api_key: str,
    results: int,
) -> dict[str, int | str]:
    device = db.scalar(select(Device).where(Device.code == device_code))
    if device is None:
        raise ThingSpeakConfigError(f"Device not found: {device_code}")

    sensors = db.scalars(
        select(Sensor).where(
            Sensor.device_id == device.id,
            Sensor.is_active.is_(True),
            Sensor.thingspeak_field.is_not(None),
        )
    ).all()
    if not sensors:
        raise ThingSpeakConfigError(f"Device has no active ThingSpeak sensors: {device_code}")

    feeds = fetch_feeds(channel_id=channel_id, read_api_key=read_api_key, results=results)
    attempted = 0
    inserted = 0
    skipped = 0

    for feed in feeds:
        measured_at = _parse_timestamp(feed.get("created_at"))
        if measured_at is None:
            skipped += 1
            continue

        external_entry_id = _as_text(feed.get("entry_id"))
        rows = []
        for sensor in sensors:
            value = _parse_decimal(feed.get(f"field{sensor.thingspeak_field}"))
            if value is None:
                continue
            attempted += 1
            rows.append(
                {
                    "sensor_id": sensor.id,
                    "measured_at": measured_at,
                    "value": value,
                    "source": "thingspeak",
                    "external_entry_id": external_entry_id,
                }
            )

        if not rows:
            skipped += 1
            continue

        stmt = insert(SensorReading).values(rows).returning(SensorReading.id)
        stmt = stmt.on_conflict_do_nothing(index_elements=["sensor_id", "measured_at"])
        inserted += len(db.scalars(stmt).all())

    db.commit()
    return {
        "device_code": device_code,
        "feeds": len(feeds),
        "attempted_readings": attempted,
        "inserted_readings": inserted,
        "skipped_feeds": skipped,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    normalized = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None


def _as_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
