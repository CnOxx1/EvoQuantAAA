import { useMemo } from "react";
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
  getKill,
  isKillOn,
  listAlerts,
  listExecutions,
  listPortfolios,
  listStrategies,
  type ClientConfig,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function OverviewPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const stratQ = useQuery({
    queryKey: ["strategies", cfg.apiBase],
    queryFn: () => listStrategies(cfg),
    enabled: connected,
  });
  const portQ = useQuery({
    queryKey: ["portfolios", cfg.apiBase],
    queryFn: () => listPortfolios(cfg),
    enabled: connected,
  });
  const alertQ = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 20),
    enabled: connected,
  });
  const execQ = useQuery({
    queryKey: ["executions", cfg.apiBase],
    queryFn: () => listExecutions(cfg, 20),
    enabled: connected,
  });
  const killQ = useQuery({
    queryKey: ["kill-ov", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
  });

  const stages = useMemo(() => {
    const alerts = alertQ.data?.length ?? 0;
    const killOn = isKillOn(killQ.data);
    return [
      { name: "ingest", ok: true },
      { name: "process", ok: true },
      { name: "DQ", ok: alerts === 0 },
      { name: "signal", ok: (stratQ.data?.length ?? 0) > 0 },
      { name: "portfolio", ok: (portQ.data?.length ?? 0) > 0 },
      { name: "risk", ok: !killOn },
      { name: "exec", ok: (execQ.data?.length ?? 0) > 0 },
      { name: "ledger", ok: true },
    ];
  }, [alertQ.data, killQ.data, stratQ.data, portQ.data, execQ.data]);

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
      <Space wrap style={{ marginBottom: 12 }}>
        {stages.map((st) => (
          <Tag key={st.name} color={st.ok ? "green" : "orange"}>
            {st.name}
          </Tag>
        ))}
      </Space>
      <Row gutter={8} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title={zh.strategy} value={stratQ.data?.length ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title={zh.portfolio} value={portQ.data?.length ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title={zh.execBatch} value={execQ.data?.length ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title={zh.kill}
              value={isKillOn(killQ.data) ? "ON" : "OFF"}
              styleValue={{
                color: isKillOn(killQ.data) ? "var(--up)" : "var(--down)",
              }}
            />
          </Card>
        </Col>
      </Row>
      <Card title={zh.openAlerts} size="small">
        <Table
          rowKey={(r) => s(r.alert_id ?? r.code ?? JSON.stringify(r))}
          size="small"
          pagination={false}
          scroll={{ y: 360 }}
          data={alertQ.data ?? []}
          columns={[
            { title: zh.level, dataIndex: "severity", width: 80, render: (v) => s(v) },
            { title: zh.source, dataIndex: "source", width: 120, render: (v) => s(v) },
            {
              title: zh.code,
              dataIndex: "code",
              width: 120,
              render: (v) => <code>{s(v)}</code>,
            },
            { title: zh.message, dataIndex: "message", render: (v) => s(v) },
            { title: zh.status, dataIndex: "status", width: 90, render: (v) => s(v) },
          ]}
        />
      </Card>
    </div>
  );
}
