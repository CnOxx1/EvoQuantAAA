import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Alert, Space, Tag, Typography } from "@arco-design/web-react";
import {
  getKill,
  getLedger,
  isKillOn,
  listDqGates,
  listPortfolios,
  listSignalBatches,
  type ClientConfig,
} from "../api/gateway";
import {
  dqStatusForAsOf,
  fetchOpenTradeDays,
  isOpenTradeDay,
  prevOpenDay,
} from "../lib/tradeCalendar";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

/** Business-day readiness strip for quant ops. */
export function DayStatusBar({
  cfg,
  settings,
  connected,
  onSnapAsOf,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
  onSnapAsOf?: (day: string) => void;
}) {
  const asOf = settings.asOf;

  const calQ = useQuery({
    queryKey: ["trade-days", cfg.apiBase],
    queryFn: () => fetchOpenTradeDays(cfg),
    enabled: connected,
    staleTime: 60_000,
  });
  const dqQ = useQuery({
    queryKey: ["dq-gates", cfg.apiBase],
    queryFn: () => listDqGates(cfg, { limit: 80 }),
    enabled: connected,
    staleTime: 30_000,
  });
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
    refetchInterval: 15_000,
  });
  const ledgerQ = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, asOf],
    queryFn: () => getLedger(cfg, settings.accountId, asOf),
    enabled: connected && Boolean(asOf),
  });
  const sigQ = useQuery({
    queryKey: ["signals-day", cfg.apiBase, asOf],
    queryFn: () => listSignalBatches(cfg, 30),
    enabled: connected && Boolean(asOf),
  });
  const portQ = useQuery({
    queryKey: ["portfolios-day", cfg.apiBase, asOf],
    queryFn: () => listPortfolios(cfg, { asOf, limit: 50 }),
    enabled: connected && Boolean(asOf),
  });

  const openDays = calQ.data ?? [];
  const tradeOk = asOf ? isOpenTradeDay(openDays, asOf) : false;
  const prev = asOf && openDays.length ? prevOpenDay(openDays, asOf) : null;
  const dq = dqStatusForAsOf(dqQ.data ?? [], asOf || "");
  const killOn = isKillOn(killQ.data);
  const mark = (ledgerQ.data?.mark as Record<string, unknown> | undefined) ?? {};
  const nav = Number(ledgerQ.data?.nav ?? mark.nav);
  const cash = Number(ledgerQ.data?.cash ?? mark.cash);
  const pnl = Number(ledgerQ.data?.pnl ?? mark.pnl);
  const pnlPct = ledgerQ.data?.pnl_pct ?? mark.pnl_pct;

  const daySignals = (sigQ.data ?? []).filter(
    (r) => String(r.as_of_date ?? r.as_of ?? "").slice(0, 10) === asOf,
  ).length;
  const dayPorts = (portQ.data ?? []).length;
  const dayApproved = (portQ.data ?? []).filter(
    (r) => String(r.status).toLowerCase() === "approved",
  ).length;

  if (!connected) return null;

  return (
    <div style={{ marginBottom: 12 }}>
      <Space wrap size={8} style={{ marginBottom: 8 }}>
        <Tag color={asOf ? "arcoblue" : "red"}>业务日 {asOf || "未设"}</Tag>
        <Tag
          color={
            calQ.isLoading ? "gray" : tradeOk ? "green" : asOf ? "orangered" : "gray"
          }
          title={tradeOk ? "开市日" : "非开市日（编排可能 skipped）"}
        >
          {calQ.isLoading ? "交易日…" : tradeOk ? "开市" : "休市/未知"}
        </Tag>
        {!tradeOk && prev && prev !== asOf && onSnapAsOf ? (
          <Tag
            color="arcoblue"
            style={{ cursor: "pointer" }}
            onClick={() => onSnapAsOf(prev)}
          >
            对齐上一开市日 {prev}
          </Tag>
        ) : null}
        <Tag color={dq.ok ? "green" : "red"} title={dq.detail}>
          DQ {dq.status}
        </Tag>
        <Link to="/risk">
          <Tag color={killOn ? "red" : "green"}>
            Kill {killOn ? "ON" : "OFF"}
          </Tag>
        </Link>
        <Tag color="purple">
          当日信号 {daySignals} · 组合 {dayPorts}/{dayApproved}审
        </Tag>
        <Link to="/data/quality" style={{ fontSize: 12 }}>
          质量门 →
        </Link>
        <Link to="/risk" style={{ fontSize: 12 }}>
          风控 →
        </Link>
      </Space>

      <Alert
        type={dq.ok && !killOn && tradeOk ? "success" : "warning"}
        content={
          <Space wrap size={16}>
            <Typography.Text>
              现金 <b>{n(cash, 2)}</b>
            </Typography.Text>
            <Typography.Text>
              市值 <b>{n(mark.market_value, 2)}</b>
            </Typography.Text>
            <Typography.Text>
              NAV <b>{Number.isFinite(nav) ? n(nav, 2) : "—"}</b>
            </Typography.Text>
            <Typography.Text>
              相对开户盈亏{" "}
              <b>
                {Number.isFinite(pnl) ? n(pnl, 2) : "—"}
                {pnlPct != null && Number.isFinite(Number(pnlPct))
                  ? ` (${(Number(pnlPct) * 100).toFixed(2)}%)`
                  : ""}
              </b>
            </Typography.Text>
            <Typography.Text type="secondary">
              账户 {settings.accountId}
              {mark.missing_prices
                ? ` · 缺价 ${s(mark.missing_prices)}`
                : ""}
            </Typography.Text>
            <Link to="/ledger" style={{ fontSize: 12 }}>
              账本 →
            </Link>
          </Space>
        }
      />
    </div>
  );
}
