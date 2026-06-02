from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from backend.app.models import Device
from backend.app.services.analytics import HUMIDITY_SENSOR, TEMPERATURE_SENSOR, get_series, get_summary


MADRID = ZoneInfo("Europe/Madrid")
REPORT_DIR = Path("outputs/informes")
CHART_DIR = Path("outputs/graficos")
TEMP_UNIT = "°C"


def generate_device_report_pdf(
    db: Session,
    *,
    device: Device,
    start: datetime | None,
    end: datetime | None,
    threshold_c: float,
    hot_window_hours: int,
    limit: int,
) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    series = get_series(db, device=device, start=start, end=end, limit=limit)
    summary = get_summary(
        db,
        device=device,
        start=start,
        end=end,
        limit=limit,
        threshold_c=threshold_c,
        hot_window_hours=hot_window_hours,
    )

    stamp = datetime.now(MADRID).strftime("%Y%m%d_%H%M%S")
    pdf_path = REPORT_DIR / f"informe_{device.code}_{stamp}.pdf"
    temp_chart = CHART_DIR / f"{device.code}_{stamp}_temperatura.png"
    hum_chart = CHART_DIR / f"{device.code}_{stamp}_humedad.png"

    _plot_sensor(series, TEMPERATURE_SENSOR, "Temperatura", TEMP_UNIT, temp_chart, threshold_c)
    has_humidity = _plot_sensor(series, HUMIDITY_SENSOR, "Humedad", "percent", hum_chart, None)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Informe termico orientativo - PRL-Tech", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(device.name, styles["Heading2"]),
        Paragraph(f"Dispositivo: {device.code}", styles["Normal"]),
        Paragraph(f"Ubicacion: {device.location or 'No indicada'}", styles["Normal"]),
        Paragraph("Zona horaria mostrada: Europe/Madrid", styles["Normal"]),
        Spacer(1, 7 * mm),
    ]

    story.append(_summary_table(summary, styles))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("Grafico de temperatura", styles["Heading3"]))
    story.append(_report_image(temp_chart))

    if has_humidity:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Grafico de humedad", styles["Heading3"]))
        story.append(_report_image(hum_chart))

    doc.build(story)
    return pdf_path


def _summary_table(summary: dict, styles) -> Table:
    hot_window = summary["hot_window"]
    rows = [
        ["Inicio", _format_dt(summary["start"])],
        ["Fin", _format_dt(summary["end"])],
        ["Registros temperatura", summary["records"]],
        [f"Temp. media ({TEMP_UNIT})", summary["temp_avg_c"]],
        [f"Temp. maxima ({TEMP_UNIT})", summary["temp_max_c"]],
        [f"Temp. minima ({TEMP_UNIT})", summary["temp_min_c"]],
        ["Humedad media (%)", summary["hum_avg_pct"]],
        [f"Umbral ({TEMP_UNIT})", summary["threshold_c"]],
        ["Tiempo total sobre umbral", _format_duration(summary["minutes_over_threshold"])],
        [
            "Franja mas calurosa",
            (
                f"{_format_dt(hot_window['start'])} - {_format_dt(hot_window['end'])} "
                f"({hot_window['average_temp_c']} {TEMP_UNIT})"
                if hot_window
                else "No disponible"
            ),
        ],
    ]
    table = Table(rows, hAlign="LEFT", colWidths=[60 * mm, 105 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return table


def _plot_sensor(
    series: list[dict],
    sensor_code: str,
    title: str,
    unit: str,
    out_path: Path,
    threshold_c: float | None,
) -> bool:
    points = [
        (point["measured_at"].astimezone(MADRID), float(point["values"][sensor_code]))
        for point in series
        if sensor_code in point["values"]
    ]
    if not points:
        return False

    x = [item[0] for item in points]
    y = [item[1] for item in points]

    plt.figure(figsize=(8.8, 4.2))
    plt.plot(x, y, label=title)
    if threshold_c is not None:
        plt.axhline(threshold_c, linestyle="--", linewidth=1.2, color="red", label=f"Umbral {threshold_c} {TEMP_UNIT}")
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M", tz=MADRID))
    plt.xticks(rotation=35, ha="right")
    plt.title(title)
    plt.xlabel("Fecha y hora")
    plt.ylabel(unit)
    plt.tight_layout()
    plt.legend()
    plt.savefig(out_path, dpi=140)
    plt.close()
    return True


def _report_image(path: Path) -> Image:
    image = Image(str(path))
    image._restrictSize(170 * mm, 105 * mm)
    return image


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "No disponible"
    return value.astimezone(MADRID).strftime("%d/%m/%Y %H:%M")


def _format_duration(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return f"{minutes} min"
