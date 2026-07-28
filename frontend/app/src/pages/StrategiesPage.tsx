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
import { parseJsonField, s, statusZh } from "../lib/format";
import styles from "./pages.module.css";

const LANES = ["DRAFT", "BACKTESTED", "PAPER", "LIVE", "RETIRED"] as const;
const LANE_ZH: Record<string, string> = {
  DRAFT: "草稿",
  BACKTESTED: "已回测",
  PAPER: "纸面",
  LIVE: "生产",
  RETIRED: "退役",
};

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
    for (const lane of LANES) map[lane] = [];
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
      if (!version) throw new Error("未选择策略版本");
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
      setResultBox(
        err instanceof ApiError
          ? JSON.stringify(err.body, null, 2)
          : String(err),
      );
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    mut.mutate();
  }

  const params = parseJsonField(selected?.params);

  return (
    <div>
      <h1>策略版本</h1>
      <p className="lede">
        数据来自 <code className="mono">/v1/strategies</code>
        。LIVE 表示可出生产信号，不代表本台可下单。
      </p>

      <div className={styles.lanes}>
        {LANES.map((lane) => (
          <div key={lane} className={styles.lane}>
            <div className={styles.laneTitle}>
              {LANE_ZH[lane]} ({lane})
            </div>
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
                      setBacktestRun(String(row.backtest_run_id ?? ""));
                      setResultBox("");
                    }}
                  >
                    <code className="mono">{id.slice(0, 16)}</code>
                    <div className={styles.muted}>
                      {s(row.strategy_code ?? row.strategy_kind)}
                    </div>
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
          <h2>策略列表（{q.data?.length ?? 0}）</h2>
          <DataTable
            headers={["版本", "代码", "类型", "状态", "更新时间"]}
            empty="无策略"
            isEmpty={(q.data ?? []).length === 0}
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
                  <td>{s(row.strategy_code)}</td>
                  <td className="mono">{s(row.strategy_kind)}</td>
                  <td>
                    <StatusPill tone={toneFromStatus(String(row.status))}>
                      {statusZh(String(row.status))}
                    </StatusPill>
                  </td>
                  <td className="mono">{s(row.updated_at)}</td>
                </tr>
              );
            })}
          </DataTable>
          {selected ? (
            <pre className={styles.result} style={{ marginTop: "0.75rem" }}>
              {JSON.stringify(
                {
                  strategy_version: selected.strategy_version,
                  note: selected.note,
                  research_run_id: selected.research_run_id,
                  backtest_run_id: selected.backtest_run_id,
                  params,
                },
                null,
                2,
              )}
            </pre>
          ) : null}
        </section>

        <section className={styles.panel}>
          <h2>晋升操作</h2>
          <form className={styles.form} onSubmit={onSubmit}>
            <label>
              策略版本
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
                    {LANE_ZH[x]} ({x})
                  </option>
                ))}
              </select>
            </label>
            <label>
              关联回测（可选）
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
              跳过质量门（必须填写原因）
            </label>
            <button
              type="submit"
              className={styles.primary}
              disabled={mut.isPending || !connected}
            >
              {mut.isPending ? "提交中…" : "提交晋升"}
            </button>
          </form>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>
      </div>
    </div>
  );
}
