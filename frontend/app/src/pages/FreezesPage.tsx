import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Drawer,
  Grid,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listEvidenceFreezes,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { PieChart } from "../components/PieChart";
import { STATUS_COLORS, countBy } from "../lib/chartAgg";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function FreezesPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [row, setRow] = useState<JsonMap | null>(null);
  const q = useQuery({
    queryKey: ["freezes", cfg.apiBase],
    queryFn: () => listEvidenceFreezes(cfg, 80),
    enabled: connected,
  });

  const statusSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.status, "unknown"), {
        colors: STATUS_COLORS,
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
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.freezes}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        research_lab · research_evidence_freeze（walk-forward OOS）·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>
      </Typography.Paragraph>
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={10} lg={8}>
          <PieChart
            title="冻结状态"
            slices={statusSlices}
            height={160}
            emptyHint="暂无冻结"
            loading={q.isLoading}
          />
        </Col>
      </Row>
      <Table
        rowKey={(r) => s(r.freeze_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setRow(r) })}
        columns={[
          {
            title: "freeze",
            dataIndex: "freeze_id",
            width: 180,
            render: (v) => <code>{s(v)}</code>,
          },
          { title: "evidence_run", dataIndex: "evidence_run_id", render: (v) => s(v) },
          { title: "universe", dataIndex: "universe_code", render: (v) => s(v) },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
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
        width={480}
        title={row ? `冻结 ${s(row.freeze_id)}` : zh.detail}
        visible={Boolean(row)}
        onCancel={() => setRow(null)}
        footer={null}
      >
        {row ? (
          <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
            {JSON.stringify(row, null, 2)}
          </pre>
        ) : null}
      </Drawer>
    </div>
  );
}
