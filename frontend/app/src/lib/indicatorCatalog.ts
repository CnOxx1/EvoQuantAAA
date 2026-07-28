/** 指标预设与配色（placement 以 meta API 为准）。 */

export const MAX_OVERLAY = 8;
export const MAX_SUB = 6;

export const PALETTE = [
  "#ff7d00",
  "#165dff",
  "#722ed1",
  "#0fc6c2",
  "#f5319d",
  "#f7ba1e",
  "#3491fa",
  "#00b42a",
  "#86909c",
  "#f53f3f",
  "#b71de8",
  "#14c9c9",
] as const;

export type IndPlacement = "overlay" | "sub";
export type IndStyle = "line" | "hist";

export type IndicatorMetaItem = {
  code: string;
  count: number;
  category: string;
  category_zh: string;
  placement: IndPlacement;
  style: IndStyle;
};

export type IndicatorPreset = {
  id: string;
  label: string;
  codes: string[];
};

export const PRESETS: IndicatorPreset[] = [
  { id: "ma", label: "MA", codes: ["MA_5", "MA_20", "MA_60"] },
  { id: "ema", label: "EMA", codes: ["EMA_12", "EMA_26"] },
  { id: "boll", label: "BOLL", codes: ["BOLL_UP", "BOLL_MID", "BOLL_LOW"] },
  { id: "macd", label: "MACD", codes: ["MACD_DIF", "MACD_DEA", "MACD_HIST"] },
  { id: "rsi", label: "RSI", codes: ["RSI_14"] },
];

export const DEFAULT_ACTIVE = ["MA_5", "MA_20", "MA_60", "RSI_14"];

export function colorFor(index: number): string {
  return PALETTE[index % PALETTE.length];
}

export function placementOf(
  code: string,
  metaByCode: Map<string, IndicatorMetaItem>,
): IndPlacement {
  const m = metaByCode.get(code);
  if (m) return m.placement;
  const u = code.toUpperCase();
  if (
    /^(MA_|EMA_|SMA_|WMA_|HMA_|BOLL_|BB|KC|DC|SUPERT|PSAR|HA_)/.test(u)
  ) {
    return "overlay";
  }
  return "sub";
}

export function styleOf(
  code: string,
  metaByCode: Map<string, IndicatorMetaItem>,
): IndStyle {
  return metaByCode.get(code)?.style ?? (code.toUpperCase().includes("HIST") ? "hist" : "line");
}

/** 切换预设：若全部已选则移除，否则在限额内补齐。 */
export function togglePreset(
  active: string[],
  preset: IndicatorPreset,
  metaByCode: Map<string, IndicatorMetaItem>,
): { next: string[]; msg?: string } {
  const allOn = preset.codes.every((c) => active.includes(c));
  if (allOn) {
    return { next: active.filter((c) => !preset.codes.includes(c)) };
  }
  let next = [...active];
  let msg: string | undefined;
  for (const code of preset.codes) {
    if (next.includes(code)) continue;
    const place = placementOf(code, metaByCode);
    const overlays = next.filter((c) => placementOf(c, metaByCode) === "overlay");
    const subs = next.filter((c) => placementOf(c, metaByCode) === "sub");
    if (place === "overlay" && overlays.length >= MAX_OVERLAY) {
      msg = `主图最多 ${MAX_OVERLAY} 条`;
      continue;
    }
    if (place === "sub" && subs.length >= MAX_SUB) {
      msg = `副图最多 ${MAX_SUB} 条`;
      continue;
    }
    next.push(code);
  }
  return { next, msg };
}

export function toggleCode(
  active: string[],
  code: string,
  metaByCode: Map<string, IndicatorMetaItem>,
): { next: string[]; msg?: string } {
  if (active.includes(code)) {
    return { next: active.filter((c) => c !== code) };
  }
  const place = placementOf(code, metaByCode);
  const overlays = active.filter((c) => placementOf(c, metaByCode) === "overlay");
  const subs = active.filter((c) => placementOf(c, metaByCode) === "sub");
  if (place === "overlay" && overlays.length >= MAX_OVERLAY) {
    return { next: active, msg: `主图最多 ${MAX_OVERLAY} 条` };
  }
  if (place === "sub" && subs.length >= MAX_SUB) {
    return { next: active, msg: `副图最多 ${MAX_SUB} 条` };
  }
  return { next: [...active, code] };
}

export function presetActive(active: string[], preset: IndicatorPreset): boolean {
  return preset.codes.every((c) => active.includes(c));
}
