import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Drawer,
  Grid,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listProcessBatches,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { PieChart } from "../components/PieChart";
import { STATUS_COLORS, countBy } from "../lib/chartAgg";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function ProcessPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [kind, setKind] = useState<string | undefined>();
  const [row, setRow] = useState<JsonMap | null>(null);
  const q = useQuery({
    queryKey: ["process", cfg.apiBase, kind],
    queryFn: () => listProcessBatches(cfg, { kind, limit: 100 }),
    enabled: connected,
  });

  const statusSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.status, "unknown"), {
        colors: STATUS_COLORS,
      }),
    [q.data],
  );

  const kindBars = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.process_kind, "?"), {
        defaultColor: "#722ed1",
      }),
    [q.data],
  );

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }}>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          加工批次
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder="process_kind"
          style={{ width: 160 }}
          value={kind}
          onChange={setKind}
          options={[
            { label: "equity_1d", value: "equity_1d" },
            { label: "index_1d", value: "index_1d" },
            { label: "tech_indicator", value: "tech_indicator" },
            { label: "fundamental_pit", value: "fundamental_pit" },
          ]}
        />
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        data_process · process_batch（复权 / 掩码 / 指标）·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>{" "}
        触发请用 <Link to="/ops/schedule">日更编排</Link>
      </Typography.Paragraph>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={10}>
          <PieChart
            title="状态"
            slices={statusSlices}
            height={180}
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={14}>
          <CategoryBars
            title="kind 分布"
            items={kindBars}
            height={180}
            loading={q.isLoading}
          />
        </Col>
      </Row>

      <Table
        rowKey={(r) => s(r.process_batch_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 25, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setRow(r) })}
        columns={[
          {
            title: "batch",
            dataIndex: "process_batch_id",
            width: 180,
            render: (v) => <code>{s(v)}</code>,
          },
          { title: "模块", dataIndex: "process_module", render: (v) => s(v) },
          { title: "kind", dataIndex: "process_kind", render: (v) => s(v) },
          {
            title: "状态",
            dataIndex: "status",
            width: 110,
            render: (v) => {
              const st = String(v || "");
              const color = st.includes("commit")
                ? "green"
                : st.includes("fail")
                  ? "red"
                  : "orange";
              return (
                <Tag size="small" color={color}>
                  {s(v)}
                </Tag>
              );
            },
          },
          { title: "创建", dataIndex: "created_at", render: (v) => s(v) },
          {
            title: "提交",
            dataIndex: "committed_at",
            render: (v) => s(v),
          },
          {
            title: "错误",
            dataIndex: "error_message",
            ellipsis: true,
            render: (v) => s(v, ""),
          },
        ]}
      />

      <Drawer
        width={560}
        title={row ? `加工 ${s(row.process_batch_id)}` : zh.detail}
        visible={Boolean(row)}
        onCancel={() => setRow(null)}
        footer={null}
      >
        {row ? (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <div>
              <Tag
                color={
                  String(row.status).includes("fail")
                    ? "red"
                    : String(row.status).includes("commit")
                      ? "green"
                      : "orange"
                }
              >
                {s(row.status)}
              </Tag>{" "}
              {s(row.process_module)} / {s(row.process_kind)}
            </div>
            {row.error_message ? (
              <Typography.Text type="error">{s(row.error_message)}</Typography.Text>
            ) : null}
            <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(row, null, 2)}
            </pre>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
