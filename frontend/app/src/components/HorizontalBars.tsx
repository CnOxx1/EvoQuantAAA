import { Spin } from "@arco-design/web-react";
import styles from "./ChartPanel.module.css";

export type HBar = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

/** Horizontal bar ranking chart. */
export function HorizontalBars({
  title,
  subtitle,
  items,
  height = 280,
  emptyHint = "暂无排名数据",
  formatValue = (v: number) => v.toFixed(2),
  maxItems = 15,
  loading = false,
}: {
  title: string;
  subtitle?: string;
  items: HBar[];
  height?: number;
  emptyHint?: string;
  formatValue?: (v: number) => string;
  maxItems?: number;
  loading?: boolean;
}) {
  const rows = [...items]
    .filter((i) => Number.isFinite(i.value))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, maxItems);
  const max = Math.max(0.0001, ...rows.map((r) => Math.abs(r.value)));
  const rowH = 22;
  const plotH = Math.max(rows.length * rowH + 8, 80);

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
      ) : !rows.length ? (
        <div className={styles.empty} style={{ height }}>
          {emptyHint}
        </div>
      ) : (
        <div style={{ padding: "8px 12px", maxHeight: height, overflow: "auto" }}>
          <svg
            width="100%"
            height={plotH}
            viewBox={`0 0 400 ${plotH}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label={title}
          >
            {rows.map((r, i) => {
              const y = i * rowH + 2;
              const w = (Math.abs(r.value) / max) * 220;
              const color =
                r.color ||
                (r.value >= 0 ? "#165dff" : "#f53f3f");
              return (
                <g key={r.id}>
                  <text
                    x={0}
                    y={y + 14}
                    fontSize={11}
                    fill="#4e5969"
                    fontFamily="IBM Plex Mono, ui-monospace, monospace"
                  >
                    {r.label.length > 10 ? `${r.label.slice(0, 10)}…` : r.label}
                  </text>
                  <rect
                    x={100}
                    y={y + 4}
                    width={w}
                    height={12}
                    rx={2}
                    fill={color}
                  />
                  <text
                    x={110 + w}
                    y={y + 14}
                    fontSize={10}
                    fill="#86909c"
                    fontFamily="IBM Plex Mono, ui-monospace, monospace"
                  >
                    {formatValue(r.value)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
    </div>
  );
}
