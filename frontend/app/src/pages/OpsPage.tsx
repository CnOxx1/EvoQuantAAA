import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Typography } from "@arco-design/web-react";
import { listAlerts, type ClientConfig } from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function OpsPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 100),
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
        {zh.opsAlerts}
      </Typography.Title>
      <Table
        rowKey={(r) => `${s(r.alert_id)}-${s(r.code)}-${s(r.message)}`}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        columns={[
          {
            title: zh.level,
            width: 90,
            render: (_, r) => (
              <Tag
                color={String(r.severity).includes("WARN") ? "orange" : "blue"}
              >
                {s(r.severity)}
              </Tag>
            ),
          },
          { title: zh.source, render: (_, r) => s(r.source) },
          { title: zh.code, render: (_, r) => <code>{s(r.code)}</code> },
          { title: zh.message, render: (_, r) => s(r.message) },
          { title: zh.status, width: 90, render: (_, r) => s(r.status) },
        ]}
      />
    </div>
  );
}
