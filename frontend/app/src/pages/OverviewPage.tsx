import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getKill,
  getLedger,
  isKillOn,
  listAlerts,
  listPortfolios,
  listStrategies,
  type ClientConfig,
} from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill, type PillTone } from "../components/StatusPill";
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
  hasLedger: boolean;
  connected: boolean;
}): Stage[] {
  if (!input.connected) {
    return [
      "ingest",
      "process",
      "DQ",
      "signal",
      "portfolio",
      "risk",
      "exec",
      "ledger",
    ].map((id) => ({
      id,
      label: id,
      tone: "skipped" as const,
      detail: "API 未连接",
    }));
  }
  return [
    {
      id: "ingest",
      label: "ingest",
      tone: "ok",
      detail: "经 schedule/CLI；本页不触发 bulk",
    },
    {
      id: "process",
      label: "process",
      tone: "ok",
      detail: "加工链路默认假定已跑",
    },
    {
      id: "dq",
      label: "DQ",
      tone: input.alerts > 0 ? "degraded" : "ok",
      detail: input.alerts > 0 ? `${input.alerts} 条近期告警` : "无近期告警",
    },
    {
      id: "signal",
      label: "signal",
      tone: input.strategies > 0 ? "ok" : "degraded",
      detail: `${input.strategies} 个策略版本`,
    },
    {
      id: "portfolio",
      label: "portfolio",
      tone: input.portfolios > 0 ? "ok" : "degraded",
      detail: `${input.drafts} draft / ${input.approved} approved`,
    },
    {
      id: "risk",
      label: "risk",
      tone: input.killOn ? "failed" : "ok",
      detail: input.killOn ? "Kill ON" : "Kill OFF",
    },
    {
      id: "exec",
      label: "exec",
      tone: "info",
      detail: "执行只读；F3 前不在 UI 下单",
    },
    {
      id: "ledger",
      label: "ledger",
      tone: input.hasLedger ? "ok" : "degraded",
      detail: input.hasLedger ? "账户可读" : "账本未就绪",
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
  const ledgerQ = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });

  const portfolios = pfQ.data ?? [];
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
        hasLedger: Boolean(ledgerQ.data && !ledgerQ.isError),
      }),
    [
      connected,
      stratQ.data,
      portfolios,
      killQ.data,
      alertsQ.data,
      ledgerQ.data,
      ledgerQ.isError,
    ],
  );

  return (
    <div>
      <h1>今日管道</h1>
      <p className="lede">
        as-of {settings.asOf} · 灯带由现有 gateway 接口拼装（F1）；不触发长窗
        bulk。
      </p>

      <div className={styles.pipeline}>
        {stages.map((s, i) => (
          <div key={s.id} className={styles.stage}>
            {i > 0 ? <span className={styles.connector} aria-hidden /> : null}
            <div className={styles.stageBody}>
              <StatusPill tone={s.tone}>{s.label}</StatusPill>
              <span className={styles.stageDetail}>{s.detail}</span>
            </div>
          </div>
        ))}
      </div>

      <div className={styles.grid2}>
        <section className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>近期告警</h2>
            <Link to="/ops">Ops →</Link>
          </div>
          <DataTable headers={["severity", "内容", "时间"]} empty="无告警">
            {(alertsQ.data ?? []).slice(0, 8).map((a) => (
              <tr key={String(a.alert_id ?? a.created_at ?? Math.random())}>
                <td>
                  <StatusPill
                    tone={
                      String(a.severity).toLowerCase() === "error"
                        ? "failed"
                        : "degraded"
                    }
                  >
                    {String(a.severity ?? "—")}
                  </StatusPill>
                </td>
                <td>{String(a.message ?? a.title ?? "—")}</td>
                <td className="mono">{String(a.created_at ?? "—")}</td>
              </tr>
            ))}
          </DataTable>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>状态摘要</h2>
            <Link to="/risk">Risk →</Link>
          </div>
          <ul className={styles.summary}>
            <li>
              Kill：{" "}
              <StatusPill tone={isKillOn(killQ.data) ? "failed" : "ok"}>
                {isKillOn(killQ.data) ? "ON" : "OFF"}
              </StatusPill>
            </li>
            <li>
              策略版本： <strong>{stratQ.data?.length ?? 0}</strong>
            </li>
            <li>
              组合： draft{" "}
              <strong>
                {portfolios.filter((p) => p.status === "draft").length}
              </strong>{" "}
              / approved{" "}
              <strong>
                {portfolios.filter((p) => p.status === "approved").length}
              </strong>
            </li>
            <li>
              账户 <code className="mono">{settings.accountId}</code>
            </li>
            <li className={styles.muted}>
              pending / execution 列表 API 待 F1 后端补齐；Trade 页占位。
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
