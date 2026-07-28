import { useQuery } from "@tanstack/react-query";
import { listAlerts, type ClientConfig } from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill } from "../components/StatusPill";
import { parseJsonField, s, statusZh } from "../lib/format";
import styles from "./pages.module.css";

export function OpsPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 50),
    enabled: connected,
  });

  return (
    <div>
      <h1>运维告警</h1>
      <p className="lede">
        数据来自 <code className="mono">/v1/ops/alerts</code>
        。覆盖度矩阵与 schedule 触发仍走 CLI（后续可接）。
      </p>

      {!connected ? (
        <p className={styles.muted}>未连接网关。</p>
      ) : (
        <section className={styles.panel}>
          <h2>告警列表（{q.data?.length ?? 0}）</h2>
          <DataTable
            headers={["级别", "标题/内容", "来源", "时间"]}
            empty="当前无告警记录"
            isEmpty={(q.data ?? []).length === 0}
          >
            {(q.data ?? []).map((a) => {
              const meta = parseJsonField(a.meta_json ?? a.meta);
              return (
                <tr key={s(a.alert_id ?? a.created_at)}>
                  <td>
                    <StatusPill
                      tone={
                        String(a.severity).toLowerCase() === "error"
                          ? "failed"
                          : String(a.severity).toLowerCase() === "warning"
                            ? "degraded"
                            : "info"
                      }
                    >
                      {statusZh(String(a.severity ?? "—"))}
                    </StatusPill>
                  </td>
                  <td>
                    <div>{s(a.title ?? a.message)}</div>
                    {a.title && a.message ? (
                      <div className={styles.muted}>{s(a.message)}</div>
                    ) : null}
                  </td>
                  <td className="mono">
                    {s(a.source ?? meta.source ?? a.job_id)}
                  </td>
                  <td className="mono">{s(a.created_at)}</td>
                </tr>
              );
            })}
          </DataTable>
        </section>
      )}
    </div>
  );
}
