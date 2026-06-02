import React from "react";
import { createRoot } from "react-dom/client";
import { Activity, CalendarDays, Download, FileText, RefreshCw, Thermometer, Droplets, Clock3 } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

type Summary = {
  device_code: string;
  start: string | null;
  end: string | null;
  records: number;
  temp_avg_c: number | null;
  temp_min_c: number | null;
  temp_max_c: number | null;
  hum_avg_pct: number | null;
  threshold_c: number;
  minutes_over_threshold: number;
  hot_window: {
    start: string;
    end: string;
    average_temp_c: number;
  } | null;
  intervals_over_threshold: Array<{
    start: string;
    end: string;
    minutes: number;
  }>;
};

type SeriesPoint = {
  measured_at: string;
  values: Record<string, string>;
};

type SeriesResponse = {
  device_code: string;
  points: SeriesPoint[];
};

type ChartPoint = {
  time: string;
  date: string;
  temperature: number | null;
  overThresholdTemperature: number | null;
  humidity: number | null;
};

const DEVICE_CODE = "home_dht22";
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
const TEMP_UNIT = "°C";

function madridDateTime(value: string | null) {
  if (!value) return "Sin datos";
  return new Intl.DateTimeFormat("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/Madrid",
  }).format(new Date(value));
}

function madridTime(value: string) {
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Madrid",
  }).format(new Date(value));
}

function toDateInputValue(date: Date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Madrid",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function startOfMadridDayIso(dateValue: string) {
  return `${dateValue}T00:00:00+02:00`;
}

function endOfMadridDayIso(dateValue: string) {
  return `${dateValue}T23:59:59+02:00`;
}

function formatDuration(totalMinutes: number | null | undefined) {
  const safeMinutes = totalMinutes ?? 0;
  const hours = Math.floor(safeMinutes / 60);
  const minutes = safeMinutes % 60;
  if (hours && minutes) return `${hours} h ${minutes} min`;
  if (hours) return `${hours} h`;
  return `${minutes} min`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [summary, setSummary] = React.useState<Summary | null>(null);
  const [series, setSeries] = React.useState<SeriesResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [threshold, setThreshold] = React.useState(30);
  const [startDate, setStartDate] = React.useState(() => toDateInputValue(new Date()));
  const [endDate, setEndDate] = React.useState(() => toDateInputValue(new Date()));

  const rangeQuery = React.useMemo(() => {
    const params = new URLSearchParams({
      start: startOfMadridDayIso(startDate),
      end: endOfMadridDayIso(endDate),
    });
    return params.toString();
  }, [startDate, endDate]);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, seriesData] = await Promise.all([
        fetchJson<Summary>(`/devices/${DEVICE_CODE}/summary?${rangeQuery}&threshold_c=${threshold}&hot_window_hours=2`),
        fetchJson<SeriesResponse>(`/devices/${DEVICE_CODE}/series?${rangeQuery}&limit=5000`),
      ]);
      setSummary(summaryData);
      setSeries(seriesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error cargando datos");
    } finally {
      setLoading(false);
    }
  }, [rangeQuery, threshold]);

  React.useEffect(() => {
    void loadData();
  }, [loadData]);

  const chartData = React.useMemo<ChartPoint[]>(() => {
    return (series?.points ?? []).map((point) => ({
      time: madridTime(point.measured_at),
      date: madridDateTime(point.measured_at),
      temperature: point.values.temperature_dht22 ? Number(point.values.temperature_dht22) : null,
      overThresholdTemperature:
        point.values.temperature_dht22 && Number(point.values.temperature_dht22) >= threshold
          ? Number(point.values.temperature_dht22)
          : null,
      humidity: point.values.humidity_dht22 ? Number(point.values.humidity_dht22) : null,
    }));
  }, [series, threshold]);

  const latest = React.useMemo(() => [...chartData].slice(-8).reverse(), [chartData]);

  const reportUrl = `${API_BASE}/devices/${DEVICE_CODE}/report.pdf?${rangeQuery}&threshold_c=${threshold}&hot_window_hours=2`;

  function applyPreset(days: number | "all") {
    if (days === "all") {
      setStartDate("2020-01-01");
      setEndDate(toDateInputValue(new Date()));
      return;
    }
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (days - 1));
    setStartDate(toDateInputValue(start));
    setEndDate(toDateInputValue(end));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>PRL-Tech</h1>
          <p>{DEVICE_CODE} · Europe/Madrid</p>
        </div>
        <div className="actions">
          <label className="threshold-control">
            Umbral
            <input
              type="number"
              min="0"
              max="60"
              step="0.5"
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
            />
          </label>
          <button type="button" onClick={loadData} disabled={loading} title="Actualizar datos">
            <RefreshCw size={18} />
            Actualizar
          </button>
          <a className="button-link" href={reportUrl} title="Descargar informe PDF">
            <Download size={18} />
            PDF
          </a>
        </div>
      </header>

      {error ? <div className="alert">No se pudieron cargar los datos: {error}</div> : null}

      <section className="filters-panel">
        <div className="filter-title">
          <CalendarDays size={18} />
          Rango de consulta
        </div>
        <label>
          Desde
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
        <div className="preset-actions">
          <button type="button" className="secondary" onClick={() => applyPreset(1)}>
            Hoy
          </button>
          <button type="button" className="secondary" onClick={() => applyPreset(7)}>
            7 dias
          </button>
          <button type="button" className="secondary" onClick={() => applyPreset(30)}>
            30 dias
          </button>
          <button type="button" className="secondary" onClick={() => applyPreset("all")}>
            Todo
          </button>
        </div>
      </section>

      <section className="metric-grid">
        <Metric icon={<Thermometer />} label="Temperatura media" value={formatMetric(summary?.temp_avg_c, TEMP_UNIT)} />
        <Metric icon={<Activity />} label="Max / Min" value={`${formatNumber(summary?.temp_max_c)} / ${formatNumber(summary?.temp_min_c)} ${TEMP_UNIT}`} />
        <Metric icon={<Droplets />} label="Humedad media" value={formatMetric(summary?.hum_avg_pct, "%")} />
        <Metric icon={<Clock3 />} label="Sobre umbral" value={formatDuration(summary?.minutes_over_threshold)} />
      </section>

      <section className="content-grid">
        <div className="panel chart-panel">
          <div className="panel-header">
            <div>
              <h2>Lecturas del periodo</h2>
              <p>{summary ? `${madridDateTime(summary.start)} - ${madridDateTime(summary.end)}` : "Cargando"}</p>
            </div>
          </div>
          {chartData.length > 0 ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" minTickGap={36} />
                  <YAxis yAxisId="temp" width={42} />
                  <YAxis yAxisId="hum" orientation="right" width={42} />
                  <Tooltip />
                  <ReferenceLine
                    yAxisId="temp"
                    y={threshold}
                    stroke="#c92a2a"
                    strokeDasharray="5 5"
                    label={{ value: `Umbral ${threshold} ${TEMP_UNIT}`, position: "insideTopLeft", fill: "#c92a2a" }}
                  />
                  <Line yAxisId="temp" type="monotone" dataKey="temperature" name="Temperatura" stroke="#d9480f" dot={false} strokeWidth={2} />
                  <Line
                    yAxisId="temp"
                    type="monotone"
                    dataKey="overThresholdTemperature"
                    name="Sobre umbral"
                    stroke="#c92a2a"
                    dot={false}
                    strokeWidth={4}
                    connectNulls={false}
                  />
                  <Line yAxisId="hum" type="monotone" dataKey="humidity" name="Humedad" stroke="#1971c2" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">No hay lecturas en el rango seleccionado.</div>
          )}
        </div>

        <aside className="panel">
          <div className="panel-header compact">
            <h2>Ultimas lecturas</h2>
          </div>
          <table className="readings-table">
            <thead>
              <tr>
                <th>Hora</th>
                <th>Temp.</th>
                <th>Hum.</th>
              </tr>
            </thead>
            <tbody>
              {latest.map((point) => (
                <tr
                  className={point.temperature !== null && point.temperature >= threshold ? "over-threshold-row" : ""}
                  key={`${point.date}-${point.temperature}-${point.humidity}`}
                >
                  <td>{point.date}</td>
                  <td>{formatNumber(point.temperature)}</td>
                  <td>{formatNumber(point.humidity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </aside>
      </section>

      <section className="report-preview panel">
        <div className="panel-header">
          <div>
            <h2>
              <FileText size={19} />
              Vista previa del informe
            </h2>
            <p>Resumen calculado con el rango y umbral seleccionados.</p>
          </div>
          <a className="button-link" href={reportUrl} title="Descargar informe PDF">
            <Download size={18} />
            Descargar PDF
          </a>
        </div>

        <div className="report-grid">
          <PreviewItem label="Periodo" value={summary ? `${madridDateTime(summary.start)} - ${madridDateTime(summary.end)}` : "Sin datos"} />
          <PreviewItem label="Umbral aplicado" value={`${threshold} ${TEMP_UNIT}`} />
          <PreviewItem label="Registros" value={`${summary?.records ?? 0}`} />
          <PreviewItem label="Tiempo total sobre umbral" value={formatDuration(summary?.minutes_over_threshold)} />
          <PreviewItem
            label="Franja mas calurosa"
            value={
              summary?.hot_window
                ? `${madridDateTime(summary.hot_window.start)} - ${madridDateTime(summary.hot_window.end)} (${formatMetric(summary.hot_window.average_temp_c, TEMP_UNIT)})`
                : "No disponible"
            }
          />
          <PreviewItem label="Temperatura media" value={formatMetric(summary?.temp_avg_c, TEMP_UNIT)} />
          <PreviewItem label="Temperatura maxima" value={formatMetric(summary?.temp_max_c, TEMP_UNIT)} />
          <PreviewItem label="Temperatura minima" value={formatMetric(summary?.temp_min_c, TEMP_UNIT)} />
          <PreviewItem label="Humedad media" value={formatMetric(summary?.hum_avg_pct, "%")} />
        </div>

        <div className="interval-preview">
          <h3>Tramos sobre umbral</h3>
          {summary?.intervals_over_threshold?.length ? (
            <ul>
              {summary.intervals_over_threshold.slice(0, 8).map((interval) => (
                <li key={`${interval.start}-${interval.end}`}>
                  <span>{madridDateTime(interval.start)} - {madridDateTime(interval.end)}</span>
                  <strong>{formatDuration(interval.minutes)}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>No hay tramos sobre el umbral en el rango seleccionado.</p>
          )}
        </div>
      </section>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="metric">
      <div className="metric-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PreviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="preview-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(value);
}

function formatMetric(value: number | null | undefined, unit: string) {
  return `${formatNumber(value)} ${unit}`;
}

createRoot(document.getElementById("root")!).render(<App />);
