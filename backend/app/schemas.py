from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    location: str | None = None
    description: str | None = None


class DeviceRead(DeviceCreate):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeasurementTypeRead(BaseModel):
    id: int
    code: str
    name: str
    default_unit: str

    model_config = ConfigDict(from_attributes=True)


class SensorCreate(BaseModel):
    device_id: int
    measurement_type_id: int
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=32)
    thingspeak_field: int | None = Field(default=None, ge=1, le=8)


class SensorRead(SensorCreate):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SensorReadingCreate(BaseModel):
    sensor_id: int
    measured_at: datetime
    value: Decimal
    source: str = "api"
    external_entry_id: str | None = None


class SensorReadingRead(SensorReadingCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceSensorReadingRead(BaseModel):
    sensor_id: int
    sensor_code: str
    measured_at: datetime
    value: Decimal
    unit: str
    source: str
    external_entry_id: str | None = None


class DeviceMeasurementPayload(BaseModel):
    device_code: str
    measured_at: datetime
    values: dict[str, Decimal]
    source: str = "api"
    external_entry_id: str | None = None


class ThingSpeakSyncRequest(BaseModel):
    device_code: str = "home_dht22"
    channel_id: int | None = None
    read_api_key: str | None = None
    results: int | None = Field(default=None, ge=1, le=20000)


class ThingSpeakSyncResult(BaseModel):
    device_code: str
    feeds: int
    attempted_readings: int
    inserted_readings: int
    skipped_feeds: int


class TimeSeriesPoint(BaseModel):
    measured_at: datetime
    values: dict[str, Decimal]


class DeviceSeriesResponse(BaseModel):
    device_code: str
    points: list[TimeSeriesPoint]


class HotWindow(BaseModel):
    start: datetime
    end: datetime
    average_temp_c: float


class ThresholdInterval(BaseModel):
    start: datetime
    end: datetime
    minutes: int


class DeviceSummaryResponse(BaseModel):
    device_code: str
    start: datetime | None
    end: datetime | None
    records: int
    temp_avg_c: float | None
    temp_min_c: float | None
    temp_max_c: float | None
    hum_avg_pct: float | None
    hot_window: HotWindow | None
    threshold_c: float
    minutes_over_threshold: int
    intervals_over_threshold: list[ThresholdInterval]
