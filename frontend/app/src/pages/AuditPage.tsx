import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Space, Table, Tag, Typography } from "@arco-design/web-react";
import { listAuditLogs, type ClientConfig, type JsonMap } from "../api/gateway";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function AuditPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [row, setRow] = useState<JsonMap | null>(null);
  const q = useQuery({
    queryKey: ["audit", cfg.apiBase],
    queryFn: () => listAuditLogs(cfg, 100),
    enabled: connected,
  });

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        API 审计
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        api_audit_log · 网关写操作留痕
      </Typography.Paragraph>
      <Table
        rowKey={(r) => s(r.audit_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 25, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setRow(r) })}
        columns={[
          {
            title: "时间",
            dataIndex: "created_at",
            width: 180,
            render: (v) => s(v),
          },
          { title: "actor", dataIndex: "actor", width: 100, render: (v) => s(v) },
          {
            title: "方法",
            dataIndex: "method",
            width: 70,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          { title: "路径", dataIndex: "path", render: (v) => <code>{s(v)}</code> },
          {
            title: "状态",
            dataIndex: "status_code",
            width: 70,
            render: (v) => (
              <Tag size="small" color={Number(v) < 400 ? "green" : "red"}>
                {s(v)}
              </Tag>
            ),
          },
        ]}
      />
      <Drawer
        width={560}
        title={row ? `审计 ${s(row.audit_id)}` : "详情"}
        visible={Boolean(row)}
        onCancel={() => setRow(null)}
        footer={null}
      >
        {row ? (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Typography.Text bold>request</Typography.Text>
            <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(row.request ?? {}, null, 2)}
            </pre>
            <Typography.Text bold>result</Typography.Text>
            <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(row.result ?? {}, null, 2)}
            </pre>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
