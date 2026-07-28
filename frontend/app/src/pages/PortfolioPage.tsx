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
import { n, s, statusZh } from "../lib/format";
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
    queryKey: ["portfolios", cfg.apiBase, statusFilter],
    queryFn: () =>
      listPortfolios(cfg, {
        status: statusFilter || undefined,
        limit: 50,
      }),
    enabled: connected,
  });

  const mut = useMutation({
    mutationFn: async (mode: "one" | "drafts") => {
      if (mode === "one") {
        const id = String(selected?.portfolio_id || "");
        if (!id) throw new Error("请先选择组合");
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
    : [];

  return (
    <div>
      <h1>目标组合</h1>
      <p className="lede">
        数据来自 <code className="mono">/v1/portfolios</code>
        。可提交风控审核；成交执行仍由 CLI/日更完成。
      </p>

      <div className={styles.toolbar}>
        <label>
          状态筛选
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">全部</option>
            <option value="draft">草稿</option>
            <option value="approved">已放行</option>
            <option value="executed">已执行</option>
          </select>
        </label>
        <button
          type="button"
          className={styles.primary}
          disabled={mut.isPending || !selected || !connected}
          onClick={() => mut.mutate("one")}
        >
          审核所选组合
        </button>
        <button
          type="button"
          className={styles.secondary}
          disabled={mut.isPending || !connected}
          onClick={() => mut.mutate("drafts")}
        >
          批量审核当日草稿
        </button>
      </div>

      <div className={styles.grid2}>
        <section className={styles.panel}>
          <h2>组合列表（{listQ.data?.length ?? 0}）</h2>
          <DataTable
            headers={["组合 ID", "状态", "策略", "业务日", "NAV", "账户"]}
            empty="无组合"
            isEmpty={(listQ.data ?? []).length === 0}
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
                      {statusZh(String(row.status))}
                    </StatusPill>
                  </td>
                  <td className="mono">
                    {s(row.strategy_version).slice(0, 18)}
                  </td>
                  <td className="mono">
                    {s(row.as_of_date ?? row.as_of)}
                  </td>
                  <td>{n(row.nav)}</td>
                  <td className="mono">{s(row.account_id)}</td>
                </tr>
              );
            })}
          </DataTable>
        </section>

        <section className={styles.panel}>
          <h2>目标持仓明细</h2>
          <DataTable
            headers={["代码", "目标股数", "权重", "价格", "市值"]}
            empty="选择左侧组合查看"
            isEmpty={positions.length === 0}
          >
            {positions.map((p, i) => (
              <tr key={`${s(p.symbol)}-${i}`}>
                <td className="mono">{s(p.symbol)}</td>
                <td>{n(p.target_shares, 0)}</td>
                <td>{n(p.target_weight, 4)}</td>
                <td>{n(p.price)}</td>
                <td>{n(p.target_value)}</td>
              </tr>
            ))}
          </DataTable>
          {resultBox ? <pre className={styles.result}>{resultBox}</pre> : null}
        </section>
      </div>
    </div>
  );
}
