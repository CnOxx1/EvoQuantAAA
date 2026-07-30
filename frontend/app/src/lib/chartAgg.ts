/** Aggregate list rows into chart slices/bars by a key. */
export function countBy<T>(
  rows: T[],
  keyFn: (row: T) => string,
  opts?: { colors?: Record<string, string>; defaultColor?: string },
): { id: string; label: string; value: number; color?: string }[] {
  const map = new Map<string, number>();
  for (const row of rows) {
    const k = keyFn(row) || "—";
    map.set(k, (map.get(k) || 0) + 1);
  }
  return Array.from(map.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
      color: opts?.colors?.[k] ?? opts?.defaultColor,
    }));
}

export const STATUS_COLORS: Record<string, string> = {
  committed: "#00b42a",
  passed: "#00b42a",
  approved: "#00b42a",
  frozen: "#00b42a",
  failed: "#f53f3f",
  rejected: "#f53f3f",
  error: "#f53f3f",
  draft: "#86909c",
  open: "#ff7d00",
  running: "#165dff",
  skipped: "#c9cdd4",
  degraded: "#ff7d00",
  warning: "#ff7d00",
  warn: "#ff7d00",
};
