import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  DatePicker,
  Drawer,
  Form,
  Input,
  Message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getBacktestRun,
  listBacktestRuns,
  runBacktest,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { toLinePoints } from "../lib/chartTime";
import { fmtPct, s } from "../lib/format";
import { zh } from "../i18n/zh";
import type { Settings } from "../state/settings";

function daysAgo(n: number, end?: string): string {
  const base = end ? new Date(`${end}T00:00:00`) : new Date();
  base.setDate(base.getDate() - n);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`;
}

export function BacktestPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const liveLocked = settings.env === "live";
  const [id, setId] = useState("");
  const [runOpen, setRunOpen] = useState(false);
  const [range, setRange] = useState<string[]>([
    daysAgo(60, settings.asOf),
    settings.asOf || daysAgo(0),
  ]);
  const [factor, setFactor] = useState("MOM_20");
  const [universe, setUniverse] = useState("TOP100");
  const [topN, setTopN] = useState("20");
  const [reb, setReb] = useState("20");

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

  const runMut = useMutation({
    mutationFn: () =>
      runBacktest(cfg, {
        strategy: "FACTOR_TOP_N",
        start: range[0],
        end: range[1],
        universe,
        factor,
        top_n: Number(topN) || 20,
        rebalance_days: Number(reb) || 20,
        factor_type: "qfq",
        require_dq: true,
      }),
    onSuccess: (data) => {
      Message.success(`${zh.btOk} · ${s(data.run_id)}`);
      setRunOpen(false);
      setId(s(data.run_id, ""));
      void qc.invalidateQueries({ queryKey: ["backtest"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const d = detailQ.data;
  const nav = (d?.nav as JsonMap[] | undefined) ?? [];
  const trades = (d?.trades as JsonMap[] | undefined) ?? [];

  const navLines = useMemo(() => {
    const strategy = toLinePoints(nav, "trade_date", "nav");
    const bench = toLinePoints(nav, "trade_date", "benchmark_nav");
    const lines = [
      { id: "策略 NAV", color: "#165dff", data: strategy, lineWidth: 2 as const },
    ];
    if (bench.some((p) => p.value > 0)) {
      lines.push({
        id: "基准",
        color: "#86909c",
        data: bench,
        lineWidth: 2 as const,
      });
    }
    return lines;
  }, [nav]);

  const ddHist = useMemo(() => {
    if (nav.length < 2) return undefined;
    let peak = Number(nav[0]?.nav) || 0;
    const pts: { time: string | number; value: number; color?: string }[] = [];
    for (const r of nav) {
      const v = Number(r.nav);
      const t = String(r.trade_date || "").slice(0, 10);
      if (!t || !Number.isFinite(v)) continue;
      peak = Math.max(peak, v);
      const dd = peak > 0 ? (v / peak - 1) * 100 : 0;
      pts.push({
        time: t,
        value: dd,
        color: dd < 0 ? "#f53f3f99" : "#00b42a55",
      });
    }
    return { id: "回撤%", data: pts };
  }, [nav]);

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 8 }} wrap>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          回测中心
        </Typography.Title>
        <Button
          type="primary"
          size="small"
          disabled={liveLocked}
          title={liveLocked ? zh.liveLocked : undefined}
          onClick={() => setRunOpen(true)}
        >
          跑 FACTOR_TOP_N
        </Button>
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        区间需 DQ gate passed；结果可在策略晋升 BACKTESTED 时选用。
      </Typography.Paragraph>
      <Alert
        type="info"
        style={{ marginBottom: 12 }}
        content={
          <>
            若报错 DQ / quality gate：先看{" "}
            <Link to="/data/quality">数据质量</Link>，或在{" "}
            <Link to="/ops/schedule">日更编排</Link> 强制跑一轮（需业务日）。
            live 环境会锁定本页写操作。
          </>
        }
      />
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
        width={860}
        title={`回测 ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <Space wrap>
              <Tag>{s(d.strategy_code)}</Tag>
              <Tag color="arcoblue">{s(d.status)}</Tag>
              <Typography.Text type="secondary">
                终值净值 {s(d.final_nav)} · 收益 {fmtPct(d.total_return).text} ·
                基准 {fmtPct(d.benchmark_return).text}
              </Typography.Text>
            </Space>
            <TimeSeriesChart
              title="净值曲线"
              subtitle={`${s(d.start_date)} → ${s(d.end_date)} · ${nav.length} 点`}
              lines={navLines}
              height={260}
              emptyHint="无 NAV 序列"
              loading={detailQ.isLoading}
            />
            <TimeSeriesChart
              title="回撤（相对峰值 %）"
              hist={ddHist}
              height={160}
              emptyHint="点太少无法画回撤"
            />
            <Typography.Text bold>净值明细（{nav.length}）</Typography.Text>
            <Table
              rowKey={(r) => s(r.trade_date)}
              size="mini"
              pagination={{ pageSize: 6, size: "mini" }}
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

      <Modal
        title="跑 FACTOR_TOP_N 回测"
        visible={runOpen}
        onCancel={() => setRunOpen(false)}
        onOk={() => runMut.mutate()}
        confirmLoading={runMut.isPending}
        okButtonProps={{
          disabled: liveLocked || !range[0] || !range[1],
        }}
      >
        <Form layout="vertical" size="small">
          <Form.Item label={zh.btRange} required>
            <DatePicker.RangePicker
              style={{ width: "100%" }}
              value={range as unknown as never}
              onChange={(ds) => {
                if (Array.isArray(ds) && ds[0] && ds[1]) setRange(ds);
              }}
            />
          </Form.Item>
          <Form.Item label={zh.factorCode}>
            <Select
              value={factor}
              onChange={setFactor}
              options={[
                "MOM_20",
                "VAL_PE_PCT",
                "FLOW_NET_5",
                "TECH_RSI_14",
                "TECH_MACD_HIST",
                "TECH_MA20_BIAS",
              ]}
            />
          </Form.Item>
          <Form.Item label={zh.universeCode}>
            <Select
              value={universe}
              onChange={setUniverse}
              options={["TOP100", "SECTOR_LEADERS", "HS300", "ZZ500"]}
            />
          </Form.Item>
          <Form.Item label={zh.topN}>
            <Input value={topN} onChange={setTopN} />
          </Form.Item>
          <Form.Item label={zh.rebalanceDays}>
            <Input value={reb} onChange={setReb} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
