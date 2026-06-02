# PRL-Tech

Aplicacion para almacenar lecturas ambientales en PostgreSQL, sincronizar datos desde ThingSpeak, consultar metricas y generar informes PDF.

## Servicios

```text
React       http://localhost:5173
FastAPI     http://localhost:8000
API docs    http://localhost:8000/docs
Adminer     http://localhost:8080
PostgreSQL  localhost:5432
```

## Arranque

1. Crea `.env` desde `.env.example` si no existe:

```powershell
Copy-Item .env.example .env
```

2. Rellena en `.env` tus valores reales de ThingSpeak:

```text
THINGSPEAK_CHANNEL_ID=
THINGSPEAK_READ_API_KEY=
```

3. Levanta todo:

```powershell
docker compose up -d --build
```

4. Verifica servicios:

```powershell
docker compose ps
docker compose logs -f api
```

## Uso

Abrir el dashboard:

```text
http://localhost:5173
```

Consultar datos desde la API:

```text
http://localhost:8000/devices/home_dht22/series?limit=1000
http://localhost:8000/devices/home_dht22/summary?threshold_c=30&hot_window_hours=2
```

Generar informe PDF:

```text
http://localhost:8000/devices/home_dht22/report.pdf?threshold_c=30&hot_window_hours=2
```

## Base de datos

Adminer:

```text
http://localhost:8080
```

Credenciales:

```text
Sistema: PostgreSQL
Servidor: db
Usuario: prl_user
Password: valor de POSTGRES_PASSWORD en .env
Base de datos: prl_tech
```

Tablas principales:

```text
devices
measurement_types
sensors
sensor_readings
```

## Sincronizacion ThingSpeak

La API sincroniza automaticamente ThingSpeak cada `THINGSPEAK_SYNC_INTERVAL_SECONDS` segundos cuando:

```text
THINGSPEAK_SYNC_ENABLED=true
```

Tambien puedes forzar una sincronizacion manual:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/integrations/thingspeak/sync" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"device_code":"home_dht22"}'
```

## Desarrollo

Backend:

```powershell
docker compose up -d --build api
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run build
```

Parar servicios:

```powershell
docker compose down
```

Borrar tambien la base de datos:

```powershell
docker compose down -v
```
