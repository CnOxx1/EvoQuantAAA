import { useEffect, useRef } from "react";
import { Spin } from "@arco-design/web-react";
import {
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
} from "lightweight-charts";
import styles from "./ChartPanel.module.css";

export type TsPoint = { time: string | number; value: number };

export type TsLine = {
  id: string;
  color: string;
  data: TsPoint[];
  lineWidth?: number;
};

export type TsHist = {
  id: string;
  data: Array<TsPoint & { color?: string }>;
};

type SeriesBag = ISeriesApi<"Line"> | ISeriesApi<"Histogram">;

function toLineData(data: TsPoint[]) {
  return data
    .filter((d) => Number.isFinite(d.value))
    .map((d) => ({ time: d.time as never, value: d.value }));
}

function toHistData(data: Array<TsPoint & { color?: string }>) {
  return data
    .filter((d) => Number.isFinite(d.value))
    .map((d) => ({
      time: d.time as never,
      value: d.value,
      ...(d.color ? { color: d.color } : {}),
    }));
}

/** Multi-line (and optional histogram) time-series chart. */
export function TimeSeriesChart({
  title,
  subtitle,
  lines = [],
  hist,
  height = 280,
  emptyHint = "暂无序列数据",
  loading = false,
}: {
  title: string;
  subtitle?: string;
  lines?: TsLine[];
  hist?: TsHist;
  height?: number;
  emptyHint?: string;
  loading?: boolean;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Map<string, SeriesBag>>(new Map());

  const hasLines = lines.some((l) => l.data.length > 0);
  const hasHist = Boolean(hist?.data.length);
  const show = !loading && (hasLines || hasHist);
  const legendLines = lines.filter((l) => l.data.length > 0);

  useEffect(() => {
    if (!show || !hostRef.current) return;
    const el = hostRef.current;
    if (!chartRef.current) {
      const chart = createChart(el, {
        height,
        layout: {
          background: { type: ColorType.Solid, color: "#ffffff" },
          textColor: "#86909c",
          fontFamily: "IBM Plex Mono, ui-monospace, monospace",
          fontSize: 11,
          attributionLogo: false,
        },
        grid: {
          vertLines: { color: "#f2f3f5" },
          horzLines: { color: "#f2f3f5" },
        },
        rightPriceScale: { borderColor: "#e5e6eb" },
        timeScale: { borderColor: "#e5e6eb" },
      });
      chartRef.current = chart;
      const ro = new ResizeObserver(() => {
        if (hostRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: hostRef.current.clientWidth });
        }
      });
      ro.observe(el);
      chart.applyOptions({ width: el.clientWidth });
      (el as HTMLDivElement & { __ro?: ResizeObserver }).__ro = ro;
    } else {
      chartRef.current.applyOptions({ height });
    }

    const chart = chartRef.current;
    const series = seriesRef.current;
    const keep = new Set<string>();

    if (hasHist && hist) {
      const key = `hist:${hist.id}`;
      keep.add(key);
      let s = series.get(key);
      if (!s) {
        s = chart.addSeries(HistogramSeries, {
          priceLineVisible: false,
          lastValueVisible: false,
          title: hist.id,
        });
        series.set(key, s);
      }
      s.setData(toHistData(hist.data) as never);
    }

    for (const line of lines) {
      if (!line.data.length) continue;
      const key = `line:${line.id}`;
      keep.add(key);
      let s = series.get(key);
      if (!s) {
        s = chart.addSeries(LineSeries, {
          color: line.color,
          lineWidth: (line.lineWidth || 2) as 1 | 2 | 3 | 4,
          priceLineVisible: false,
          lastValueVisible: true,
          title: line.id,
        });
        series.set(key, s);
      } else {
        s.applyOptions({
          color: line.color,
          lineWidth: (line.lineWidth || 2) as 1 | 2 | 3 | 4,
        });
      }
      s.setData(toLineData(line.data) as never);
    }

    for (const [key, s] of [...series.entries()]) {
      if (!keep.has(key)) {
        chart.removeSeries(s);
        series.delete(key);
      }
    }

    chart.timeScale().fitContent();
  }, [show, height, lines, hist, hasLines, hasHist]);

  useEffect(() => {
    return () => {
      const el = hostRef.current as
        | (HTMLDivElement & { __ro?: ResizeObserver })
        | null;
      el?.__ro?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (!show) {
      const el = hostRef.current as
        | (HTMLDivElement & { __ro?: ResizeObserver })
        | null;
      el?.__ro?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current.clear();
    }
  }, [show]);

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <div>
          <div className={styles.title}>{title}</div>
          {subtitle ? <div className={styles.sub}>{subtitle}</div> : null}
        </div>
      </div>
      {loading ? (
        <div className={styles.loading} style={{ height }}>
          <Spin tip="加载中…" />
        </div>
      ) : show ? (
        <>
          {legendLines.length > 1 ? (
            <div className={styles.legend}>
              {legendLines.map((l) => (
                <span key={l.id} className={styles.legendItem}>
                  <span
                    className={styles.legendSwatch}
                    style={{ background: l.color }}
                  />
                  {l.id}
                </span>
              ))}
            </div>
          ) : null}
          <div ref={hostRef} style={{ height }} />
        </>
      ) : (
        <div className={styles.empty} style={{ height }}>
          {emptyHint}
        </div>
      )}
    </div>
  );
}
