import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getKill,
  isKillOn,
  listDecisions,
  setKill,
  type ClientConfig,
} from "../api/gateway";
import { ApiError } from "../api/client";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import { n, parseJsonField, s, statusZh } from "../lib/format";
import styles from "./pages.module.css";

export function RiskPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
    refetchInterval: 10_000,
  });
  const decQ = useQuery({
    queryKey: ["decisions", cfg.apiBase],
    queryFn: () => listDecisions(cfg, 30),
    enabled: connected,
  });

  const [scope, setScope] = useState("GLOBAL");
  const [reason, setReason] = useState("");
  const [resultBox, setResultBox] = useState("");

  const switches = (killQ.data?.kill_switches || []) as Array<
    Record<string, unknown>
  >;

  const mut = useMutation({
    mutationFn: (isOn: boolean) =>
      setKill(cfg, {
        scope: scope.trim() || "GLOBAL",
        is_on: isOn,
        reason: reason.trim() || undefined,
      }),
    onSuccess: (data) => {
      setResultBox(JSON.stringify(data, null, 2));
      void qc.invalidateQueries({ queryKey: ["kill"] });
    },
    onError: (err) => {
      setResultBox(
        err instanceof ApiError
          ? JSON.stringify(err.body, null, 2)
          : String(err),
      );
    },
  });

  function onKill(e: FormEvent, isOn: boolean) {
    e.preventDefault();
    if (isOn && !window.confirm("确认开启熔断？开启后将阻止新开仓。")) return;
    mut.mutate(isOn);
  }

  return (
    <div>
      <h1>风控</h1>
      <p className="lede">
        熔断开关与审核决策。数据来自{" "}
        <code className="mono">/v1/risk/kill</code> 与{" "}
        <code className="mono">/v1/risk/decisions</code>。
      </p>

      <div className={styles.grid2}>
        <section className={`${styles.panel} ${styles.dangerPanel}`}>
          <h2>熔断开关（Kill Switch）</h2>
          <p className={styles.killStatus}>
            汇总状态：{" "}
            <StatusPill tone={isKillOn(killQ.data) ? "failed" : "ok"}>
              {isKillOn(killQ.data) ? "开启" : "关闭"}
            </StatusPill>
          </p>
          <DataTable
            headers={["作用域", "状态", "原因", "操作人", "更新时间"]}
            empty="无熔断记录"
            isEmpty={switches.length === 0}
          >
            {switches.map((row) => (
              <tr key={s(row.scope_key)}>
                <td className="mono">{s(row.scope_key)}</td>
                <td>
                  <StatusPill
                    tone={Number(row.is_on) === 1 ? "failed" : "ok"}
                  >
                    {Number(row.is_on) === 1 ? "开启" : "关闭"}
                  </StatusPill>
                </td>
                <td>{s(row.reason)}</td>
                <td>{s(row.actor)}</td>
                <td className="mono">{s(row.updated_at)}</td>
              </tr>
            ))}
          </DataTable>
          <form className={styles.form} style={{ marginTop: "0.85rem" }}>
            <label>
              作用域
              <input
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                required
              />
            </label>
            <label>
              原因
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="可选"
              />
            </label>
            <div className={styles.btnRow}>
              <button
                type="button"
                className={styles.danger}
                disabled={mut.isPending || !connected}
                onClick={(e) => onKill(e, true)}
              >
                开启熔断
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={mut.isPending || !connected}
                onClick={(e) => onKill(e, false)}
              >
                解除熔断
              </button>
            </div>
          </form>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>

        <section className={styles.panel}>
          <h2>审核决策（{decQ.data?.length ?? 0}）</h2>
          <DataTable
            headers={["决策 ID", "组合", "结果", "违约数", "时间"]}
            empty="无决策"
            isEmpty={(decQ.data ?? []).length === 0}
          >
            {(decQ.data ?? []).map((d) => {
              const meta = parseJsonField(d.meta_json ?? d.meta);
              return (
                <tr key={s(d.decision_id)}>
                  <td className="mono">{s(d.decision_id)}</td>
                  <td className="mono">{s(d.portfolio_id).slice(0, 16)}</td>
                  <td>
                    <StatusPill tone={toneFromStatus(String(d.status))}>
                      {statusZh(String(d.status))}
                    </StatusPill>
                  </td>
                  <td>
                    {n(d.breach_count, 0)}
                    {meta.limits_version
                      ? ` · ${String(meta.limits_version)}`
                      : ""}
                  </td>
                  <td className="mono">{s(d.created_at)}</td>
                </tr>
              );
            })}
          </DataTable>
        </section>
      </div>
    </div>
  );
}
