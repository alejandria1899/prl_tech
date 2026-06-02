import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import SessionLocal, engine, get_db
from backend.app.models import Device, MeasurementType, Sensor, SensorReading
from backend.app.integrations.thingspeak import ThingSpeakConfigError, sync_thingspeak_device
from backend.app.services.reports import generate_device_report_pdf
from backend.app.services.analytics import get_device_or_none, get_series, get_summary
from backend.app.schemas import (
    DeviceCreate,
    DeviceMeasurementPayload,
    DeviceRead,
    DeviceSeriesResponse,
    DeviceSensorReadingRead,
    DeviceSummaryResponse,
    MeasurementTypeRead,
    SensorCreate,
    SensorRead,
    SensorReadingCreate,
    SensorReadingRead,
    ThingSpeakSyncRequest,
    ThingSpeakSyncResult,
)

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(_initialize_database)
    task = None
    if settings.thingspeak_sync_enabled:
        task = asyncio.create_task(_thingspeak_sync_loop())
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)


def _initialize_database() -> None:
    root = Path(__file__).resolve().parents[2]
    sql_files = [
        root / "database" / "init" / "001_schema.sql",
        root / "database" / "migrations" / "002_extensible_sensors.sql",
    ]

    with engine.begin() as connection:
        for sql_file in sql_files:
            connection.exec_driver_sql(sql_file.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/devices", response_model=list[DeviceRead])
def list_devices(db: Session = Depends(get_db)) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.code)))


@app.post("/devices", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)) -> Device:
    device = Device(**payload.model_dump())
    db.add(device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Device code already exists") from exc
    db.refresh(device)
    return device


@app.get("/measurement-types", response_model=list[MeasurementTypeRead])
def list_measurement_types(db: Session = Depends(get_db)) -> list[MeasurementType]:
    return list(db.scalars(select(MeasurementType).order_by(MeasurementType.code)))


@app.get("/sensors", response_model=list[SensorRead])
def list_sensors(device_id: int | None = None, db: Session = Depends(get_db)) -> list[Sensor]:
    stmt = select(Sensor).order_by(Sensor.device_id, Sensor.code)
    if device_id is not None:
        stmt = stmt.where(Sensor.device_id == device_id)
    return list(db.scalars(stmt))


@app.post("/sensors", response_model=SensorRead, status_code=status.HTTP_201_CREATED)
def create_sensor(payload: SensorCreate, db: Session = Depends(get_db)) -> Sensor:
    sensor = Sensor(**payload.model_dump())
    db.add(sensor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Sensor already exists or references are invalid") from exc
    db.refresh(sensor)
    return sensor


@app.get("/readings", response_model=list[SensorReadingRead])
def list_readings(
    sensor_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=1000, ge=1, le=20000),
    db: Session = Depends(get_db),
) -> list[SensorReading]:
    stmt = select(SensorReading).where(SensorReading.sensor_id == sensor_id)
    if start is not None:
        stmt = stmt.where(SensorReading.measured_at >= start)
    if end is not None:
        stmt = stmt.where(SensorReading.measured_at <= end)
    stmt = stmt.order_by(SensorReading.measured_at.desc()).limit(limit)
    return list(db.scalars(stmt))


@app.get("/devices/{device_code}/readings", response_model=list[DeviceSensorReadingRead])
def list_device_readings(
    device_code: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=5000, ge=1, le=50000),
    db: Session = Depends(get_db),
) -> list[dict]:
    device = db.scalar(select(Device).where(Device.code == device_code))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    stmt = (
        select(
            SensorReading.sensor_id,
            Sensor.code.label("sensor_code"),
            SensorReading.measured_at,
            SensorReading.value,
            Sensor.unit,
            SensorReading.source,
            SensorReading.external_entry_id,
        )
        .join(Sensor, Sensor.id == SensorReading.sensor_id)
        .where(Sensor.device_id == device.id)
    )
    if start is not None:
        stmt = stmt.where(SensorReading.measured_at >= start)
    if end is not None:
        stmt = stmt.where(SensorReading.measured_at <= end)
    stmt = stmt.order_by(SensorReading.measured_at.desc(), Sensor.code).limit(limit)
    return [dict(row._mapping) for row in db.execute(stmt)]


@app.get("/devices/{device_code}/series", response_model=DeviceSeriesResponse)
def device_series(
    device_code: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=50000, ge=1, le=200000),
    db: Session = Depends(get_db),
) -> dict:
    device = get_device_or_none(db, device_code)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "device_code": device_code,
        "points": get_series(db, device=device, start=start, end=end, limit=limit),
    }


@app.get("/devices/{device_code}/summary", response_model=DeviceSummaryResponse)
def device_summary(
    device_code: str,
    start: datetime | None = None,
    end: datetime | None = None,
    threshold_c: float = Query(default=30.0),
    hot_window_hours: int = Query(default=2, ge=1, le=8),
    limit: int = Query(default=50000, ge=1, le=200000),
    db: Session = Depends(get_db),
) -> dict:
    device = get_device_or_none(db, device_code)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "device_code": device_code,
        **get_summary(
            db,
            device=device,
            start=start,
            end=end,
            limit=limit,
            threshold_c=threshold_c,
            hot_window_hours=hot_window_hours,
        ),
    }


@app.get("/devices/{device_code}/report.pdf")
def device_report_pdf(
    device_code: str,
    start: datetime | None = None,
    end: datetime | None = None,
    threshold_c: float = Query(default=30.0),
    hot_window_hours: int = Query(default=2, ge=1, le=8),
    limit: int = Query(default=50000, ge=1, le=200000),
    db: Session = Depends(get_db),
) -> FileResponse:
    device = get_device_or_none(db, device_code)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    pdf_path = generate_device_report_pdf(
        db,
        device=device,
        start=start,
        end=end,
        threshold_c=threshold_c,
        hot_window_hours=hot_window_hours,
        limit=limit,
    )
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@app.post("/readings", response_model=SensorReadingRead, status_code=status.HTTP_201_CREATED)
def create_reading(payload: SensorReadingCreate, db: Session = Depends(get_db)) -> SensorReading:
    reading = SensorReading(**payload.model_dump())
    db.add(reading)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reading already exists or sensor is invalid") from exc
    db.refresh(reading)
    return reading


@app.post("/device-readings", response_model=list[SensorReadingRead], status_code=status.HTTP_201_CREATED)
def create_device_readings(payload: DeviceMeasurementPayload, db: Session = Depends(get_db)) -> list[SensorReading]:
    device = db.scalar(select(Device).where(Device.code == payload.device_code))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    sensors = db.scalars(select(Sensor).where(Sensor.device_id == device.id)).all()
    sensors_by_code = {sensor.code: sensor for sensor in sensors}

    missing = sorted(set(payload.values) - set(sensors_by_code))
    if missing:
        raise HTTPException(status_code=422, detail={"unknown_sensors": missing})

    readings = [
        SensorReading(
            sensor_id=sensors_by_code[sensor_code].id,
            measured_at=payload.measured_at,
            value=value,
            source=payload.source,
            external_entry_id=payload.external_entry_id,
        )
        for sensor_code, value in payload.values.items()
    ]
    db.add_all(readings)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="One or more readings already exist") from exc

    for reading in readings:
        db.refresh(reading)
    return readings


@app.post("/integrations/thingspeak/sync", response_model=ThingSpeakSyncResult)
def sync_thingspeak(payload: ThingSpeakSyncRequest, db: Session = Depends(get_db)) -> dict[str, int | str]:
    channel_id = payload.channel_id or _optional_int(settings.thingspeak_channel_id)
    read_api_key = payload.read_api_key or settings.thingspeak_read_api_key
    results = payload.results or settings.thingspeak_default_results

    if channel_id is None or not read_api_key:
        raise HTTPException(status_code=400, detail="ThingSpeak channel_id and read_api_key are required")

    try:
        return sync_thingspeak_device(
            db,
            device_code=payload.device_code,
            channel_id=channel_id,
            read_api_key=read_api_key,
            results=results,
        )
    except ThingSpeakConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _optional_int(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


async def _thingspeak_sync_loop() -> None:
    while True:
        await asyncio.to_thread(_run_configured_thingspeak_sync)
        await asyncio.sleep(max(settings.thingspeak_sync_interval_seconds, 10))


def _run_configured_thingspeak_sync() -> None:
    channel_id = _optional_int(settings.thingspeak_channel_id)
    read_api_key = settings.thingspeak_read_api_key
    if channel_id is None or not read_api_key:
        logger.warning("ThingSpeak auto sync skipped: missing channel or API key")
        return

    db = SessionLocal()
    try:
        result = sync_thingspeak_device(
            db,
            device_code=settings.thingspeak_sync_device_code,
            channel_id=channel_id,
            read_api_key=read_api_key,
            results=settings.thingspeak_default_results,
        )
        logger.warning("ThingSpeak auto sync completed: %s", result)
    except Exception:
        logger.exception("ThingSpeak auto sync failed")
    finally:
        db.close()
