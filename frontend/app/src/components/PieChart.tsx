import { Spin } from "@arco-design/web-react";
import styles from "./ChartPanel.module.css";

export type Slice = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

const PALETTE = [
  "#165dff",
  "#0fc6c2",
  "#722ed1",
  "#f7ba1e",
  "#f53f3f",
  "#00b42a",
  "#ff7d00",
  "#3491fa",
  "#86909c",
  "#d91ad9",
];

function polar(cx: number, cy: number, r: number, angle: number) {
  const a = ((angle - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
}

function arcPath(
  cx: number,
  cy: number,
  rOuter: number,
  rInner: number,
  start: number,
  end: number,
) {
  const large = end - start > 180 ? 1 : 0;
  const o1 = polar(cx, cy, rOuter, end);
  const o0 = polar(cx, cy, rOuter, start);
  const i1 = polar(cx, cy, rInner, end);
  const i0 = polar(cx, cy, rInner, start);
  return [
    `M ${o0.x} ${o0.y}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${o1.x} ${o1.y}`,
    `L ${i1.x} ${i1.y}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${i0.x} ${i0.y}`,
    "Z",
  ].join(" ");
}

/** Donut / pie chart (SVG). */
export function PieChart({
  title,
  subtitle,
  slices,
  height = 240,
  emptyHint = "暂无占比数据",
  maxSlices = 10,
  loading = false,
}: {
  title: string;
  subtitle?: string;
  slices: Slice[];
  height?: number;
  emptyHint?: string;
  maxSlices?: number;
  loading?: boolean;
}) {
  const cleaned = slices
    .map((s) => ({ ...s, value: Math.max(0, Number(s.value) || 0) }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);

  let items = cleaned;
  if (cleaned.length > maxSlices) {
    const head = cleaned.slice(0, maxSlices - 1);
    const rest = cleaned.slice(maxSlices - 1);
    const other = rest.reduce((a, b) => a + b.value, 0);
    items = [
      ...head,
      { id: "__other", label: "其他", value: other, color: "#c9cdd4" },
    ];
  }

  const total = items.reduce((a, b) => a + b.value, 0);
  const size = Math.max(180, height - 8);
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size * 0.38;
  const rInner = size * 0.22;

  let angle = 0;
  const paths = items.map((it, i) => {
    const frac = total > 0 ? it.value / total : 0;
    const sweep = frac * 360;
    const start = angle;
    const end = angle + Math.max(sweep, frac > 0 ? 0.3 : 0);
    angle = end;
    return {
      ...it,
      color: it.color || PALETTE[i % PALETTE.length],
      pct: frac * 100,
      d: arcPath(cx, cy, rOuter, rInner, start, end),
    };
  });

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
      ) : !items.length || total <= 0 ? (
        <div className={styles.empty} style={{ height }}>
          {emptyHint}
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            padding: "8px 12px",
            flexWrap: "wrap",
          }}
        >
          <svg
            width={size * 0.55}
            height={size * 0.55}
            viewBox={`0 0 ${size} ${size}`}
            role="img"
            aria-label={title}
          >
            {paths.map((p) => (
              <path key={p.id} d={p.d} fill={p.color}>
                <title>{`${p.label}: ${p.pct.toFixed(1)}%`}</title>
              </path>
            ))}
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              fontSize={12}
              fill="#4e5969"
              fontFamily="IBM Plex Mono, ui-monospace, monospace"
            >
              {items.length}
            </text>
            <text
              x={cx}
              y={cy + 12}
              textAnchor="middle"
              fontSize={10}
              fill="#86909c"
            >
              只
            </text>
          </svg>
          <div style={{ flex: 1, minWidth: 140, maxHeight: height - 16, overflow: "auto" }}>
            {paths.map((p) => (
              <div
                key={p.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                  marginBottom: 4,
                  fontFamily: "IBM Plex Mono, ui-monospace, monospace",
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 2,
                    background: p.color,
                    flexShrink: 0,
                  }}
                />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {p.label}
                </span>
                <span style={{ color: "#86909c" }}>{p.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
