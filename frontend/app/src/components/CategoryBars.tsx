import { Spin } from "@arco-design/web-react";
import styles from "./ChartPanel.module.css";

export type BarItem = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

/** Simple categorical bar chart (SVG) — no extra deps. */
export function CategoryBars({
  title,
  subtitle,
  items,
  height = 220,
  emptyHint = "暂无分类数据",
  formatValue = (v: number) => String(v),
  loading = false,
}: {
  title: string;
  subtitle?: string;
  items: BarItem[];
  height?: number;
  emptyHint?: string;
  formatValue?: (v: number) => string;
  loading?: boolean;
}) {
  const max = Math.max(0, ...items.map((i) => Math.abs(i.value)));
  const plotH = Math.max(120, height - 36);
  const padL = 8;
  const padR = 8;
  const padT = 12;
  const padB = 28;
  const w = Math.max(320, items.length * 48);
  const innerW = w - padL - padR;
  const innerH = plotH - padT - padB;
  const gap = 0.28;
  const bw = items.length ? (innerW / items.length) * (1 - gap) : 0;
  const step = items.length ? innerW / items.length : 0;

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <div>
          <div className={styles.title}>{title}</div>
          {subtitle ? <div className={styles.sub}>{subtitle}</div> : null}
        </div>
      </div>
      {loading ? (
        <div className={styles.loading} style={{ height: plotH }}>
          <Spin tip="加载中…" />
        </div>
      ) : !items.length ? (
        <div className={styles.empty} style={{ height: plotH }}>
          {emptyHint}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <svg
            width="100%"
            height={plotH}
            viewBox={`0 0 ${w} ${plotH}`}
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label={title}
          >
            <line
              x1={padL}
              x2={w - padR}
              y1={padT + innerH}
              y2={padT + innerH}
              stroke="#e5e6eb"
            />
            {items.map((it, i) => {
              const x = padL + i * step + (step - bw) / 2;
              const h =
                max > 0 ? (Math.abs(it.value) / max) * (innerH - 4) : 0;
              const y = padT + innerH - h;
              const color = it.color || "rgb(var(--primary-6))";
              return (
                <g key={it.id}>
                  <rect
                    x={x}
                    y={y}
                    width={bw}
                    height={h}
                    fill={color}
                    rx={2}
                  />
                  <text
                    x={x + bw / 2}
                    y={padT + innerH + 14}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#86909c"
                    fontFamily="IBM Plex Mono, ui-monospace, monospace"
                  >
                    {it.label}
                  </text>
                  <text
                    x={x + bw / 2}
                    y={y - 4}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#4e5969"
                    fontFamily="IBM Plex Mono, ui-monospace, monospace"
                  >
                    {formatValue(it.value)}
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
