import {
  listDqGates,
  listEconCalendar,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";

export function ymd(d: Date): string {
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  d.setDate(d.getDate() + n);
  return ymd(d);
}

/** Prefer SSE open days; fall back to any exchange with is_open. */
export function openTradeDays(rows: JsonMap[]): string[] {
  const sse = new Set<string>();
  const any = new Set<string>();
  for (const r of rows) {
    const open = r.is_open === true || r.is_open === 1 || r.is_open === "1";
    if (!open) continue;
    const day = String(r.trade_date || "").slice(0, 10);
    if (!day) continue;
    any.add(day);
    const ex = String(r.exchange || "").toUpperCase();
    if (ex.includes("SSE") || ex.includes("SH") || ex === "XSHG") {
      sse.add(day);
    }
  }
  const set = sse.size ? sse : any;
  return [...set].sort();
}

export async function fetchOpenTradeDays(
  cfg: ClientConfig,
  opts?: { start?: string; end?: string },
): Promise<string[]> {
  const end = opts?.end || ymd(new Date());
  const start = opts?.start || addDays(end, -120);
  const data = await listEconCalendar(cfg, { start, end, limit: 300 });
  return openTradeDays(data.trade_days ?? []);
}

export function prevOpenDay(openDays: string[], asOf: string): string | null {
  const day = asOf.slice(0, 10);
  for (let i = openDays.length - 1; i >= 0; i -= 1) {
    if (openDays[i] <= day) return openDays[i];
  }
  return openDays.length ? openDays[openDays.length - 1] : null;
}

export function isOpenTradeDay(openDays: string[], asOf: string): boolean {
  return openDays.includes(asOf.slice(0, 10));
}

export type DqAsOfStatus = {
  status: string;
  ok: boolean;
  scope: string;
  start?: string;
  end?: string;
  detail: string;
};

/** Pick best CORE (else any) gate covering as_of. */
export function dqStatusForAsOf(
  gates: JsonMap[],
  asOf: string,
): DqAsOfStatus {
  const day = asOf.slice(0, 10);
  if (!day) {
    return { status: "unknown", ok: false, scope: "", detail: "未设置业务日" };
  }
  const covering = gates.filter((g) => {
    const a = String(g.start_date || "").slice(0, 10);
    const b = String(g.end_date || "").slice(0, 10);
    return a && b && a <= day && day <= b;
  });
  const core = covering.filter(
    (g) => String(g.scope || "").toUpperCase() === "CORE",
  );
  const pool = core.length ? core : covering;
  if (!pool.length) {
    return {
      status: "missing",
      ok: false,
      scope: "CORE",
      detail: `无覆盖 ${day} 的 DQ gate`,
    };
  }
  const passed = pool.find((g) => {
    const st = String(g.status || "").toLowerCase();
    return st === "pass" || st === "passed" || st === "ok";
  });
  const pick = passed || pool[0];
  const st = String(pick.status || "unknown");
  const ok =
    st.toLowerCase() === "pass" ||
    st.toLowerCase() === "passed" ||
    st.toLowerCase() === "ok";
  return {
    status: st,
    ok,
    scope: String(pick.scope || ""),
    start: String(pick.start_date || "").slice(0, 10),
    end: String(pick.end_date || "").slice(0, 10),
    detail: `${pick.scope || "?"} ${st} · ${String(pick.start_date || "").slice(0, 10)}→${String(pick.end_date || "").slice(0, 10)}`,
  };
}

export async function fetchDqAsOf(
  cfg: ClientConfig,
  asOf: string,
): Promise<DqAsOfStatus> {
  const gates = await listDqGates(cfg, { limit: 80 });
  return dqStatusForAsOf(gates, asOf);
}
