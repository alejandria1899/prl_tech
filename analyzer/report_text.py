from datetime import datetime

def conclusions_text(resumen, franja, minutos_sobre, intervalo_min, nota_legal):
    lineas = []
    lineas.append("INFORME ORIENTATIVO – Temperatura/Humedad\n")
    lineas.append(f"Registros: {resumen['n']}")
    lineas.append(f"Temperatura media: {resumen['temp_media']} °C")
    lineas.append(f"Máxima: {resumen['temp_max']} °C | Mínima: {resumen['temp_min']} °C")
    if resumen.get("hum_media") is not None:
        lineas.append(f"Humedad media: {resumen['hum_media']} %")

    if franja:
        lineas.append(f"Franja más calurosa ({franja['inicio']} → {franja['fin']}): "
                      f"{franja['temp_media_franja']} °C")

    minutos_totales = resumen['n'] * intervalo_min
    lineas.append(f"Minutos sobre umbral: {minutos_sobre} / {minutos_totales}")
    lineas.append("\n---\n" + nota_legal.strip())
    return "\n".join(lineas)
