import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Typography } from "@arco-design/web-react";
import { listResearchRuns, type ClientConfig } from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function ResearchPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["research", cfg.apiBase],
    queryFn: () => listResearchRuns(cfg, 50),
    enabled: connected,
  });

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.research}
      </Typography.Title>
      <Table
        rowKey={(r) => s(r.run_id ?? r.research_run_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        columns={[
          {
            title: "run",
            render: (_, r) => (
              <code>{s(r.run_id ?? r.research_run_id)}</code>
            ),
          },
          { title: "kind", render: (_, r) => s(r.kind) },
          { title: zh.factor, render: (_, r) => s(r.factor_code ?? r.factor) },
          {
            title: zh.conclusion,
            width: 100,
            render: (_, r) => <Tag>{s(r.status ?? r.conclusion)}</Tag>,
          },
        ]}
      />
    </div>
  );
}
