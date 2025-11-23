# analyzer/charts.py
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.dates as mdates


def grafica_temp(df, col_ts, col_temp, out_png, titulo, umbral=None):
    """
    Gráfico SOLO de temperatura.
    - Línea roja de la temperatura.
    - Línea horizontal del umbral (si se indica).
    - Zona superior al umbral coloreada.
    - Eje X con solo las horas (HH:MM).
    """
    x = df[col_ts]
    y = df[col_temp]

    plt.figure()
    plt.plot(x, y, label="Temperatura (°C)", color="red")

    # Línea del umbral
    if umbral is not None:
        plt.axhline(umbral, linestyle="--", linewidth=1.2, color="orange", label=f"Umbral {umbral} °C")
        y2 = np.array(y, dtype=float)
        plt.fill_between(x, y2, umbral, where=y2 >= umbral, alpha=0.25, color="red")

    # --- Formato del eje X: solo hora ---
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45)

    plt.title(titulo)
    plt.xlabel("Hora del día")
    plt.ylabel("Temperatura (°C)")
    plt.tight_layout()
    plt.legend()
    plt.savefig(out_png)
    plt.close()


def grafica_hum(df, col_ts, col_hum, out_png, titulo):
    """
    Gráfico SOLO de humedad.
    - Eje X con solo las horas (HH:MM).
    """
    if col_hum not in df.columns or not df[col_hum].notna().any():
        return None

    x = df[col_ts]
    y = df[col_hum]

    plt.figure()
    plt.plot(x, y, label="Humedad (%)", color="blue")

    # --- Formato del eje X: solo hora ---
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45)

    plt.title(titulo)
    plt.xlabel("Hora del día")
    plt.ylabel("Humedad (%)")
    plt.tight_layout()
    plt.legend()
    plt.savefig(out_png)
    plt.close()
    return out_png
