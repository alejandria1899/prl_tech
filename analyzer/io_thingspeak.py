# analyzer/io_thingspeak.py
import requests
import pandas as pd


def cargar_desde_thingspeak(
    channel_id: int,
    read_api_key: str,
    field_temp: int = 1,
    field_hum: int = 2,
    results: int = 10000,
) -> pd.DataFrame:
    """
    Descarga datos de ThingSpeak y devuelve un DataFrame con:
    - timestamp (datetime, sin zona horaria)
    - temp_c (float)
    - hum_pct (float o NaN)

    Se asume:
      field_temp -> temperatura (°C)
      field_hum  -> humedad (%)
    """

    # Endpoint correcto para varios campos:
    # https://api.thingspeak.com/channels/{id}/feeds.json
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"

    params = {
        "api_key": read_api_key,
        "results": results,
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()  # si hay 4xx/5xx lanza excepción

    data = resp.json()
    feeds = data.get("feeds", [])

    if not feeds:
        # DataFrame vacío con las columnas esperadas
        return pd.DataFrame(columns=["timestamp", "temp_c", "hum_pct"])

    df = pd.DataFrame(feeds)

    # Parseo de fecha
    ts = pd.to_datetime(df["created_at"], utc=True, errors="coerce").dt.tz_localize(None)
    df["timestamp"] = ts

    temp_key = f"field{field_temp}"
    hum_key = f"field{field_hum}"

    df["temp_c"] = pd.to_numeric(df[temp_key], errors="coerce")

    if hum_key in df.columns:
        df["hum_pct"] = pd.to_numeric(df[hum_key], errors="coerce")
    else:
        df["hum_pct"] = pd.NA

    df = (
        df[["timestamp", "temp_c", "hum_pct"]]
        .dropna(subset=["timestamp", "temp_c"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df
