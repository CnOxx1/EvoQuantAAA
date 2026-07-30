import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Grid,
  Message,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getExecution,
  getLedger,
  listExecutions,
  listPending,
  postLedger,
  resumePending,
  type ClientConfig,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { zh } from "../i18n/zh";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

export function TradePage({
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
  const [unpostedOnly, setUnpostedOnly] = useState(false);
  const listQ = useQuery({
    queryKey: ["executions", cfg.apiBase],
    queryFn: () => listExecutions(cfg, 50),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["execution", cfg.apiBase, id],
    queryFn: () => getExecution(cfg, id),
    enabled: connected && Boolean(id),
  });
  const pendQ = useQuery({
    queryKey: ["pending", cfg.apiBase, settings.accountId],
    queryFn: () => listPending(cfg, settings.accountId),
    enabled: connected,
  });

  const resumeMut = useMutation({
    mutationFn: () =>
      resumePending(cfg, {
        as_of: settings.asOf,
        account_id: settings.accountId,
        adapter: "paper",
      }),
    onSuccess: () => {
      Message.success(zh.resumePending);
      void qc.invalidateQueries({ queryKey: ["pending"] });
      void qc.invalidateQueries({ queryKey: ["executions"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const postMut = useMutation({
    mutationFn: (executionId: string) =>
      postLedger(cfg, { execution_id: executionId }),
    onSuccess: () => {
      Message.success(zh.postLedger);
      void qc.invalidateQueries({ queryKey: ["execution"] });
      void qc.invalidateQueries({ queryKey: ["executions"] });
      void qc.invalidateQueries({ queryKey: ["ledger"] });
      void qc.invalidateQueries({ queryKey: ["pipeline"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const ledgerQ = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, settings.asOf],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });
  const postedIds = useMemo(() => {
    const posts =
      (ledgerQ.data?.postings as Record<string, unknown>[] | undefined) ?? [];
    return new Set(
      posts
        .filter((p) => String(p.status).toLowerCase() === "committed")
        .map((p) => String(p.execution_id || "")),
    );
  }, [ledgerQ.data]);

  const orders =
    (detailQ.data?.orders as Record<string, unknown>[] | undefined) ?? [];
  const fills =
    (detailQ.data?.fills as Record<string, unknown>[] | undefined) ?? [];

  const statusSlices = useMemo(() => {
    const map: Record<string, number> = {};
    for (const r of listQ.data ?? []) {
      const st = String(r.status || "unknown");
      map[st] = (map[st] || 0) + 1;
    }
    return Object.entries(map).map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
    }));
  }, [listQ.data]);

  const fillBars = useMemo(
    () =>
      fills.map((f, i) => ({
        id: `${s(f.fill_id)}-${i}`,
        label: `${s(f.side)} ${s(f.symbol)}`,
        value: Math.abs(Number(f.amount) || 0),
        color: String(f.side).toUpperCase().includes("SELL")
          ? "#f53f3f"
          : "#165dff",
      })),
    [fills],
  );

  const pendingBars = useMemo(
    () =>
      (pendQ.data ?? []).map((r) => ({
        id: s(r.pending_id, s(r.symbol)),
        label: `${s(r.side)} ${s(r.symbol)}`,
        value: Number(r.qty_remaining ?? r.remaining_qty ?? r.qty) || 0,
        color: "#ff7d00",
      })),
    [pendQ.data],
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
      <Space style={{ marginBottom: 8 }}>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          {zh.trade}
        </Typography.Title>
        <Button
          size="mini"
          disabled={liveLocked || !settings.asOf}
          loading={resumeMut.isPending}
          onClick={() => resumeMut.mutate()}
          title={
            liveLocked
              ? zh.liveLocked
              : !settings.asOf
                ? zh.needAsOf
                : undefined
          }
        >
          {zh.resumePending}
        </Button>
        <Button
          size="mini"
          type={unpostedOnly ? "primary" : "default"}
          onClick={() => setUnpostedOnly((v) => !v)}
        >
          仅未过账
        </Button>
      </Space>

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={10}>
          <PieChart
            title="执行状态"
            slices={statusSlices}
            height={180}
            emptyHint="暂无执行批次"
          />
        </Col>
        <Col span={14}>
          <HorizontalBars
            title="未成交残差"
            items={pendingBars}
            height={180}
            formatValue={(v) => n(v, 0)}
            emptyHint="无 open pending"
          />
        </Col>
      </Row>

      <Table
        rowKey={(r) => s(r.execution_id)}
        size="small"
        loading={listQ.isLoading}
        data={(listQ.data ?? []).filter((r) => {
          if (!unpostedOnly) return true;
          const eid = String(r.execution_id || "");
          return eid && !postedIds.has(eid);
        })}
        style={{ marginBottom: 12 }}
        onRow={(r) => ({
          onClick: () => setId(s(r.execution_id, "")),
        })}
        columns={[
          {
            title: "execution",
            render: (_, r) => <code>{s(r.execution_id)}</code>,
          },
          {
            title: zh.adapter,
            width: 110,
            render: (_, r) => <Tag>{s(r.adapter ?? r.adapter_kind)}</Tag>,
          },
          {
            title: zh.status,
            width: 100,
            render: (_, r) => <Tag>{s(r.status)}</Tag>,
          },
          {
            title: "过账",
            width: 80,
            render: (_, r) => {
              const eid = String(r.execution_id || "");
              const ok = postedIds.has(eid);
              return (
                <Tag color={ok ? "green" : "orangered"} size="small">
                  {ok ? "已过账" : "未过账"}
                </Tag>
              );
            },
          },
          {
            title: "fills",
            width: 70,
            render: (_, r) => s(r.fill_count),
          },
          { title: zh.account, render: (_, r) => s(r.account_id) },
        ]}
      />
      {id ? (
        <Space direction="vertical" style={{ width: "100%", marginBottom: 12 }}>
          <Space>
            <Typography.Text>
              {zh.orders} / {id}
            </Typography.Text>
            <Button
              size="mini"
              disabled={liveLocked || postedIds.has(id)}
              loading={postMut.isPending}
              title={
                liveLocked
                  ? zh.liveLocked
                  : postedIds.has(id)
                    ? "已过账"
                    : "将成交写入账本"
              }
              onClick={() => postMut.mutate(id)}
            >
              {zh.postLedger}
            </Button>
          </Space>
          <Table
            rowKey={(r) => `${s(r.event_id ?? r.order_id)}-${s(r.symbol)}`}
            size="small"
            data={orders}
            columns={[
              { title: zh.code, render: (_, r) => s(r.symbol) },
              { title: zh.side, render: (_, r) => s(r.side) },
              { title: zh.qty, render: (_, r) => s(r.qty ?? r.quantity) },
              {
                title: "limit",
                render: (_, r) => s(r.limit_price),
              },
              { title: zh.status, render: (_, r) => s(r.status) },
              { title: zh.reason, render: (_, r) => s(r.reason) },
            ]}
          />
          <Typography.Text>{zh.fills}</Typography.Text>
          {fills.length ? (
            <CategoryBars
              title="成交金额"
              items={fillBars}
              height={160}
              formatValue={(v) => n(v, 0)}
            />
          ) : null}
          <Table
            rowKey={(r) => `${s(r.fill_id)}-${s(r.symbol)}-${s(r.price)}`}
            size="small"
            data={fills}
            columns={[
              { title: zh.code, render: (_, r) => s(r.symbol) },
              { title: zh.side, render: (_, r) => s(r.side) },
              { title: zh.price, render: (_, r) => s(r.price) },
              { title: zh.qty, render: (_, r) => s(r.qty ?? r.quantity) },
              { title: zh.amount, render: (_, r) => s(r.amount) },
            ]}
          />
        </Space>
      ) : null}
      <Typography.Title heading={6}>
        {zh.pending} · {pendQ.data?.length ?? 0}
      </Typography.Title>
      <Table
        rowKey={(r) => s(r.pending_id)}
        size="small"
        loading={pendQ.isLoading}
        data={pendQ.data ?? []}
        columns={[
          { title: zh.code, render: (_, r) => <code>{s(r.symbol)}</code> },
          { title: zh.side, width: 60, render: (_, r) => s(r.side) },
          {
            title: zh.qtyRemain,
            render: (_, r) => s(r.qty_remaining ?? r.remaining_qty ?? r.qty),
          },
          {
            title: "origin",
            render: (_, r) => s(r.qty_origin),
          },
          { title: zh.status, width: 80, render: (_, r) => s(r.status) },
          { title: zh.reason, render: (_, r) => s(r.last_reason) },
        ]}
      />
    </div>
  );
}
