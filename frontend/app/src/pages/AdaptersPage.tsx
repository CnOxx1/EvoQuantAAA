import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Grid, Table, Tag, Typography } from "@arco-design/web-react";
import { listExecutionAdapters, type ClientConfig } from "../api/gateway";
import { PieChart } from "../components/PieChart";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function AdaptersPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["adapters", cfg.apiBase],
    queryFn: () => listExecutionAdapters(cfg),
    enabled: connected,
  });

  const fillSlices = useMemo(() => {
    const rows = q.data ?? [];
    let allow = 0;
    let block = 0;
    for (const r of rows) {
      if (r.allow_fills) allow += 1;
      else block += 1;
    }
    return [
      { id: "allow", label: "可成交", value: allow, color: "#00b42a" },
      { id: "block", label: "不成交", value: block, color: "#f53f3f" },
    ].filter((x) => x.value > 0);
  }, [q.data]);

  const enabledSlices = useMemo(() => {
    const rows = q.data ?? [];
    let on = 0;
    let off = 0;
    for (const r of rows) {
      if (r.enabled) on += 1;
      else off += 1;
    }
    return [
      { id: "on", label: "启用", value: on, color: "#165dff" },
      { id: "off", label: "停用", value: off, color: "#86909c" },
    ].filter((x) => x.value > 0);
  }, [q.data]);

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
        执行适配器
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        execution/adapters · paper 可成交；stub / live_gated 永不成交 ·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>{" "}
        （UI 禁 live_gated）
      </Typography.Paragraph>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={12}>
          <PieChart
            title="启用"
            slices={enabledSlices}
            height={140}
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={12}>
          <PieChart
            title="成交许可"
            slices={fillSlices}
            height={140}
            loading={q.isLoading}
          />
        </Col>
      </Row>
      <Table
        rowKey={(r) => s(r.kind)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        columns={[
          {
            title: "kind",
            dataIndex: "kind",
            width: 140,
            render: (v) => <code>{s(v)}</code>,
          },
          {
            title: "启用",
            dataIndex: "enabled",
            width: 80,
            render: (v) => (
              <Tag size="small" color={v ? "green" : "gray"}>
                {v ? "是" : "否"}
              </Tag>
            ),
          },
          {
            title: "允许成交",
            dataIndex: "allow_fills",
            width: 100,
            render: (v) => (
              <Tag size="small" color={v ? "green" : "orangered"}>
                {v ? "是" : "否"}
              </Tag>
            ),
          },
          {
            title: "要求 live 环境",
            dataIndex: "require_live_env",
            width: 120,
            render: (v) => (v ? "是" : "否"),
          },
          {
            title: "说明",
            render: (_, r) => {
              const meta = r.meta as Record<string, unknown> | undefined;
              return s(meta?.note ?? "");
            },
          },
          { title: "创建", dataIndex: "created_at", render: (v) => s(v) },
        ]}
      />
    </div>
  );
}
