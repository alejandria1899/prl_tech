import pandas as pd

def check_gaps(df, col_ts, intervalo_min, max_gap_min):
    deltas = df[col_ts].diff().dt.total_seconds().div(60)
    gaps = df.loc[(deltas > max_gap_min)]
    return gaps[[col_ts]].assign(gap_min=deltas[gaps.index])

def filtrar_outliers(df, col_temp, min_ok, max_ok):
    mask = (df[col_temp] >= min_ok) & (df[col_temp] <= max_ok)
    return df[mask].copy(), df[~mask].copy()
