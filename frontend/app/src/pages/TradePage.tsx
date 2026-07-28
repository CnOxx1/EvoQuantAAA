import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getExecution,
  listExecutions,
  listPending,
  type ClientConfig,
  type ExecutionRow,
} from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import { n, s, statusZh } from "../lib/format";
import type { Settings } from "../state/settings";
import styles from "./pages.module.css";

export function TradePage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [selected, setSelected] = useState<ExecutionRow | null>(null);

  const listQ = useQuery({
    queryKey: ["executions", cfg.apiBase, settings.accountId],
    queryFn: () =>
      listExecutions(cfg, { accountId: settings.accountId, limit: 50 }),
    enabled: connected,
  });
  const pendQ = useQuery({
    queryKey: ["pending", cfg.apiBase, settings.accountId],
    queryFn: () =>
      listPending(cfg, {
        accountId: settings.accountId,
        status: "open",
        limit: 100,
      }),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["execution", cfg.apiBase, selected?.execution_id],
    queryFn: () => getExecution(cfg, String(selected!.execution_id)),
    enabled: connected && Boolean(selected?.execution_id),
  });

  const fills = Array.isArray(detailQ.data?.fills)
    ? (detailQ.data!.fills as Array<Record<string, unknown>>)
    : [];
  const orders = Array.isArray(detailQ.data?.orders)
    ? (detailQ.data!.orders as Array<Record<string, unknown>>)
    : [];

  return (
    <div>
      <h1>交易执行</h1>
      <p className="lede">
        账户 <code className="mono">{settings.accountId}</code> ·
        只读展示执行批次 / 成交 / 残差 ·{" "}
        <strong>本页不下单</strong>
      </p>

      {!connected ? (
        <p className={styles.muted}>未连接网关。</p>
      ) : (
        <>
          <section className={styles.panel} style={{ marginBottom: "1rem" }}>
            <h2>执行批次</h2>
            <DataTable
              headers={[
                "执行 ID",
                "状态",
                "适配器",
                "业务日",
                "委托/成交",
                "组合",
              ]}
              empty="暂无执行记录"
              isEmpty={(listQ.data ?? []).length === 0}
            >
              {(listQ.data ?? []).map((row) => {
                const id = s(row.execution_id);
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
                        {statusZh(String(row.status))}
                      </StatusPill>
                    </td>
                    <td className="mono">{s(row.adapter)}</td>
                    <td className="mono">{s(row.as_of_date)}</td>
                    <td>
                      {n(row.order_count, 0)} / {n(row.fill_count, 0)}
                    </td>
                    <td className="mono">{s(row.portfolio_id)}</td>
                  </tr>
                );
              })}
            </DataTable>
          </section>

          <div className={styles.grid2} style={{ marginBottom: "1rem" }}>
            <section className={styles.panel}>
              <h2>委托事件</h2>
              <DataTable
                headers={["代码", "方向", "数量", "状态", "原因"]}
                empty="点击上方执行 ID 查看"
                isEmpty={orders.length === 0}
              >
                {orders.map((o, i) => (
                  <tr key={`${s(o.event_id)}-${i}`}>
                    <td className="mono">{s(o.symbol)}</td>
                    <td>{s(o.side)}</td>
                    <td>{n(o.qty, 0)}</td>
                    <td>
                      <StatusPill tone={toneFromStatus(String(o.status))}>
                        {statusZh(String(o.status))}
                      </StatusPill>
                    </td>
                    <td>{s(o.reason, "")}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
            <section className={styles.panel}>
              <h2>成交明细</h2>
              <DataTable
                headers={["代码", "方向", "数量", "价格", "金额"]}
                empty="无成交或未选择执行"
                isEmpty={fills.length === 0}
              >
                {fills.map((f, i) => (
                  <tr key={`${s(f.fill_id)}-${i}`}>
                    <td className="mono">{s(f.symbol)}</td>
                    <td>{s(f.side)}</td>
                    <td>{n(f.qty, 0)}</td>
                    <td>{n(f.price)}</td>
                    <td>{n(f.amount)}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
          </div>

          <section className={styles.panel}>
            <h2>未完成残差（open）</h2>
            <DataTable
              headers={["代码", "方向", "剩余数量", "原始数量", "原因", "策略"]}
              empty="无 open 残差"
              isEmpty={(pendQ.data ?? []).length === 0}
            >
              {(pendQ.data ?? []).map((p) => (
                <tr key={s(p.pending_id)}>
                  <td className="mono">{s(p.symbol)}</td>
                  <td>{s(p.side)}</td>
                  <td>{n(p.qty_remaining, 0)}</td>
                  <td>{n(p.qty_origin, 0)}</td>
                  <td>{s(p.last_reason, "")}</td>
                  <td className="mono">{s(p.strategy_version)}</td>
                </tr>
              ))}
            </DataTable>
          </section>
        </>
      )}
    </div>
  );
}
