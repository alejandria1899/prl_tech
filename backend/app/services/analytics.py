from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Device, Sensor, SensorReading


TEMPERATURE_SENSOR = "temperature_dht22"
HUMIDITY_SENSOR = "humidity_dht22"


def get_device_or_none(db: Session, device_code: str) -> Device | None:
    return db.scalar(select(Device).where(Device.code == device_code))


def get_series(
    db: Session,
    *,
    device: Device,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[dict]:
    rows = _reading_rows(db, device=device, start=start, end=end, limit=limit * 16)
    grouped: dict[datetime, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        grouped[row.measured_at][row.sensor_code] = row.value

    points = [
        {"measured_at": measured_at, "values": values}
        for measured_at, values in sorted(grouped.items())
    ]
    return points[:limit]


def get_summary(
    db: Session,
    *,
    device: Device,
    start: datetime | None,
    end: datetime | None,
    limit: int,
    threshold_c: float,
    hot_window_hours: int,
) -> dict:
    points = get_series(db, device=device, start=start, end=end, limit=limit)
    temp_points = [
        (point["measured_at"], float(point["values"][TEMPERATURE_SENSOR]))
        for point in points
        if TEMPERATURE_SENSOR in point["values"]
    ]
    hum_values = [
        float(point["values"][HUMIDITY_SENSOR])
        for point in points
        if HUMIDITY_SENSOR in point["values"]
    ]

    temp_values = [value for _, value in temp_points]
    intervals = _threshold_intervals(temp_points, threshold_c)
    hot_window = _hot_window(temp_points, hot_window_hours)

    return {
        "start": points[0]["measured_at"] if points else start,
        "end": points[-1]["measured_at"] if points else end,
        "records": len(temp_points),
        "temp_avg_c": _round_or_none(_avg(temp_values)),
        "temp_min_c": _round_or_none(min(temp_values) if temp_values else None),
        "temp_max_c": _round_or_none(max(temp_values) if temp_values else None),
        "hum_avg_pct": _round_or_none(_avg(hum_values)),
        "hot_window": hot_window,
        "threshold_c": threshold_c,
        "minutes_over_threshold": sum(interval["minutes"] for interval in intervals),
        "intervals_over_threshold": intervals,
    }


def _reading_rows(
    db: Session,
    *,
    device: Device,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list:
    stmt = (
        select(
            SensorReading.measured_at,
            Sensor.code.label("sensor_code"),
            SensorReading.value,
        )
        .join(Sensor, Sensor.id == SensorReading.sensor_id)
        .where(Sensor.device_id == device.id)
    )
    if start is not None:
        stmt = stmt.where(SensorReading.measured_at >= start)
    if end is not None:
        stmt = stmt.where(SensorReading.measured_at <= end)
    stmt = stmt.order_by(SensorReading.measured_at.asc(), Sensor.code).limit(limit)
    return list(db.execute(stmt))


def _threshold_intervals(points: list[tuple[datetime, float]], threshold_c: float) -> list[dict]:
    intervals = []
    current_start = None
    previous_time = None

    for measured_at, value in points:
        if value >= threshold_c and current_start is None:
            current_start = measured_at
        elif value < threshold_c and current_start is not None:
            end = previous_time or measured_at
            intervals.append(_interval(current_start, end))
            current_start = None
        previous_time = measured_at

    if current_start is not None and previous_time is not None:
        intervals.append(_interval(current_start, previous_time))

    return intervals


def _hot_window(points: list[tuple[datetime, float]], window_hours: int) -> dict | None:
    if not points:
        return None

    best = None
    left = 0
    running_sum = 0.0
    window_seconds = window_hours * 3600

    for right, (end_time, value) in enumerate(points):
        running_sum += value
        while left <= right and (end_time - points[left][0]).total_seconds() > window_seconds:
            running_sum -= points[left][1]
            left += 1
        count = right - left + 1
        if count <= 0:
            continue
        average = running_sum / count
        if best is None or average > best["average_temp_c"]:
            best = {
                "start": points[left][0],
                "end": end_time,
                "average_temp_c": round(average, 1),
            }

    return best


def _interval(start: datetime, end: datetime) -> dict:
    return {
        "start": start,
        "end": end,
        "minutes": max(int((end - start).total_seconds() / 60), 0),
    }


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)
