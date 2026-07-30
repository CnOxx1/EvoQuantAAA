import { Spin } from "@arco-design/web-react";
import styles from "./Heatmap.module.css";

export function Heatmap({
  title,
  subtitle,
  rowLabels,
  colLabels,
  values,
  emptyHint = "暂无矩阵数据",
  loading = false,
}: {
  title: string;
  subtitle?: string;
  rowLabels: string[];
  colLabels: string[];
  /** values[row][col] */
  values: number[][];
  emptyHint?: string;
  loading?: boolean;
}) {
  const flat = values.flat().filter((v) => Number.isFinite(v));
  const max = flat.length ? Math.max(...flat) : 0;

  const cellColor = (n: number) => {
    if (!Number.isFinite(n) || n <= 0) return "var(--color-fill-2)";
    if (max <= 0) return "rgb(var(--primary-2))";
    const t = Math.min(1, n / max);
    const alpha = 0.15 + t * 0.75;
    return `rgba(22, 93, 255, ${alpha.toFixed(3)})`;
  };

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <div>
          <div className={styles.title}>{title}</div>
          {subtitle ? <div className={styles.sub}>{subtitle}</div> : null}
        </div>
      </div>
      {loading ? (
        <div className={styles.empty}>
          <Spin tip="加载中…" />
        </div>
      ) : !rowLabels.length || !colLabels.length ? (
        <div className={styles.empty}>{emptyHint}</div>
      ) : (
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.corner} />
                {colLabels.map((c) => (
                  <th key={c} className={styles.col}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowLabels.map((r, ri) => (
                <tr key={r}>
                  <th className={styles.row}>{r}</th>
                  {colLabels.map((c, ci) => {
                    const n = values[ri]?.[ci] ?? 0;
                    return (
                      <td
                        key={c}
                        className={styles.cell}
                        style={{ background: cellColor(n) }}
                        title={`${r} · ${c} = ${n}`}
                      >
                        {n || "·"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
