import pandas as pd

def franja_mas_caliente(df, col_ts, col_temp, ventana_horas=2):
    ds = df.set_index(col_ts).sort_index()
    roll = ds[col_temp].rolling(f"{ventana_horas}H").mean()
    idxmax = roll.idxmax()
    if pd.isna(idxmax):
        return None
    t_fin = idxmax
    t_ini = t_fin - pd.Timedelta(hours=ventana_horas)
    return {"inicio": t_ini, "fin": t_fin, "temp_media_franja": round(roll.loc[idxmax], 1)}
