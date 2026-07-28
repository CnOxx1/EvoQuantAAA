import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getKill,
  getLedger,
  isKillOn,
  listAlerts,
  listExecutions,
  listPending,
  listPortfolios,
  listStrategies,
  type ClientConfig,
} from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill, type PillTone } from "../components/StatusPill";
import { n, s, statusZh } from "../lib/format";
import type { Settings } from "../state/settings";
import styles from "./pages.module.css";

type Stage = { id: string; label: string; tone: PillTone; detail: string };

function buildPipeline(input: {
  strategies: number;
  portfolios: number;
  drafts: number;
  approved: number;
  killOn: boolean;
  alerts: number;
  executions: number;
  pending: number;
  cash: number | null;
  connected: boolean;
}): Stage[] {
  if (!input.connected) {
    return ["取数", "加工", "质检", "信号", "组合", "风控", "执行", "账本"].map(
      (label, i) => ({
        id: String(i),
        label,
        tone: "skipped" as const,
        detail: "请先连接网关",
      }),
    );
  }
  return [
    {
      id: "ingest",
      label: "取数",
      tone: "ok",
      detail: "由日更/CLI 负责",
    },
    {
      id: "process",
      label: "加工",
      tone: "ok",
      detail: "复权与可买卖掩码",
    },
    {
      id: "dq",
      label: "质检",
      tone: input.alerts > 0 ? "degraded" : "ok",
      detail:
        input.alerts > 0 ? `近 ${input.alerts} 条告警` : "近期无告警",
    },
    {
      id: "signal",
      label: "信号",
      tone: input.strategies > 0 ? "ok" : "degraded",
      detail: `${input.strategies} 个策略版本`,
    },
    {
      id: "portfolio",
      label: "组合",
      tone: input.portfolios > 0 ? "ok" : "degraded",
      detail: `草稿 ${input.drafts} / 已放行 ${input.approved}`,
    },
    {
      id: "risk",
      label: "风控",
      tone: input.killOn ? "failed" : "ok",
      detail: input.killOn ? "熔断已开启" : "熔断关闭",
    },
    {
      id: "exec",
      label: "执行",
      tone: input.executions > 0 ? "ok" : "info",
      detail: `${input.executions} 次执行 · 残差 ${input.pending}`,
    },
    {
      id: "ledger",
      label: "账本",
      tone: input.cash !== null ? "ok" : "degraded",
      detail:
        input.cash !== null ? `现金 ${n(input.cash, 2)}` : "账本未就绪",
    },
  ];
}

export function OverviewPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
    refetchInterval: 15_000,
  });
  const alertsQ = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 20),
    enabled: connected,
  });
  const stratQ = useQuery({
    queryKey: ["strategies", cfg.apiBase],
    queryFn: () => listStrategies(cfg, 50),
    enabled: connected,
  });
  const pfQ = useQuery({
    queryKey: ["portfolios", cfg.apiBase],
    queryFn: () => listPortfolios(cfg, { limit: 50 }),
    enabled: connected,
  });
  const exQ = useQuery({
    queryKey: ["executions", cfg.apiBase, settings.accountId],
    queryFn: () =>
      listExecutions(cfg, { accountId: settings.accountId, limit: 20 }),
    enabled: connected,
  });
  const pendQ = useQuery({
    queryKey: ["pending", cfg.apiBase, settings.accountId],
    queryFn: () =>
      listPending(cfg, { accountId: settings.accountId, status: "open" }),
    enabled: connected,
  });
  const ledgerQ = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, settings.asOf],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });

  const portfolios = pfQ.data ?? [];
  const cash =
    ledgerQ.data && !ledgerQ.isError
      ? Number(ledgerQ.data.cash ?? NaN)
      : null;
  const stages = useMemo(
    () =>
      buildPipeline({
        connected,
        strategies: stratQ.data?.length ?? 0,
        portfolios: portfolios.length,
        drafts: portfolios.filter((p) => p.status === "draft").length,
        approved: portfolios.filter((p) => p.status === "approved").length,
        killOn: isKillOn(killQ.data),
        alerts: alertsQ.data?.length ?? 0,
        executions: exQ.data?.length ?? 0,
        pending: pendQ.data?.length ?? 0,
        cash: Number.isFinite(cash as number) ? (cash as number) : null,
      }),
    [
      connected,
      stratQ.data,
      portfolios,
      killQ.data,
      alertsQ.data,
      exQ.data,
      pendQ.data,
      cash,
    ],
  );

  return (
    <div>
      <h1>今日管道</h1>
      <p className="lede">
        业务日 {settings.asOf} · 账户{" "}
        <code className="mono">{settings.accountId}</code> ·
        以下数据均来自网关已落库结果
      </p>

      <div className={styles.pipeline}>
        {stages.map((sRow, i) => (
          <div key={sRow.id} className={styles.stage}>
            {i > 0 ? <span className={styles.connector} aria-hidden /> : null}
            <div className={styles.stageBody}>
              <StatusPill tone={sRow.tone}>{sRow.label}</StatusPill>
              <span className={styles.stageDetail}>{sRow.detail}</span>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.grid2}>
        <section className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>近期告警</h2>
            <Link to="/ops">运维 →</Link>
          </div>
          <DataTable
            headers={["级别", "内容", "时间"]}
            empty="暂无告警"
            isEmpty={(alertsQ.data ?? []).length === 0}
          >
            {(alertsQ.data ?? []).slice(0, 8).map((a) => (
              <tr key={s(a.alert_id ?? a.created_at)}>
                <td>
                  <StatusPill
                    tone={
                      String(a.severity).toLowerCase() === "error"
                        ? "failed"
                        : "degraded"
                    }
                  >
                    {statusZh(String(a.severity ?? "—"))}
                  </StatusPill>
                </td>
                <td>{s(a.message ?? a.title)}</td>
                <td className="mono">{s(a.created_at)}</td>
              </tr>
            ))}
          </DataTable>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>数据摘要</h2>
            <Link to="/ledger">账本 →</Link>
          </div>
          <ul className={styles.summary}>
            <li>
              熔断：{" "}
              <StatusPill tone={isKillOn(killQ.data) ? "failed" : "ok"}>
                {isKillOn(killQ.data) ? "开启" : "关闭"}
              </StatusPill>
            </li>
            <li>
              策略版本： <strong>{stratQ.data?.length ?? 0}</strong>
            </li>
            <li>
              组合：草稿{" "}
              <strong>
                {portfolios.filter((p) => p.status === "draft").length}
              </strong>{" "}
              / 已放行{" "}
              <strong>
                {portfolios.filter((p) => p.status === "approved").length}
              </strong>{" "}
              / 已执行{" "}
              <strong>
                {portfolios.filter((p) => p.status === "executed").length}
              </strong>
            </li>
            <li>
              执行批次： <strong>{exQ.data?.length ?? 0}</strong> · 未完成残差{" "}
              <strong>{pendQ.data?.length ?? 0}</strong>
            </li>
            <li>
              现金余额：{" "}
              <strong>{cash !== null && Number.isFinite(cash) ? n(cash) : "—"}</strong>
            </li>
            <li>
              持仓只数：{" "}
              <strong>
                {Array.isArray(ledgerQ.data?.positions)
                  ? ledgerQ.data.positions.length
                  : "—"}
              </strong>
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
