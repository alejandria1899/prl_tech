import pandas as pd

def resumen_basico(df, col_temp, col_hum):
    return {
        "n": int(len(df)),
        "temp_media": round(df[col_temp].mean(), 1),
        "temp_max": round(df[col_temp].max(), 1),
        "temp_min": round(df[col_temp].min(), 1),
        "hum_media": round(df[col_hum].mean(), 1) if col_hum in df.columns else None
    }

def minutos_sobre_umbral(df, col_temp, umbral, col_ts):
    # cada fila = intervalo_min minutos (suponemos fijo)
    return int((df[df[col_temp] > umbral].shape[0]))
