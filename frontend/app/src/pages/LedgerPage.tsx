import { useQuery } from "@tanstack/react-query";
import { getLedger, type ClientConfig } from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import { n, s, statusZh } from "../lib/format";
import type { Settings } from "../state/settings";
import styles from "./pages.module.css";

export function LedgerPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, settings.asOf],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });

  const positions = Array.isArray(q.data?.positions)
    ? (q.data!.positions as Array<Record<string, unknown>>)
    : [];
  const sellable = q.data?.sellable as
    | { rows?: Array<Record<string, unknown>>; cash?: number }
    | undefined;
  const sellRows = Array.isArray(sellable?.rows) ? sellable!.rows! : [];

  return (
    <div>
      <h1>账本</h1>
      <p className="lede">
        账户 <code className="mono">{settings.accountId}</code> · 业务日{" "}
        {settings.asOf} · 数据来自{" "}
        <code className="mono">/v1/ledger/accounts/{"{id}"}</code>
      </p>

      {!connected ? (
        <p className={styles.muted}>未连接网关，请先到「设置」检查 API 地址。</p>
      ) : q.isError ? (
        <p className={styles.muted}>读取失败：{String(q.error)}</p>
      ) : (
        <>
          <div className={styles.grid2} style={{ marginBottom: "1rem" }}>
            <section className={styles.panel}>
              <h2>账户概览</h2>
              <ul className={styles.summary}>
                <li>
                  状态：{" "}
                  <StatusPill tone={toneFromStatus(String(q.data?.status))}>
                    {statusZh(String(q.data?.status ?? "—"))}
                  </StatusPill>
                </li>
                <li>
                  币种： <strong>{s(q.data?.currency, "CNY")}</strong>
                </li>
                <li>
                  期初现金： <strong>{n(q.data?.opening_cash)}</strong>
                </li>
                <li>
                  当前现金： <strong>{n(q.data?.cash)}</strong>
                </li>
                <li>
                  持仓只数： <strong>{positions.length}</strong>
                </li>
              </ul>
            </section>
            <section className={styles.panel}>
              <h2>说明</h2>
              <p className={styles.muted}>
                持仓来自 ledger_balance；若传入业务日，网关会附带 T+1
                可卖报告（sellable）。本页只读，不过账。
              </p>
            </section>
          </div>

          <section className={styles.panel} style={{ marginBottom: "1rem" }}>
            <h2>持仓余额</h2>
            <DataTable
              headers={["代码", "数量"]}
              empty="无持仓"
              isEmpty={positions.length === 0}
            >
              {positions.map((p) => (
                <tr key={s(p.symbol)}>
                  <td className="mono">{s(p.symbol)}</td>
                  <td>{n(p.qty, 0)}</td>
                </tr>
              ))}
            </DataTable>
          </section>

          <section className={styles.panel}>
            <h2>可卖（T+1）</h2>
            <DataTable
              headers={["代码", "可卖数量", "其他"]}
              empty="无可用可卖明细（或账户无持仓）"
              isEmpty={sellRows.length === 0}
            >
              {sellRows.map((r, i) => (
                <tr key={`${s(r.symbol)}-${i}`}>
                  <td className="mono">{s(r.symbol)}</td>
                  <td>{n(r.sellable_qty ?? r.qty ?? r.available, 0)}</td>
                  <td className="mono">
                    {s(r.strategy_version ?? r.note, "")}
                  </td>
                </tr>
              ))}
            </DataTable>
          </section>
        </>
      )}
    </div>
  );
}
