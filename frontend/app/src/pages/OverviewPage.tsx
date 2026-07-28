import { useQuery } from "@tanstack/react-query";
import {
  Card,
  Grid,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getOpsPipeline,
  listAlerts,
  type ClientConfig,
} from "../api/gateway";
import { PaperPipeline } from "../components/PaperPipeline";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function OverviewPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const pipeQ = useQuery({
    queryKey: ["pipeline", cfg.apiBase],
    queryFn: () => getOpsPipeline(cfg),
    enabled: connected,
    refetchInterval: 30_000,
  });
  const alertQ = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 20),
    enabled: connected,
  });

  const stages = pipeQ.data?.stages ?? [];
  const counts = pipeQ.data?.counts ?? {};

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnectedSettings}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.todayPipe}
      </Typography.Title>

      <PaperPipeline cfg={cfg} settings={settings} connected={connected} />

      <Typography.Title heading={6}>{zh.pipeline}</Typography.Title>
      <Space wrap style={{ marginBottom: 16 }}>
        {stages.map((st) => (
          <Tag key={st.name} color={st.ok ? "green" : "red"}>
            {st.name}: {st.ok ? zh.pipeOk : zh.pipeBad}
            {st.detail ? ` (${st.detail})` : ""}
          </Tag>
        ))}
        {pipeQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : null}
      </Space>

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="LIVE"
              value={counts.live_strategies ?? 0}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="PAPER" value={counts.paper_strategies ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={zh.pending}
              value={counts.open_pending ?? 0}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={zh.openAlerts}
              value={counts.open_alerts ?? 0}
            />
          </Card>
        </Col>
      </Row>

      <Typography.Title heading={6}>{zh.opsAlerts}</Typography.Title>
      <Table
        rowKey={(r) => s(r.alert_id ?? r.id ?? r.created_at)}
        size="small"
        loading={alertQ.isLoading}
        data={alertQ.data ?? []}
        columns={[
          {
            title: zh.level,
            width: 80,
            render: (_, r) => <Tag>{s(r.severity ?? r.level)}</Tag>,
          },
          { title: zh.source, render: (_, r) => s(r.source ?? r.job_id) },
          { title: zh.message, render: (_, r) => s(r.message ?? r.title) },
          { title: zh.time, render: (_, r) => s(r.created_at) },
        ]}
      />
    </div>
  );
}
