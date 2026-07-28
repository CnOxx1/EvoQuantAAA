import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { zh } from "../i18n/zh";
import styles from "./ChartPanel.module.css";

export type ChartPoint = { time: number; value: number; color?: string };

export type CandlePoint = {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type LinePoint = { time: string | number; value: number };

export type OverlayLine = {
  id: string;
  color: string;
  data: LinePoint[];
  lineWidth?: number;
};

export type SubSeries = {
  id: string;
  color: string;
  data: LinePoint[];
  style?: "line" | "hist";
};

export type SubPane =
  | { kind: "none" }
  | { kind: "multi"; series: SubSeries[] };

export type ChartMode = "histogram" | "candle";

export type IndChip = {
  id: string;
  label: string;
  active?: boolean;
  disabled?: boolean;
};

export function ChartPanel({
  title,
  subtitle,
  mode = "histogram",
  data = [],
  candles = [],
  overlays = [],
  subPane = { kind: "none" },
  height = 420,
  emptyHint = zh.hintClick,
  indicators,
  onToggleIndicator,
}: {
  title: string;
  subtitle?: string;
  mode?: ChartMode;
  data?: ChartPoint[];
  candles?: CandlePoint[];
  overlays?: OverlayLine[];
  subPane?: SubPane;
  height?: number;
  emptyHint?: string;
  indicators?: IndChip[];
  onToggleIndicator?: (id: string) => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const show =
    mode === "candle" ? candles.length > 0 : data.length > 0;
  const needSub =
    mode === "candle" &&
    subPane.kind === "multi" &&
    subPane.series.some((s) => s.data.length > 0);

  useEffect(() => {
    if (!show || !hostRef.current) return;
    const el = hostRef.current;
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
      timeScale: {
        borderColor: "#e5e6eb",
        timeVisible: mode === "candle",
      },
    });
    chartRef.current = chart;

    if (mode === "candle") {
      const candle = chart.addSeries(CandlestickSeries, {
        upColor: "#f53f3f",
        downColor: "#00b42a",
        borderUpColor: "#f53f3f",
        borderDownColor: "#00b42a",
        wickUpColor: "#f53f3f",
        wickDownColor: "#00b42a",
      });
      candle.setData(
        candles
          .filter(
            (c) =>
              Number.isFinite(c.open) &&
              Number.isFinite(c.high) &&
              Number.isFinite(c.low) &&
              Number.isFinite(c.close),
          )
          .map((c) => ({
            time: c.time as never,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          })),
      );

      for (const ov of overlays) {
        if (!ov.data.length) continue;
        const line = chart.addSeries(LineSeries, {
          color: ov.color,
          lineWidth: (ov.lineWidth || 1) as 1 | 2 | 3 | 4,
          priceLineVisible: false,
          lastValueVisible: false,
          title: ov.id,
        });
        line.setData(
          ov.data
            .filter((d) => Number.isFinite(d.value))
            .map((d) => ({ time: d.time as never, value: d.value })),
        );
      }

      if (needSub && subPane.kind === "multi") {
        chart.addPane();
        for (const s of subPane.series) {
          if (!s.data.length) continue;
          if (s.style === "hist") {
            const hist = chart.addSeries(
              HistogramSeries,
              {
                priceLineVisible: false,
                lastValueVisible: false,
                title: s.id,
              },
              1,
            );
            hist.setData(
              s.data
                .filter((d) => Number.isFinite(d.value))
                .map((d) => ({
                  time: d.time as never,
                  value: d.value,
                  color: d.value >= 0 ? `${s.color}99` : "#00b42a88",
                })),
            );
          } else {
            const line = chart.addSeries(
              LineSeries,
              {
                color: s.color,
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
                title: s.id,
              },
              1,
            );
            line.setData(
              s.data
                .filter((d) => Number.isFinite(d.value))
                .map((d) => ({ time: d.time as never, value: d.value })),
            );
          }
        }
        try {
          const panes = chart.panes();
          if (panes.length > 1) {
            panes[0].setStretchFactor(2.2);
            panes[1].setStretchFactor(1);
          }
        } catch {
          /* ignore */
        }
      }
    } else {
      const series = chart.addSeries(HistogramSeries, {
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(
        data.map((d) => ({
          time: d.time as UTCTimestamp,
          value: d.value,
          ...(d.color ? { color: d.color } : {}),
        })),
      );
    }

    chart.timeScale().fitContent();
    const ro = new ResizeObserver(() => {
      if (hostRef.current) {
        chart.applyOptions({ width: hostRef.current.clientWidth });
      }
    });
    ro.observe(el);
    chart.applyOptions({ width: el.clientWidth });
    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [show, height, mode, candles, data, overlays, subPane, needSub]);

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <div>
          <div className={styles.title}>{title}</div>
          {subtitle ? <div className={styles.sub}>{subtitle}</div> : null}
        </div>
        {indicators && indicators.length > 0 ? (
          <div className={styles.inds}>
            {indicators.map((ind) => (
              <button
                key={ind.id}
                type="button"
                disabled={ind.disabled}
                className={`${styles.ind} ${ind.active ? styles.indOn : ""}`}
                title={ind.disabled ? zh.comingSoon : ind.label}
                onClick={() => onToggleIndicator?.(ind.id)}
              >
                {ind.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {show ? (
        <div ref={hostRef} style={{ height }} />
      ) : (
        <div className={styles.empty} style={{ height }}>
          {emptyHint}
        </div>
      )}
    </div>
  );
}
