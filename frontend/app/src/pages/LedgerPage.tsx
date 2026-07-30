import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Descriptions,
  Grid,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getLedger,
  listLedgerAccounts,
  type ClientConfig,
} from "../api/gateway";
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function LedgerPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const accountsQ = useQuery({
    queryKey: ["ledger-accounts", cfg.apiBase],
    queryFn: () => listLedgerAccounts(cfg),
    enabled: connected,
  });
  const q = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, settings.asOf],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });

  const sleeves =
    (q.data?.sleeves as Record<string, unknown>[] | undefined) ?? [];
  const positions =
    (q.data?.positions as Record<string, unknown>[] | undefined) ?? [];
  const lots = (q.data?.lots as Record<string, unknown>[] | undefined) ?? [];
  const postings =
    (q.data?.postings as Record<string, unknown>[] | undefined) ?? [];
  const sellable =
    (q.data?.sellable as Record<string, unknown>[] | undefined) ?? [];

  const posSource = sleeves.length ? sleeves : positions;
  const posSlices = useMemo(
    () =>
      posSource
        .map((p) => ({
          id: `${s(p.symbol)}-${s(p.strategy_version ?? "")}`,
          label: s(p.symbol),
          value: Math.abs(Number(p.qty ?? p.shares) || 0),
        }))
        .filter((x) => x.value > 0),
    [posSource],
  );

  const sellBars = useMemo(
    () =>
      sellable.map((r) => ({
        id: s(r.symbol, ""),
        label: s(r.symbol),
        value: Number(r.sellable) || 0,
        color: "#00b42a",
      })),
    [sellable],
  );

  const lockedBars = useMemo(
    () =>
      sellable.map((r) => ({
        id: `L-${s(r.symbol)}`,
        label: s(r.symbol),
        value: Number(r.locked) || 0,
        color: "#ff7d00",
      })),
    [sellable],
  );

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
        账本 · {settings.accountId}
      </Typography.Title>

      <Descriptions
        column={4}
        size="small"
        style={{ marginBottom: 12 }}
        data={[
          { label: "现金", value: n(q.data?.cash ?? q.data?.cash_balance, 2) },
          {
            label: "市值",
            value: n(
              (q.data?.mark as Record<string, unknown> | undefined)
                ?.market_value ?? q.data?.market_value,
              2,
            ),
          },
          { label: "NAV", value: n(q.data?.nav, 2) },
          {
            label: "相对开户盈亏",
            value: (() => {
              const pnl = Number(q.data?.pnl);
              const pct = Number(q.data?.pnl_pct);
              if (!Number.isFinite(pnl)) return "—";
              const p =
                Number.isFinite(pct) ? ` (${(pct * 100).toFixed(2)}%)` : "";
              return `${n(pnl, 2)}${p}`;
            })(),
          },
          { label: "as_of", value: s(settings.asOf) },
          { label: "状态", value: s(q.data?.status) },
          {
            label: "缺价标的",
            value: s(
              (q.data?.mark as Record<string, unknown> | undefined)
                ?.missing_prices,
              "0",
            ),
          },
          {
            label: "持仓数",
            value: s(
              (q.data?.mark as Record<string, unknown> | undefined)
                ?.position_count,
              String(posSource.length),
            ),
          },
        ]}
      />

      <Typography.Text bold>账户</Typography.Text>
      <Table
        style={{ marginTop: 8, marginBottom: 16 }}
        rowKey={(r) => s(r.account_id)}
        size="mini"
        loading={accountsQ.isLoading}
        data={accountsQ.data ?? []}
        pagination={false}
        columns={[
          {
            title: "账户",
            dataIndex: "account_id",
            render: (v) => <code>{s(v)}</code>,
          },
          { title: "币种", dataIndex: "currency", width: 70, render: (v) => s(v) },
          {
            title: "现金",
            dataIndex: "cash",
            render: (v) => n(v, 2),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 90,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
        ]}
      />

      <Descriptions
        column={3}
        size="small"
        style={{ marginBottom: 12 }}
        data={[
          { label: "开户现金", value: n(q.data?.opening_cash, 2) },
          {
            label: "过账次数",
            value: String(postings.length),
          },
          {
            label: "最近过账",
            value: s(postings[0]?.as_of_date ?? postings[0]?.created_at),
          },
        ]}
      />

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <PieChart
            title="持仓结构（股数）"
            slices={posSlices}
            height={220}
            emptyHint="无持仓"
          />
        </Col>
        <Col span={12}>
          <HorizontalBars
            title="可卖 vs 锁定"
            subtitle="绿=可卖 · 橙=T+1 锁定"
            items={[...sellBars, ...lockedBars].filter((x) => x.value > 0)}
            height={220}
            formatValue={(v) => n(v, 0)}
            emptyHint="无可卖明细"
          />
        </Col>
      </Row>

      <Tabs defaultActiveTab="sleeves">
        <Tabs.TabPane key="sleeves" title={`Sleeve (${sleeves.length || positions.length})`}>
          <Table
            rowKey={(r) =>
              `${s(r.symbol)}-${s(r.strategy_version ?? "")}-${s(r.qty ?? r.shares)}`
            }
            size="small"
            loading={q.isLoading}
            data={sleeves.length ? sleeves : positions}
            columns={[
              { title: "代码", render: (_, r) => <code>{s(r.symbol)}</code> },
              {
                title: "股数",
                render: (_, r) => n(r.qty ?? r.shares ?? r.quantity, 0),
              },
              {
                title: "策略",
                render: (_, r) => s(r.strategy_version ?? "—"),
              },
            ]}
          />
        </Tabs.TabPane>
        <Tabs.TabPane key="lots" title={`Lots (${lots.length})`}>
          <Table
            rowKey={(r) => s(r.lot_id)}
            size="small"
            loading={q.isLoading}
            data={lots}
            columns={[
              { title: "lot", dataIndex: "lot_id", render: (v) => <code>{s(v)}</code> },
              { title: "代码", dataIndex: "symbol", render: (v) => s(v) },
              { title: "买入日", dataIndex: "buy_date", render: (v) => s(v) },
              {
                title: "剩余",
                dataIndex: "qty_remaining",
                render: (v) => n(v, 0),
              },
              {
                title: "策略",
                dataIndex: "strategy_version",
                render: (v) => s(v, "—"),
              },
            ]}
          />
        </Tabs.TabPane>
        <Tabs.TabPane key="sellable" title={`可卖 (${sellable.length})`}>
          <Table
            rowKey={(r) => s(r.symbol)}
            size="small"
            loading={q.isLoading}
            data={sellable}
            columns={[
              { title: "代码", render: (_, r) => <code>{s(r.symbol)}</code> },
              {
                title: "持仓",
                render: (_, r) => n(r.shares ?? r.qty, 0),
              },
              {
                title: "可卖",
                render: (_, r) => n(r.sellable, 0),
              },
              {
                title: "锁定",
                render: (_, r) => n(r.locked, 0),
              },
            ]}
            noDataElement="无 as_of 可卖明细（或账户无持仓）"
          />
        </Tabs.TabPane>
        <Tabs.TabPane key="postings" title={`过账 (${postings.length})`}>
          <Table
            rowKey={(r) => s(r.posting_id)}
            size="small"
            loading={q.isLoading}
            data={postings}
            columns={[
              {
                title: "posting",
                dataIndex: "posting_id",
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "execution",
                dataIndex: "execution_id",
                render: (v) => <code>{s(v)}</code>,
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 100,
                render: (v) => <Tag size="small">{s(v)}</Tag>,
              },
              { title: "as_of", dataIndex: "as_of_date", render: (v) => s(v) },
              {
                title: "分录数",
                dataIndex: "entry_count",
                width: 80,
                render: (v) => n(v, 0),
              },
              {
                title: "现金后",
                dataIndex: "cash_after",
                render: (v) => n(v, 2),
              },
            ]}
          />
        </Tabs.TabPane>
      </Tabs>

      <Space style={{ marginTop: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          账户切换请到「设置」修改 accountId
        </Typography.Text>
      </Space>
    </div>
  );
}
