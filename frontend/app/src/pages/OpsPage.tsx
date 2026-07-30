import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Grid, Table, Tag, Typography } from "@arco-design/web-react";
import { listAlerts, type ClientConfig } from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { PieChart } from "../components/PieChart";
import { STATUS_COLORS, countBy } from "../lib/chartAgg";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

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

  const severitySlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.severity ?? r.level, "unknown"), {
        colors: {
          ...STATUS_COLORS,
          error: "#f53f3f",
          ERROR: "#f53f3f",
          warning: "#ff7d00",
          WARN: "#ff7d00",
          info: "#165dff",
          INFO: "#165dff",
        },
      }),
    [q.data],
  );

  const sourceBars = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.source, "?"), {
        defaultColor: "#165dff",
      }).slice(0, 10),
    [q.data],
  );

  const statusSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.status, "open"), {
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
        {zh.opsAlerts}
      </Typography.Title>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={8}>
          <PieChart
            title="级别"
            slices={severitySlices}
            height={180}
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={8}>
          <PieChart
            title="状态"
            slices={statusSlices}
            height={180}
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={8}>
          <CategoryBars
            title="来源 Top"
            items={sourceBars}
            height={180}
            loading={q.isLoading}
          />
        </Col>
      </Row>

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
