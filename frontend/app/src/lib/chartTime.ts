/** Convert YYYY-MM-DD (or ISO) to lightweight-charts business day / unix. */
export function toChartTime(raw: string | number | null | undefined): string | number | null {
  if (raw == null || raw === "") return null;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  const s = String(raw).trim();
  const day = s.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) return day;
  const t = Date.parse(s);
  if (Number.isFinite(t)) return Math.floor(t / 1000);
  return null;
}

export function toLinePoints(
  rows: Array<Record<string, unknown>>,
  timeKey: string,
  valueKey: string,
): { time: string | number; value: number }[] {
  const out: { time: string | number; value: number }[] = [];
  for (const r of rows) {
    const time = toChartTime(r[timeKey] as string | number | undefined);
    const value = Number(r[valueKey]);
    if (time == null || !Number.isFinite(value)) continue;
    out.push({ time, value });
  }
  return out;
}

/** Build equal-width histogram bins for a numeric series. */
export function histogramBins(
  values: number[],
  binCount = 20,
): { label: string; value: number; mid: number }[] {
  const xs = values.filter((v) => Number.isFinite(v));
  if (!xs.length) return [];
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  if (lo === hi) {
    return [{ label: lo.toFixed(3), value: xs.length, mid: lo }];
  }
  const n = Math.max(4, Math.min(binCount, xs.length));
  const step = (hi - lo) / n;
  const counts = Array.from({ length: n }, () => 0);
  for (const v of xs) {
    let i = Math.floor((v - lo) / step);
    if (i >= n) i = n - 1;
    if (i < 0) i = 0;
    counts[i] += 1;
  }
  return counts.map((c, i) => {
    const a = lo + i * step;
    const b = a + step;
    return {
      label: `${a.toFixed(2)}`,
      value: c,
      mid: (a + b) / 2,
    };
  });
}
