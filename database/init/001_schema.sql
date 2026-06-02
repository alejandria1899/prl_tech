CREATE TABLE IF NOT EXISTS devices (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    location TEXT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS measurement_types (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    default_unit TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sensors (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    measurement_type_id BIGINT NOT NULL REFERENCES measurement_types(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    thingspeak_field INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, code)
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    sensor_id BIGINT NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
    measured_at TIMESTAMPTZ NOT NULL,
    value NUMERIC(12, 4) NOT NULL,
    source TEXT NOT NULL DEFAULT 'api',
    external_entry_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sensor_id, measured_at)
);

CREATE TABLE IF NOT EXISTS measurements (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    measured_at TIMESTAMPTZ NOT NULL,
    temp_c NUMERIC(5, 2) NOT NULL,
    hum_pct NUMERIC(5, 2),
    source TEXT NOT NULL DEFAULT 'api',
    thingspeak_entry_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, measured_at)
);

CREATE INDEX IF NOT EXISTS idx_measurements_device_time
    ON measurements (device_id, measured_at DESC);

CREATE INDEX IF NOT EXISTS idx_sensors_device
    ON sensors (device_id);

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_time
    ON sensor_readings (sensor_id, measured_at DESC);

INSERT INTO devices (code, name, location)
VALUES ('home_dht22', 'Mi estacion DHT22', 'Casa')
ON CONFLICT (code) DO NOTHING;

INSERT INTO measurement_types (code, name, default_unit)
VALUES
    ('temperature', 'Temperatura', 'degC'),
    ('humidity', 'Humedad relativa', 'percent'),
    ('co2', 'CO2', 'ppm'),
    ('noise', 'Ruido', 'dBA'),
    ('light', 'Iluminacion', 'lux')
ON CONFLICT (code) DO NOTHING;

INSERT INTO sensors (device_id, measurement_type_id, code, name, unit, thingspeak_field)
SELECT d.id, mt.id, 'temperature_dht22', 'Temperatura DHT22', 'degC', 1
FROM devices d
JOIN measurement_types mt ON mt.code = 'temperature'
WHERE d.code = 'home_dht22'
ON CONFLICT (device_id, code) DO NOTHING;

INSERT INTO sensors (device_id, measurement_type_id, code, name, unit, thingspeak_field)
SELECT d.id, mt.id, 'humidity_dht22', 'Humedad DHT22', 'percent', 2
FROM devices d
JOIN measurement_types mt ON mt.code = 'humidity'
WHERE d.code = 'home_dht22'
ON CONFLICT (device_id, code) DO NOTHING;
