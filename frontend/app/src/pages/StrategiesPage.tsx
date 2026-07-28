import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listStrategies,
  promoteStrategy,
  type ClientConfig,
  type StrategyRow,
} from "../api/gateway";
import { ApiError } from "../api/client";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import styles from "./pages.module.css";

const LANES = ["DRAFT", "BACKTESTED", "PAPER", "LIVE", "RETIRED"] as const;

export function StrategiesPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["strategies", cfg.apiBase],
    queryFn: () => listStrategies(cfg, 100),
    enabled: connected,
  });
  const [selected, setSelected] = useState<StrategyRow | null>(null);
  const [to, setTo] = useState("PAPER");
  const [backtestRun, setBacktestRun] = useState("");
  const [reason, setReason] = useState("");
  const [skipGates, setSkipGates] = useState(false);
  const [resultBox, setResultBox] = useState("");

  const byStatus = useMemo(() => {
    const map: Record<string, StrategyRow[]> = {};
    for (const s of LANES) map[s] = [];
    for (const row of q.data ?? []) {
      const st = String(row.status || "DRAFT").toUpperCase();
      (map[st] ??= []).push(row);
    }
    return map;
  }, [q.data]);

  const mut = useMutation({
    mutationFn: () => {
      const version = String(
        selected?.strategy_version || selected?.version || "",
      );
      if (!version) throw new Error("未选择 strategy_version");
      if (skipGates && !reason.trim()) {
        throw new Error("跳过质量门必须填写原因");
      }
      return promoteStrategy(cfg, version, {
        to,
        backtest_run: backtestRun.trim() || undefined,
        reason: reason.trim() || undefined,
        skip_gates: skipGates,
      });
    },
    onSuccess: (data) => {
      setResultBox(JSON.stringify(data, null, 2));
      void qc.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setResultBox(JSON.stringify(err.body, null, 2));
      } else {
        setResultBox(String(err));
      }
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    mut.mutate();
  }

  return (
    <div>
      <h1>策略版本</h1>
      <p className="lede">
        状态机 + 晋升抽屉。LIVE 为生产信号源，不直接下单。跳过质量门须原因。
      </p>

      <div className={styles.lanes}>
        {LANES.map((lane) => (
          <div key={lane} className={styles.lane}>
            <div className={styles.laneTitle}>{lane}</div>
            <div className={styles.laneBody}>
              {(byStatus[lane] ?? []).map((row) => {
                const id = String(row.strategy_version ?? "—");
                return (
                  <button
                    key={id}
                    type="button"
                    className={styles.chip}
                    onClick={() => {
                      setSelected(row);
                      setResultBox("");
                    }}
                  >
                    <code className="mono">{id.slice(0, 14)}</code>
                  </button>
                );
              })}
              {(byStatus[lane] ?? []).length === 0 ? (
                <span className={styles.muted}>空</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.grid2}>
        <section className={styles.panel}>
          <h2>列表</h2>
          <DataTable
            headers={["version", "status", "strategy_id"]}
            empty="无策略"
          >
            {(q.data ?? []).map((row) => {
              const id = String(row.strategy_version ?? "—");
              return (
                <tr key={id}>
                  <td>
                    <button
                      type="button"
                      className={styles.linkish}
                      onClick={() => setSelected(row)}
                    >
                      <code className="mono">{id}</code>
                    </button>
                  </td>
                  <td>
                    <StatusPill tone={toneFromStatus(String(row.status))}>
                      {String(row.status ?? "—")}
                    </StatusPill>
                  </td>
                  <td className="mono">{String(row.strategy_id ?? "—")}</td>
                </tr>
              );
            })}
          </DataTable>
        </section>

        <section className={styles.panel}>
          <h2>晋升</h2>
          <form className={styles.form} onSubmit={onSubmit}>
            <label>
              strategy_version
              <input
                className="mono"
                value={String(
                  selected?.strategy_version ?? selected?.version ?? "",
                )}
                onChange={(e) =>
                  setSelected({
                    ...(selected ?? {}),
                    strategy_version: e.target.value,
                  })
                }
                required
                placeholder="sv_…"
              />
            </label>
            <label>
              目标状态
              <select value={to} onChange={(e) => setTo(e.target.value)}>
                {LANES.map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </select>
            </label>
            <label>
              backtest_run（可选）
              <input
                className="mono"
                value={backtestRun}
                onChange={(e) => setBacktestRun(e.target.value)}
                placeholder="bt_…"
              />
            </label>
            <label>
              原因
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={skipGates ? "跳过质量门必填" : "可选"}
              />
            </label>
            <label className={styles.check}>
              <input
                type="checkbox"
                checked={skipGates}
                onChange={(e) => setSkipGates(e.target.checked)}
              />
              跳过质量门（须原因）
            </label>
            <button type="submit" className={styles.primary} disabled={mut.isPending}>
              {mut.isPending ? "提交中…" : "提交晋升"}
            </button>
          </form>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>
      </div>
    </div>
  );
}
