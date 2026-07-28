export function s(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  return String(v);
}

export function n(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const x = Number(v);
  if (!Number.isFinite(x)) return s(v);
  return x.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

export function statusZh(status?: string): string {
  const map: Record<string, string> = {
    draft: "草稿",
    approved: "已放行",
    executed: "已执行",
    rejected: "已拒绝",
    blocked: "已阻断",
    committed: "已提交",
    failed: "失败",
    skipped: "跳过",
    running: "运行中",
    open: "未完成",
    filled: "已成交",
    DRAFT: "草稿",
    BACKTESTED: "已回测",
    PAPER: "纸面",
    LIVE: "生产",
    RETIRED: "退役",
    ok: "正常",
    error: "错误",
    warning: "警告",
  };
  if (!status) return "—";
  return map[status] || map[status.toLowerCase()] || status;
}

export function parseJsonField(raw: unknown): Record<string, unknown> {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    return raw as Record<string, unknown>;
  }
  if (typeof raw === "string" && raw.trim()) {
    try {
      const v = JSON.parse(raw);
      return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  }
  return {};
}
