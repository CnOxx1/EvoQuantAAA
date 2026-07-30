import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Drawer,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listCostParams,
  listPromotionGateParams,
  listPromotionGateResults,
  listRiskLimits,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function ParamsPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [gateRow, setGateRow] = useState<JsonMap | null>(null);

  const costQ = useQuery({
    queryKey: ["cost-params", cfg.apiBase],
    queryFn: () => listCostParams(cfg),
    enabled: connected,
  });
  const riskQ = useQuery({
    queryKey: ["risk-limits", cfg.apiBase],
    queryFn: () => listRiskLimits(cfg),
    enabled: connected,
  });
  const gateParamQ = useQuery({
    queryKey: ["gate-params", cfg.apiBase],
    queryFn: () => listPromotionGateParams(cfg),
    enabled: connected,
  });
  const gateResQ = useQuery({
    queryKey: ["gate-results", cfg.apiBase],
    queryFn: () => listPromotionGateResults(cfg, 80),
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
        参考参数
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        cost_params · risk_limits · promotion_gate_* ·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>{" "}
        参数变更走迁移 / 运维，不在 UI 写入
      </Typography.Paragraph>

      <Tabs defaultActiveTab="cost">
        <Tabs.TabPane key="cost" title="费用 / 冲击">
          <Table
            rowKey={(r) => s(r.version)}
            size="small"
            loading={costQ.isLoading}
            data={costQ.data ?? []}
            columns={[
              {
                title: "version",
                dataIndex: "version",
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "佣金",
                dataIndex: "commission_rate",
                render: (v) => n(Number(v) * 10000, 2) + "‱",
              },
              {
                title: "印花税",
                dataIndex: "stamp_tax_rate",
                render: (v) => n(Number(v) * 10000, 2) + "‱",
              },
              {
                title: "滑点",
                dataIndex: "slippage_rate",
                render: (v) => n(Number(v) * 10000, 2) + "‱",
              },
              {
                title: "冲击",
                render: (_, r) =>
                  `${s(r.impact_model, "flat")} · coef=${s(r.impact_coef, "0")}`,
              },
              {
                title: "整手",
                dataIndex: "lot_size",
                width: 70,
                render: (v) => n(v, 0),
              },
              {
                title: "说明",
                render: (_, r) => s((r.meta as JsonMap | undefined)?.note, ""),
              },
            ]}
          />
        </Tabs.TabPane>

        <Tabs.TabPane key="risk" title="风控限额">
          <Table
            rowKey={(r) => s(r.version)}
            size="small"
            loading={riskQ.isLoading}
            data={riskQ.data ?? []}
            columns={[
              {
                title: "version",
                dataIndex: "version",
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "单票上限",
                dataIndex: "max_single_weight",
                render: (v) => n(Number(v) * 100, 1) + "%",
              },
              {
                title: "持仓数",
                render: (_, r) => `${s(r.min_names)}–${s(r.max_names)}`,
              },
              {
                title: "总敞口",
                dataIndex: "max_gross_exposure",
                render: (v) => n(Number(v) * 100, 1) + "%",
              },
              {
                title: "行业上限",
                dataIndex: "max_industry_weight",
                render: (v) => (v == null ? "—" : n(Number(v) * 100, 1) + "%"),
              },
              {
                title: "ADV 参与",
                dataIndex: "max_adv_participation",
                render: (v) => (v == null ? "—" : n(Number(v) * 100, 1) + "%"),
              },
              {
                title: "说明",
                render: (_, r) => s((r.meta as JsonMap | undefined)?.note, ""),
              },
            ]}
          />
        </Tabs.TabPane>

        <Tabs.TabPane key="gates" title="晋升门阈值">
          <Table
            rowKey={(r) => s(r.version)}
            size="small"
            loading={gateParamQ.isLoading}
            data={gateParamQ.data ?? []}
            expandedRowRender={(r) => (
              <pre style={{ fontSize: 11, margin: 0 }}>
                {JSON.stringify(r.thresholds ?? {}, null, 2)}
              </pre>
            )}
            columns={[
              {
                title: "version",
                dataIndex: "version",
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "说明",
                render: (_, r) => s((r.meta as JsonMap | undefined)?.note, ""),
              },
              { title: "创建", dataIndex: "created_at", render: (v) => s(v) },
            ]}
          />
        </Tabs.TabPane>

        <Tabs.TabPane key="results" title="晋升评估记录">
          <Table
            rowKey={(r) => s(r.gate_id)}
            size="small"
            loading={gateResQ.isLoading}
            data={gateResQ.data ?? []}
            pagination={{ pageSize: 15, size: "mini" }}
            onRow={(r) => ({ onClick: () => setGateRow(r) })}
            columns={[
              {
                title: "gate",
                dataIndex: "gate_id",
                width: 140,
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "策略",
                dataIndex: "strategy_version",
                render: (v) => s(v),
              },
              { title: "目标", dataIndex: "to_status", width: 100, render: (v) => s(v) },
              {
                title: "结果",
                width: 100,
                render: (_, r) => (
                  <Tag size="small" color={r.passed ? "green" : r.skipped ? "orange" : "red"}>
                    {r.skipped ? "skip" : r.passed ? "pass" : "fail"}
                  </Tag>
                ),
              },
              {
                title: "门版本",
                dataIndex: "gate_version",
                render: (v) => s(v),
              },
              { title: "时间", dataIndex: "created_at", render: (v) => s(v) },
            ]}
          />
        </Tabs.TabPane>
      </Tabs>

      <Drawer
        width={560}
        title={gateRow ? `评估 ${s(gateRow.gate_id)}` : "评估详情"}
        visible={Boolean(gateRow)}
        onCancel={() => setGateRow(null)}
        footer={null}
      >
        {gateRow ? (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <Typography.Text>
              {s(gateRow.strategy_version)} → {s(gateRow.to_status)}
            </Typography.Text>
            <Typography.Text bold>metrics</Typography.Text>
            <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(gateRow.metrics ?? {}, null, 2)}
            </pre>
            <Typography.Text bold>checks</Typography.Text>
            <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(gateRow.checks ?? {}, null, 2)}
            </pre>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
