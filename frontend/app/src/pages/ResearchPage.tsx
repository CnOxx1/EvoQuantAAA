import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  listResearchRuns,
  type ClientConfig,
  type ResearchRunRow,
} from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill, toneFromStatus } from "../components/StatusPill";
import { parseJsonField, s, statusZh } from "../lib/format";
import styles from "./pages.module.css";

export function ResearchPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  connected: boolean;
}) {
  const [selected, setSelected] = useState<ResearchRunRow | null>(null);
  const q = useQuery({
    queryKey: ["research-runs", cfg.apiBase],
    queryFn: () => listResearchRuns(cfg, 50),
    enabled: connected,
  });

  const meta = parseJsonField(selected?.meta ?? selected?.meta_json);

  return (
    <div>
      <h1>研究运行</h1>
      <p className="lede">
        数据来自 <code className="mono">/v1/research/runs</code>
        。证据冻结详情后续可再加深。
      </p>

      {!connected ? (
        <p className={styles.muted}>未连接网关。</p>
      ) : (
        <div className={styles.grid2}>
          <section className={styles.panel}>
            <h2>运行列表（{q.data?.length ?? 0}）</h2>
            <DataTable
              headers={["运行 ID", "因子", "Universe", "区间", "状态"]}
              empty="暂无研究运行"
              isEmpty={(q.data ?? []).length === 0}
            >
              {(q.data ?? []).map((row) => {
                const id = s(row.run_id);
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
                    <td className="mono">{s(row.factor_code)}</td>
                    <td className="mono">{s(row.universe_code)}</td>
                    <td className="mono">
                      {s(row.start_date)} ~ {s(row.end_date)}
                    </td>
                    <td>
                      <StatusPill tone={toneFromStatus(String(row.status))}>
                        {statusZh(String(row.status))}
                      </StatusPill>
                    </td>
                  </tr>
                );
              })}
            </DataTable>
          </section>

          <section className={styles.panel}>
            <h2>元数据</h2>
            {!selected ? (
              <p className={styles.muted}>点击左侧运行 ID 查看 meta。</p>
            ) : (
              <>
                <ul className={styles.summary}>
                  <li>
                    运行： <code className="mono">{s(selected.run_id)}</code>
                  </li>
                  <li>
                    因子： <strong>{s(selected.factor_code)}</strong>
                  </li>
                  <li>
                    状态： {statusZh(String(selected.status))}
                  </li>
                </ul>
                <pre className={styles.result}>
                  {JSON.stringify(meta, null, 2)}
                </pre>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
