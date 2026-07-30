import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Grid,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getOpsPipeline,
  listAlerts,
  listOpsActivity,
  type ClientConfig,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { DayStatusBar } from "../components/DayStatusBar";
import { PaperPipeline } from "../components/PaperPipeline";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import { saveSettings, type Settings } from "../state/settings";

const { Row, Col } = Grid;

export function OverviewPage({
  cfg,
  settings,
  connected,
  onSettingsChange,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
  onSettingsChange?: (s: Settings) => void;
}) {
  const snapAsOf = (day: string) => {
    const next = { ...settings, asOf: day };
    saveSettings(next);
    onSettingsChange?.(next);
  };

  const pipeQ = useQuery({
    queryKey: ["pipeline", cfg.apiBase],
    queryFn: () => getOpsPipeline(cfg),
    enabled: connected,
    refetchInterval: 30_000,
  });
  const alertQ = useQuery({
    queryKey: ["alerts", cfg.apiBase],
    queryFn: () => listAlerts(cfg, 8),
    enabled: connected,
  });
  const actQ = useQuery({
    queryKey: ["ops-activity-overview", cfg.apiBase],
    queryFn: () => listOpsActivity(cfg, 80),
    enabled: connected,
    refetchInterval: 30_000,
  });

  const stages = pipeQ.data?.stages ?? [];
  const counts = pipeQ.data?.counts ?? {};

  const countBars = [
    {
      id: "live",
      label: "LIVE",
      value: Number(counts.live_strategies ?? 0),
      color: "#165dff",
    },
    {
      id: "paper",
      label: "PAPER",
      value: Number(counts.paper_strategies ?? 0),
      color: "#0fc6c2",
    },
    {
      id: "draft",
      label: "草稿",
      value: Number(counts.draft_portfolios ?? 0),
      color: "#86909c",
    },
    {
      id: "approved",
      label: "已审",
      value: Number(counts.approved_portfolios ?? 0),
      color: "#00b42a",
    },
    {
      id: "exec",
      label: "执行",
      value: Number(counts.executions ?? 0),
      color: "#722ed1",
    },
    {
      id: "pending",
      label: "残差",
      value: Number(counts.open_pending ?? 0),
      color: "#ff7d00",
    },
    {
      id: "alerts",
      label: "告警",
      value: Number(counts.open_alerts ?? 0),
      color: "#f53f3f",
    },
  ];

  const kindMap: Record<string, number> = {};
  for (const e of actQ.data ?? []) {
    const k = String(e.kind ?? "other");
    kindMap[k] = (kindMap[k] || 0) + 1;
  }
  const kindBars = Object.entries(kindMap).map(([k, v]) => ({
    id: k,
    label: k,
    value: v,
    color: "#165dff",
  }));

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

      <DayStatusBar
        cfg={cfg}
        settings={settings}
        connected={connected}
        onSnapAsOf={snapAsOf}
      />

      <PaperPipeline
        cfg={cfg}
        settings={settings}
        connected={connected}
        onSnapAsOf={snapAsOf}
      />

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
        <Col xs={24} md={14}>
          <CategoryBars
            title="管道计数"
            subtitle="策略 / 组合 / 执行 / 告警"
            items={countBars}
            height={200}
            loading={pipeQ.isLoading}
          />
        </Col>
        <Col xs={24} md={10}>
          <CategoryBars
            title="近况活动构成"
            subtitle="最近批次按模块"
            items={kindBars}
            height={200}
            emptyHint="暂无活动"
            loading={actQ.isLoading}
          />
        </Col>
      </Row>

      <Space style={{ marginBottom: 8 }} align="center">
        <Typography.Title heading={6} style={{ margin: 0 }}>
          {zh.opsAlerts}
        </Typography.Title>
        <Link to="/ops" style={{ fontSize: 12 }}>
          查看全部 →
        </Link>
      </Space>
      <Table
        rowKey={(r) => s(r.alert_id ?? r.id ?? r.created_at)}
        size="small"
        loading={alertQ.isLoading}
        data={alertQ.data ?? []}
        pagination={false}
        columns={[
          {
            title: zh.level,
            width: 80,
            render: (_, r) => <Tag>{s(r.severity ?? r.level)}</Tag>,
          },
          { title: zh.source, render: (_, r) => s(r.source ?? r.job_id) },
          { title: zh.message, render: (_, r) => s(r.message ?? r.title) },
          { title: zh.time, width: 160, render: (_, r) => s(r.created_at) },
        ]}
      />
    </div>
  );
}
