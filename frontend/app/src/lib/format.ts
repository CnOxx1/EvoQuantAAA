export function s(v: unknown, fallback = "\u2014") {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

export function n(v: unknown, digits = 2) {
  const x = Number(v);
  if (!Number.isFinite(x)) return "\u2014";
  return x.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function fmtPct(v: unknown) {
  const x = Number(v);
  if (!Number.isFinite(x)) return { text: "\u2014", up: false, down: false };
  const sign = x > 0 ? "+" : "";
  return {
    text: `${sign}${x.toFixed(2)}%`,
    up: x > 0,
    down: x < 0,
  };
}

export function fmtAmt(v: unknown) {
  const x = Number(v);
  if (!Number.isFinite(x)) return "\u2014";
  const abs = Math.abs(x);
  if (abs >= 1e8) return `${(x / 1e8).toFixed(2)}\u4ebf`;
  if (abs >= 1e4) return `${(x / 1e4).toFixed(1)}\u4e07`;
  return x.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
