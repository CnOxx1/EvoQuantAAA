import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, Grid, Space, Statistic, Tag, Typography } from "@arco-design/web-react";
import { listModules, type ClientConfig } from "../api/gateway";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function ModulesPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const nav = useNavigate();
  const q = useQuery({
    queryKey: ["modules", cfg.apiBase],
    queryFn: () => listModules(cfg),
    enabled: connected,
  });

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  const modules = q.data?.modules ?? [];
  const counts = q.data?.counts ?? {};

  return (
    <div className="page">
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        后端模块地图
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        只读聚合各模块表规模；点击进入对应运维页。
      </Typography.Paragraph>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {(
          [
            ["ingest_batch", "取数批次"],
            ["signal_batch", "信号批次"],
            ["strategy_version", "策略版本"],
            ["execution_run", "执行批次"],
          ] as const
        ).map(([key, title]) => (
          <Col key={key} xs={12} sm={6}>
            <Card size="small">
              <Statistic title={title} value={Number(counts[key] ?? 0)} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[12, 12]}>
        {modules.map((m) => (
          <Col key={m.id} xs={24} sm={12} md={8} lg={6}>
            <Card
              size="small"
              hoverable
              onClick={() => nav(m.route)}
              style={{ cursor: "pointer", height: "100%" }}
              title={
                <Space size={6}>
                  <span>{m.name}</span>
                  <Tag size="small">{m.id}</Tag>
                </Space>
              }
              extra={
                m.count != null ? (
                  <Typography.Text type="secondary">{n(m.count, 0)}</Typography.Text>
                ) : null
              }
            >
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {m.desc}
              </Typography.Text>
              <div style={{ marginTop: 8 }}>
                <Typography.Text code style={{ fontSize: 11 }}>
                  {s(m.path)}
                </Typography.Text>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
