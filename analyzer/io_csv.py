# analyzer/io_csv.py
import pandas as pd

def cargar_csv(ruta, col_ts, col_temp, col_hum):
    """
    Lee el CSV, parsea fechas y fuerza columnas numéricas (coma -> punto).
    Si no existe col_hum, la crea como NaN.
    Devuelve DataFrame ordenado por timestamp.
    """
    df = pd.read_csv(ruta, parse_dates=[col_ts])

    # Asegurar columnas presentes
    faltan = {col_ts, col_temp} - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas obligatorias: {faltan}")
    if col_hum not in df.columns:
        df[col_hum] = None

    # Normalizar posibles comas decimales y forzar a float
    df[col_temp] = (
        df[col_temp]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    # Humedad si existe con valores
    try:
        df[col_hum] = (
            df[col_hum]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )
    except Exception:
        pass

    # Limpiar y ordenar
    df = df.dropna(subset=[col_ts, col_temp]).sort_values(col_ts).reset_index(drop=True)
    return df
