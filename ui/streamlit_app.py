from pathlib import Path
import sys
import streamlit as st
import pandas as pd
import numpy as np
import yaml

# --- AÑADIR RAÍZ DEL PROYECTO AL PATH ---
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Interactivo
import plotly.express as px

# Estático para PDF
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm

# Nuestra función para leer de ThingSpeak
from analyzer.io_thingspeak import cargar_desde_thingspeak


# ---------------------------
# Config página y rutas
# ---------------------------
st.set_page_config(page_title="PRL-Tech – Informes desde ThingSpeak", layout="wide")
st.title("📡 PRL-Tech – Informes desde ThingSpeak")

OUT_DIR = Path("outputs")
OUT_PDF = OUT_DIR / "informes"
OUT_PNG = OUT_DIR / "graficos"
OUT_PDF.mkdir(parents=True, exist_ok=True)
OUT_PNG.mkdir(parents=True, exist_ok=True)

NOTA_LEGAL_PATH = Path("docs/nota_legal_orientativo.txt")
NOTA_LEGAL = NOTA_LEGAL_PATH.read_text(encoding="utf-8") if NOTA_LEGAL_PATH.exists() else ""

CONFIG_PATH = Path("config/settings.yaml")
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CFG = yaml.safe_load(f)
else:
    CFG = {}

# ---------------------------
# Funciones utilitarias
# ---------------------------
def franja_mas_caliente(df: pd.DataFrame, ventana_horas=2):
    if df.empty:
        return None
    ds = df.set_index("timestamp").sort_index()
    roll = ds["temp_c"].rolling(f"{ventana_horas}h").mean()
    idxmax = roll.idxmax()
    if pd.isna(idxmax):
        return None
    t_fin = idxmax
    t_ini = t_fin - pd.Timedelta(hours=ventana_horas)
    return {
        "inicio": t_ini,
        "fin": t_fin,
        "temp_media_franja": round(float(roll.loc[idxmax]), 1),
    }


def intervalos_sobre_umbral(df: pd.DataFrame, umbral: float):
    if df.empty:
        return []
    d = df.sort_values("timestamp").reset_index(drop=True).copy()
    s = d["temp_c"] >= float(umbral)
    starts = d.loc[s & ~s.shift(fill_value=False), "timestamp"].reset_index(drop=True)
    ends = d.loc[~s & s.shift(fill_value=False), "timestamp"].reset_index(drop=True)
    if len(ends) < len(starts):
        ends = pd.concat([ends, pd.Series([d["timestamp"].iloc[-1]])], ignore_index=True)
    return list(zip(starts.tolist(), ends.tolist()))


def grafica_temp_png(df: pd.DataFrame, titulo: str, umbral: float, out_path: Path):
    plt.figure()
    plt.plot(df["timestamp"], df["temp_c"], label="Temperatura (°C)")
    if umbral is not None:
        plt.axhline(umbral, linestyle="--", linewidth=1.2, label=f"Umbral {umbral} °C")
        y2 = df["temp_c"].to_numpy(dtype=float)
        plt.fill_between(df["timestamp"], y2, umbral, where=y2 >= umbral, alpha=0.25)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45)
    plt.title(titulo)
    plt.xlabel("Hora del día")
    plt.ylabel("Temperatura (°C)")
    plt.tight_layout()
    plt.legend()
    plt.savefig(out_path)
    plt.close()


def grafica_hum_png(df: pd.DataFrame, titulo: str, out_path: Path):
    if not df["hum_pct"].notna().any():
        return None
    plt.figure()
    plt.plot(df["timestamp"], df["hum_pct"], label="Humedad (%)")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    plt.xticks(rotation=45)
    plt.title(titulo)
    plt.xlabel("Hora del día")
    plt.ylabel("Humedad (%)")
    plt.tight_layout()
    plt.legend()
    plt.savefig(out_path)
    plt.close()
    return out_path


def resumen_basico(df: pd.DataFrame):
    return {
        "n": int(len(df)),
        "temp_media": round(float(df["temp_c"].mean()), 1) if len(df) else None,
        "temp_max": round(float(df["temp_c"].max()), 1) if len(df) else None,
        "temp_min": round(float(df["temp_c"].min()), 1) if len(df) else None,
        "hum_media": round(float(df["hum_pct"].mean()), 1) if df["hum_pct"].notna().any() else None,
    }


def generar_pdf(df: pd.DataFrame, fecha_ini, fecha_fin, umbral: float, ventana_horas: int, nombre_cliente: str = ""):
    d0 = pd.to_datetime(fecha_ini)
    d1 = pd.to_datetime(fecha_fin)
    df["fecha"] = df["timestamp"].dt.date
    mask = (df["fecha"] >= d0.date()) & (df["fecha"] <= d1.date())
    dsub = df.loc[mask].copy()
    if dsub.empty:
        st.warning("No hay datos en el rango seleccionado.")
        return None

    pdf_name = f"informe_{d0.date()}_a_{d1.date()}.pdf"
    pdf_path = OUT_PDF / pdf_name

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

    story.append(Paragraph("Informe térmico orientativo – PRL-Tech", styles["Title"]))
    if nombre_cliente:
        story.append(Paragraph(nombre_cliente, styles["Heading2"]))
    story.append(Paragraph(f"Rango: {d0.date()} → {d1.date()}", styles["Normal"]))
    story.append(Paragraph(f"Umbral temperatura: {umbral} °C – Ventana franja: {ventana_horas} h", styles["Normal"]))
    story.append(Spacer(1, 10 * mm))

    fechas = sorted(dsub["fecha"].unique())
    for i, f in enumerate(fechas):
        dd = dsub[dsub["fecha"] == f].copy()

        res = resumen_basico(dd)
        franja = franja_mas_caliente(dd, ventana_horas=ventana_horas)
        tramos = intervalos_sobre_umbral(dd, umbral)

        tabla_data = [
            ["Día", str(f)],
            ["Registros", res["n"]],
            ["Temp. media (°C)", res["temp_media"]],
            ["Temp. máx (°C)", res["temp_max"]],
            ["Temp. mín (°C)", res["temp_min"]],
        ]
        if res["hum_media"] is not None:
            tabla_data.append(["Humedad media (%)", res["hum_media"]])

        if franja:
            tabla_data.append([
                "Franja más calurosa",
                f"{franja['inicio'].strftime('%H:%M')} → {franja['fin'].strftime('%H:%M')} "
                f"({franja['temp_media_franja']} °C)",
            ])
        else:
            tabla_data.append(["Franja más calurosa", "No disponible"])

        if tramos:
            mins = sum(int((fin - ini).total_seconds() / 60) for ini, fin in tramos)

            if len(dd) > 1:
                diffs = dd.sort_values("timestamp")["timestamp"].diff().dt.total_seconds().dropna() / 60.0
                if not diffs.empty:
                    step = int(round(diffs.median()))
                else:
                    step = 10
            else:
                step = 10

            total_mins = len(dd) * step
            pct = round(100 * mins / total_mins, 1) if total_mins else 0.0

            tabla_data.append([
                f"Tramos ≥ {umbral} °C",
                ", ".join(f"{ini.strftime('%H:%M')}–{fin.strftime('%H:%M')}" for ini, fin in tramos),
            ])
            tabla_data.append(["% del día ≥ umbral", f"{pct}%"])
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

        png_temp = OUT_PNG / f"{f}_temp.png"
        grafica_temp_png(dd, f"{f} – Temperatura", umbral, png_temp)
        img_temp = Image(str(png_temp)); img_temp._restrictSize(170 * mm, 120 * mm)

        story.append(Paragraph(f"Día {f}", styles["Heading2"]))
        story.append(Spacer(1, 4 * mm))
        story.append(tabla)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Gráfico de temperatura", styles["Heading3"]))
        story.append(img_temp)

        if dd["hum_pct"].notna().any():
            png_hum = OUT_PNG / f"{f}_hum.png"
            grafica_hum_png(dd, f"{f} – Humedad", png_hum)
            img_hum = Image(str(png_hum)); img_hum._restrictSize(170 * mm, 120 * mm)
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Gráfico de humedad", styles["Heading3"]))
            story.append(img_hum)

        if i < len(fechas) - 1:
            story.append(PageBreak())

    if NOTA_LEGAL.strip():
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("<b>Nota:</b>", styles["Heading3"]))
        for linea in NOTA_LEGAL.splitlines():
            story.append(Paragraph(linea, styles["Normal"]))

    doc.build(story)
    return pdf_path


# ---------------------------
# UI – Carga desde ThingSpeak
# ---------------------------
st.sidebar.title("ThingSpeak")

ts_cfg = CFG.get("thingspeak", {})

channel_default = str(ts_cfg.get("channel_id", "")) if ts_cfg.get("channel_id") is not None else ""
api_default = ts_cfg.get("read_api_key") or st.secrets.get("THINGSPEAK_READ_API_KEY", "")


channel_id = st.sidebar.text_input("Channel ID", value=channel_default)
read_api_key = st.sidebar.text_input("Read API Key", value=api_default, type="password")
results = st.sidebar.number_input(
    "Número máximo de registros",
    min_value=100,
    max_value=20000,
    value=int(ts_cfg.get("results", 5000)) if ts_cfg.get("results") else 5000,
    step=100,
)

if "df" not in st.session_state:
    st.session_state.df = None

if st.sidebar.button("📡 Cargar datos desde ThingSpeak"):
    if not channel_id or not read_api_key:
        st.error("Debes indicar Channel ID y Read API Key.")
    else:
        try:
            df = cargar_desde_thingspeak(
                channel_id=int(channel_id),
                read_api_key=read_api_key,
                field_temp=int(ts_cfg.get("field_temp", 1)),
                field_hum=int(ts_cfg.get("field_hum", 2)),
                results=int(results),
            )
        except Exception as e:
            st.error(f"Error consultando ThingSpeak: {e}")
            df = None
        else:
            if df is None or df.empty:
                st.warning("ThingSpeak no ha devuelto datos.")
            else:
                st.session_state.df = df
                st.success(f"Datos cargados: {len(df)} registros.")


df = st.session_state.df

# ---------------------------
# Contenido principal
# ---------------------------
if df is not None and not df.empty:
    df["fecha"] = df["timestamp"].dt.date

    min_day = df["fecha"].min()
    max_day = df["fecha"].max()

    st.subheader("🎚️ Filtros")
    c1, c2 = st.columns(2)
    fecha_ini = c1.date_input("Fecha inicial", value=min_day, min_value=min_day, max_value=max_day)
    fecha_fin = c2.date_input("Fecha final", value=max_day, min_value=min_day, max_value=max_day)

    st.subheader("⚙️ Parámetros")
    umbral = st.number_input("Umbral de temperatura (°C)", value=30.0, step=0.5)
    ventana = st.slider("Franja más calurosa (horas)", min_value=1, max_value=4, value=2)

    st.subheader("👀 Vista previa rápida")
    dia_preview = st.selectbox("Elige un día para previsualizar gráficos", sorted(df["fecha"].unique()))
    dprev = df[df["fecha"] == dia_preview].copy()

    day_start = pd.to_datetime(dia_preview)
    day_end = day_start + pd.Timedelta(hours=23, minutes=59)

    st.subheader(f"🌡️ Temperatura – {dia_preview}")
    fig_temp = px.line(dprev, x="timestamp", y="temp_c", title=f"Temperatura del {dia_preview}")
    fig_temp.add_hline(y=umbral, line_dash="dash", line_color="red", annotation_text=f"Umbral {umbral} °C")
    fig_temp.update_traces(hovertemplate="<b>%{x|%H:%M}</b><br>Temp: %{y:.1f} °C<extra></extra>")
    fig_temp.update_xaxes(tickformat="%H:%M", range=[day_start, day_end], rangeslider_visible=False)
    fig_temp.update_layout(hovermode="x unified")
    st.plotly_chart(fig_temp, use_container_width=True)

    if dprev["hum_pct"].notna().any():
        st.subheader(f"💧 Humedad – {dia_preview}")
        fig_hum = px.line(dprev, x="timestamp", y="hum_pct", title=f"Humedad del {dia_preview}")
        fig_hum.update_traces(hovertemplate="<b>%{x|%H:%M}</b><br>Humedad: %{y:.1f} %<extra></extra>")
        fig_hum.update_xaxes(tickformat="%H:%M", range=[day_start, day_end], rangeslider_visible=False)
        fig_hum.update_layout(hovermode="x unified")
        st.plotly_chart(fig_hum, use_container_width=True)
    else:
        st.info("Este día no tiene datos de humedad.")

    st.subheader("🧾 Generar informe PDF")
    if st.button("Generar informe"):
        if fecha_fin < fecha_ini:
            st.error("La fecha final no puede ser anterior a la inicial.")
        else:
            pdf_path = generar_pdf(df, fecha_ini, fecha_fin, umbral, ventana,
                                   nombre_cliente=CFG.get("nombre_cliente", ""))
            if pdf_path:
                st.success(f"✅ Informe generado: {pdf_path}")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Descargar PDF",
                        data=f.read(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                    )
else:
    st.info("Configura ThingSpeak en la barra lateral y pulsa 'Cargar datos'.")
