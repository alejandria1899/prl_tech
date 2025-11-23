from pathlib import Path
import yaml
import pandas as pd

# ReportLab (PDF)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm

from analyzer.charts import grafica_temp, grafica_hum
from analyzer.io_thingspeak import cargar_desde_thingspeak


# --------------------------
# Utilidades de análisis
# --------------------------
def franja_mas_caliente(df, col_ts, col_temp, ventana_horas=2):
    ds = df.set_index(col_ts).sort_index()
    roll = ds[col_temp].rolling(f"{ventana_horas}H").mean()
    idxmax = roll.idxmax()
    if pd.isna(idxmax):
        return None
    t_fin = idxmax
    t_ini = t_fin - pd.Timedelta(hours=ventana_horas)
    return {"inicio": t_ini, "fin": t_fin, "temp_media_franja": round(float(roll.loc[idxmax]), 1)}


def intervalos_sobre_umbral(df, col_ts, col_temp, umbral):
    df = df.sort_values(col_ts).reset_index(drop=True).copy()
    s = (df[col_temp] >= float(umbral))  # incluye 30.0 exactos

    starts = df.loc[s & ~s.shift(fill_value=False), col_ts].reset_index(drop=True)
    ends = df.loc[~s & s.shift(fill_value=False), col_ts].reset_index(drop=True)
    if len(ends) < len(starts):
        ends = pd.concat([ends, pd.Series([df[col_ts].iloc[-1]])], ignore_index=True)

    return list(zip(starts.tolist(), ends.tolist()))


def resumen_basico(df, col_temp, col_hum):
    res = {
        "n": int(len(df)),
        "temp_media": round(float(df[col_temp].mean()), 1) if len(df) else None,
        "temp_max": round(float(df[col_temp].max()), 1) if len(df) else None,
        "temp_min": round(float(df[col_temp].min()), 1) if len(df) else None,
    }
    if col_hum in df.columns and df[col_hum].notna().any():
        res["hum_media"] = round(float(df[col_hum].mean()), 1)
    else:
        res["hum_media"] = None
    return res


# --------------------------
# Generación de PDF
# --------------------------
def generar_pdf_semana(cfg, df):
    salida_pdf_dir = Path(cfg["salida_informes"])
    salida_png_dir = Path(cfg["salida_graficos"])
    salida_pdf_dir.mkdir(parents=True, exist_ok=True)
    salida_png_dir.mkdir(parents=True, exist_ok=True)

    nota_legal = Path(cfg["nota_legal_path"]).read_text(encoding="utf-8")

    pdf_path = salida_pdf_dir / "informe_semana.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    # Portada
    story.append(Paragraph(cfg.get("titulo_informe", "Informe PRL-Tech"), styles["Title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(cfg.get("nombre_cliente", ""), styles["Heading2"]))
    story.append(Spacer(1, 10 * mm))

    col_ts, col_temp, col_hum = cfg["col_timestamp"], cfg["col_temp"], cfg["col_hum"]
    df["fecha"] = df[col_ts].dt.date
    umbral = float(cfg["umbral_alerta_temp"])
    intervalo_min = float(cfg["intervalo_min"])
    ventana_horas = int(cfg["franja_resumen_horas"])

    fechas_ordenadas = sorted(df["fecha"].unique())
    for idx, fecha in enumerate(fechas_ordenadas):
        df_dia = df[df["fecha"] == fecha].copy()

        # Métricas del día
        resumen = resumen_basico(df_dia, col_temp, col_hum)
        franja = franja_mas_caliente(df_dia, col_ts, col_temp, ventana_horas)
        tramos = intervalos_sobre_umbral(df_dia, col_ts, col_temp, umbral)

        # Tabla resumen
        tabla_data = [
            ["Día", str(fecha)],
            ["Registros", resumen["n"]],
            ["Temp. media (°C)", resumen["temp_media"]],
            ["Temp. máx (°C)", resumen["temp_max"]],
            ["Temp. mín (°C)", resumen["temp_min"]],
        ]
        if resumen["hum_media"] is not None:
            tabla_data.append(["Humedad media (%)", resumen["hum_media"]])

        if franja:
            tabla_data.append([
                f"Franja más calurosa ({ventana_horas} h)",
                f"{franja['inicio'].strftime('%H:%M')} → {franja['fin'].strftime('%H:%M')} "
                f"({franja['temp_media_franja']} °C)",
            ])
        else:
            tabla_data.append([f"Franja más calurosa ({ventana_horas} h)", "No disponible"])

        # Tramos ≥ umbral
        if tramos:
            minutos_sobre = sum(int((fin - ini).total_seconds() / 60) for ini, fin in tramos)
            minutos_totales = len(df_dia) * intervalo_min
            porcentaje = round(100 * minutos_sobre / minutos_totales, 1) if minutos_totales else 0.0
            tramos_texto = ", ".join(f"{ini.strftime('%H:%M')}–{fin.strftime('%H:%M')}" for ini, fin in tramos)
            tabla_data.append([f"Tramos ≥ {umbral} °C", tramos_texto])
            tabla_data.append(["% del día ≥ umbral", f"{porcentaje}%"])
        else:
            tabla_data.append([f"Tramos ≥ {umbral} °C", "Ninguno"])

        tabla = Table(tabla_data, hAlign="LEFT", colWidths=[60 * mm, 105 * mm])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))

        # Gráficos
        png_temp = Path(cfg["salida_graficos"]) / f"dia_{fecha}_temp.png"
        grafica_temp(df_dia, col_ts, col_temp, png_temp, f"{fecha} – Temperatura", umbral=umbral)
        img_temp = Image(str(png_temp)); img_temp._restrictSize(170 * mm, 120 * mm)

        img_hum = None
        png_hum = Path(cfg["salida_graficos"]) / f"dia_{fecha}_hum.png"
        result = grafica_hum(df_dia, col_ts, col_hum, png_hum, f"{fecha} – Humedad")
        if result:
            img_hum = Image(str(png_hum)); img_hum._restrictSize(170 * mm, 120 * mm)

        story.append(Paragraph(f"Día {fecha}", styles["Heading2"]))
        story.append(Spacer(1, 4 * mm))
        story.append(tabla)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Gráfico de temperatura", styles["Heading3"]))
        story.append(img_temp)

        if img_hum is not None:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Gráfico de humedad", styles["Heading3"]))
            story.append(img_hum)

        if idx < len(fechas_ordenadas) - 1:
            story.append(PageBreak())

    # Nota legal
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("<b>Nota:</b>", styles["Heading3"]))
    for linea in nota_legal.splitlines():
        story.append(Paragraph(linea, styles["Normal"]))

    doc.build(story)
    return pdf_path


# --------------------------
# MAIN
# --------------------------
if __name__ == "__main__":
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ts_cfg = cfg["thingspeak"]
    df = cargar_desde_thingspeak(
        channel_id=int(ts_cfg["channel_id"]),
        read_api_key=ts_cfg["read_api_key"],
        field_temp=int(ts_cfg.get("field_temp", 1)),
        field_hum=int(ts_cfg.get("field_hum", 2)),
        results=int(ts_cfg.get("results", 10000)),
    )

    if df.empty:
        raise SystemExit("ThingSpeak no devolvió datos. Revisa channel_id / API key.")

    pdf_path = generar_pdf_semana(cfg, df)
    print(f"✅ PDF generado: {pdf_path}")
