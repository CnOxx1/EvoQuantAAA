import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Space, Table, Tag, Typography } from "@arco-design/web-react";
import {
  getBacktestRun,
  listBacktestRuns,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { fmtPct, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function BacktestPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [id, setId] = useState("");
  const q = useQuery({
    queryKey: ["backtest", cfg.apiBase],
    queryFn: () => listBacktestRuns(cfg, { limit: 50 }),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["backtest-detail", cfg.apiBase, id],
    queryFn: () => getBacktestRun(cfg, id),
    enabled: connected && Boolean(id),
  });

  const d = detailQ.data;
  const nav = (d?.nav as JsonMap[] | undefined) ?? [];
  const trades = (d?.trades as JsonMap[] | undefined) ?? [];

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
        回测中心
      </Typography.Title>
      <Table
        rowKey={(r) => s(r.run_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setId(s(r.run_id, "")) })}
        columns={[
          { title: "run", dataIndex: "run_id", width: 160, render: (v) => s(v) },
          { title: "策略", dataIndex: "strategy_code", width: 120, render: (v) => s(v) },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          {
            title: "区间",
            width: 180,
            render: (_, r) => `${s(r.start_date)} → ${s(r.end_date)}`,
          },
          {
            title: "收益",
            dataIndex: "total_return",
            width: 90,
            render: (v) => fmtPct(v).text,
          },
          {
            title: "回撤",
            dataIndex: "max_drawdown",
            width: 90,
            render: (v) => fmtPct(v).text,
          },
          { title: "成交笔数", dataIndex: "trade_count", width: 80, render: (v) => s(v) },
          { title: "创建", dataIndex: "created_at", width: 160, render: (v) => s(v) },
        ]}
      />
      <Drawer
        width={720}
        title={`回测 ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">加载中…</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <Space wrap>
              <Tag>{s(d.strategy_code)}</Tag>
              <Tag color="arcoblue">{s(d.status)}</Tag>
              <Typography.Text type="secondary">
                终值净值 {s(d.final_nav)} · 收益 {fmtPct(d.total_return).text}
              </Typography.Text>
            </Space>
            <Typography.Text bold>净值曲线（{nav.length}）</Typography.Text>
            <Table
              rowKey={(r) => s(r.trade_date)}
              size="mini"
              pagination={{ pageSize: 8, size: "mini" }}
              data={nav}
              columns={[
                { title: "日期", dataIndex: "trade_date", render: (v) => s(v) },
                { title: "NAV", dataIndex: "nav", render: (v) => s(v) },
                { title: "现金", dataIndex: "cash", render: (v) => s(v) },
                { title: "市值", dataIndex: "market_value", render: (v) => s(v) },
                { title: "基准", dataIndex: "benchmark_nav", render: (v) => s(v) },
              ]}
            />
            <Typography.Text bold>成交（{trades.length}）</Typography.Text>
            <Table
              rowKey={(r) =>
                `${s(r.trade_date)}-${s(r.symbol)}-${s(r.side)}-${s(r.shares)}-${s(r.price)}`
              }
              size="mini"
              pagination={{ pageSize: 8, size: "mini" }}
              data={trades}
              columns={[
                { title: "日期", dataIndex: "trade_date", render: (v) => s(v) },
                { title: "代码", dataIndex: "symbol", render: (v) => s(v) },
                { title: "方向", dataIndex: "side", render: (v) => s(v) },
                { title: "股数", dataIndex: "shares", render: (v) => s(v) },
                { title: "价格", dataIndex: "price", render: (v) => s(v) },
                { title: "金额", dataIndex: "amount", render: (v) => s(v) },
              ]}
            />
          </Space>
        ) : (
          <Typography.Text type="secondary">无详情</Typography.Text>
        )}
      </Drawer>
    </div>
  );
}
