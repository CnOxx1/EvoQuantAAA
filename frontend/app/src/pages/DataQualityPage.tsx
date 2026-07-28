import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Select, Space, Table, Tag, Typography } from "@arco-design/web-react";
import {
  getDqRun,
  listDqGates,
  listDqRuns,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function DataQualityPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [scope, setScope] = useState<string | undefined>();
  const [id, setId] = useState("");

  const runsQ = useQuery({
    queryKey: ["dq-runs", cfg.apiBase, scope],
    queryFn: () => listDqRuns(cfg, { scope, limit: 50 }),
    enabled: connected,
  });
  const gatesQ = useQuery({
    queryKey: ["dq-gates", cfg.apiBase, scope],
    queryFn: () => listDqGates(cfg, { scope, limit: 50 }),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["dq-detail", cfg.apiBase, id],
    queryFn: () => getDqRun(cfg, id),
    enabled: connected && Boolean(id),
  });

  const results = (detailQ.data?.results as JsonMap[] | undefined) ?? [];

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }}>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          数据质量
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder="scope"
          style={{ width: 120 }}
          value={scope}
          onChange={setScope}
          options={[
            { label: "CORE", value: "CORE" },
            { label: "ALPHA", value: "ALPHA" },
          ]}
        />
      </Space>
      <Typography.Text bold>门禁</Typography.Text>
      <Table
        style={{ marginTop: 8, marginBottom: 16 }}
        rowKey={(r) =>
          `${s(r.scope)}-${s(r.start_date)}-${s(r.end_date)}-${s(r.factor_type)}`
        }
        size="small"
        loading={gatesQ.isLoading}
        data={gatesQ.data ?? []}
        pagination={{ pageSize: 8, size: "mini" }}
        columns={[
          { title: "scope", dataIndex: "scope", render: (v) => s(v) },
          {
            title: "区间",
            render: (_, r) => `${s(r.start_date)} → ${s(r.end_date)}`,
          },
          {
            title: "状态",
            dataIndex: "status",
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          { title: "dq_run", dataIndex: "dq_run_id", render: (v) => s(v) },
          { title: "更新", dataIndex: "updated_at", render: (v) => s(v) },
        ]}
      />
      <Typography.Text bold>DQ 运行</Typography.Text>
      <Table
        style={{ marginTop: 8 }}
        rowKey={(r) => s(r.dq_run_id)}
        size="small"
        loading={runsQ.isLoading}
        data={runsQ.data ?? []}
        pagination={{ pageSize: 15, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setId(s(r.dq_run_id, "")) })}
        columns={[
          { title: "run", dataIndex: "dq_run_id", width: 160, render: (v) => s(v) },
          { title: "scope", dataIndex: "scope", width: 80, render: (v) => s(v) },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          {
            title: "区间",
            render: (_, r) => `${s(r.start_date)} → ${s(r.end_date)}`,
          },
          { title: "创建", dataIndex: "created_at", render: (v) => s(v) },
        ]}
      />
      <Drawer
        width={640}
        title={`DQ ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        <Table
          rowKey={(r) => `${s(r.rule_code)}-${s(r.checked_at)}-${s(r.message)}`}
          size="mini"
          loading={detailQ.isLoading}
          data={results}
          pagination={{ pageSize: 12, size: "mini" }}
          columns={[
            { title: "规则", dataIndex: "rule_code", render: (v) => s(v) },
            { title: "级别", dataIndex: "severity", render: (v) => s(v) },
            { title: "状态", dataIndex: "status", render: (v) => s(v) },
            { title: "消息", dataIndex: "message", render: (v) => s(v) },
          ]}
        />
      </Drawer>
    </div>
  );
}
