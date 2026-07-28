import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getPortfolio,
  listPortfolios,
  reviewRisk,
  type ClientConfig,
  type PortfolioRow,
} from "../api/gateway";
import { ApiError } from "../api/client";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import type { Settings } from "../state/settings";
import styles from "./pages.module.css";

export function PortfolioPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<PortfolioRow | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [resultBox, setResultBox] = useState("");

  const listQ = useQuery({
    queryKey: ["portfolios", cfg.apiBase, statusFilter, settings.asOf],
    queryFn: () =>
      listPortfolios(cfg, {
        status: statusFilter || undefined,
        asOf: settings.asOf,
        limit: 50,
      }),
    enabled: connected,
  });

  const mut = useMutation({
    mutationFn: async (mode: "one" | "drafts") => {
      if (mode === "one") {
        const id = String(selected?.portfolio_id || "");
        if (!id) throw new Error("请先选择 portfolio");
        return reviewRisk(cfg, { portfolio_id: id });
      }
      return reviewRisk(cfg, { drafts: true, as_of: settings.asOf });
    },
    onSuccess: (data) => {
      setResultBox(JSON.stringify(data, null, 2));
      void qc.invalidateQueries({ queryKey: ["portfolios"] });
      void qc.invalidateQueries({ queryKey: ["decisions"] });
    },
    onError: (err) => {
      setResultBox(
        err instanceof ApiError
          ? JSON.stringify(err.body, null, 2)
          : String(err),
      );
    },
  });

  async function openDetail(row: PortfolioRow) {
    setSelected(row);
    setResultBox("");
    try {
      const d = await getPortfolio(cfg, String(row.portfolio_id));
      setDetail(d);
    } catch (err) {
      setDetail(null);
      setResultBox(
        err instanceof ApiError
          ? JSON.stringify(err.body, null, 2)
          : String(err),
      );
    }
  }

  const positions = Array.isArray(detail?.positions)
    ? (detail?.positions as Record<string, unknown>[])
    : Array.isArray(detail?.items)
      ? (detail?.items as Record<string, unknown>[])
      : [];

  return (
    <div>
      <h1>目标持仓</h1>
      <p className="lede">
        draft → 风控审核。成交执行仍走 schedule/CLI（F3 前 UI 不下单）。
      </p>

      <div className={styles.toolbar}>
        <label>
          状态
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">全部</option>
            <option value="draft">draft</option>
            <option value="approved">approved</option>
            <option value="executed">executed</option>
          </select>
        </label>
        <button
          type="button"
          className={styles.primary}
          disabled={mut.isPending || !selected}
          onClick={() => mut.mutate("one")}
        >
          审核所选
        </button>
        <button
          type="button"
          className={styles.secondary}
          disabled={mut.isPending}
          onClick={() => mut.mutate("drafts")}
        >
          批量审核 draft（as-of）
        </button>
      </div>

      <div className={styles.grid2}>
        <section className={styles.panel}>
          <h2>组合</h2>
          <DataTable
            headers={["portfolio", "status", "strategy", "as_of"]}
            empty="无组合"
          >
            {(listQ.data ?? []).map((row) => {
              const id = String(row.portfolio_id ?? "—");
              return (
                <tr key={id}>
                  <td>
                    <button
                      type="button"
                      className={styles.linkish}
                      onClick={() => void openDetail(row)}
                    >
                      <code className="mono">{id}</code>
                    </button>
                  </td>
                  <td>
                    <StatusPill tone={toneFromStatus(String(row.status))}>
                      {String(row.status ?? "—")}
                    </StatusPill>
                  </td>
                  <td className="mono">
                    {String(row.strategy_version ?? "—")}
                  </td>
                  <td className="mono">
                    {String(row.as_of_date ?? row.as_of ?? "—")}
                  </td>
                </tr>
              );
            })}
          </DataTable>
        </section>

        <section className={styles.panel}>
          <h2>持仓明细</h2>
          <DataTable
            headers={["symbol", "target", "price", "can_buy", "can_sell"]}
            empty="选择组合查看"
          >
            {positions.map((p, i) => (
              <tr key={`${String(p.symbol)}-${i}`}>
                <td className="mono">{String(p.symbol ?? "—")}</td>
                <td>{String(p.target_shares ?? p.shares ?? "—")}</td>
                <td>{String(p.price ?? "—")}</td>
                <td>{String(p.can_buy ?? "—")}</td>
                <td>{String(p.can_sell ?? "—")}</td>
              </tr>
            ))}
          </DataTable>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>
      </div>
    </div>
  );
}
