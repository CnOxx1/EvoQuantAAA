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
    if (isOn && !window.confirm("确认开启 Kill Switch？将阻止新开仓。")) return;
    mut.mutate(isOn);
  }

  return (
    <div>
      <h1>风控</h1>
      <p className="lede">
        Kill Switch 与决策列表。ADV/行业明细以决策返回为准。
      </p>

      <div className={styles.grid2}>
        <section className={`${styles.panel} ${styles.dangerPanel}`}>
          <h2>Kill Switch</h2>
          <p className={styles.killStatus}>
            当前：{" "}
            <StatusPill tone={isKillOn(killQ.data) ? "failed" : "ok"}>
              {isKillOn(killQ.data) ? "ON" : "OFF"}
            </StatusPill>
          </p>
          <form className={styles.form}>
            <label>
              Scope
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
                disabled={mut.isPending}
                onClick={(e) => onKill(e, true)}
              >
                开启 Kill
              </button>
              <button
                type="button"
                className={styles.primary}
                disabled={mut.isPending}
                onClick={(e) => onKill(e, false)}
              >
                解除 Kill
              </button>
            </div>
          </form>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>

        <section className={styles.panel}>
          <h2>决策</h2>
          <DataTable
            headers={["decision", "portfolio", "status", "time"]}
            empty="无决策"
          >
            {(decQ.data ?? []).map((d) => (
              <tr key={String(d.decision_id ?? Math.random())}>
                <td className="mono">{String(d.decision_id ?? "—")}</td>
                <td className="mono">{String(d.portfolio_id ?? "—")}</td>
                <td>
                  <StatusPill tone={toneFromStatus(String(d.status))}>
                    {String(d.status ?? "—")}
                  </StatusPill>
                </td>
                <td className="mono">{String(d.created_at ?? "—")}</td>
              </tr>
            ))}
          </DataTable>
        </section>
      </div>
    </div>
  );
}
