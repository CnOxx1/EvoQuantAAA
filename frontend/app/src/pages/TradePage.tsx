import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Message,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getExecution,
  listExecutions,
  listPending,
  postLedger,
  resumePending,
  type ClientConfig,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

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
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const orders =
    (detailQ.data?.orders as Record<string, unknown>[] | undefined) ?? [];
  const fills =
    (detailQ.data?.fills as Record<string, unknown>[] | undefined) ?? [];

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
          title={liveLocked ? zh.liveLocked : undefined}
        >
          {zh.resumePending}
        </Button>
      </Space>
      <Table
        rowKey={(r) => s(r.execution_id)}
        size="small"
        loading={listQ.isLoading}
        data={listQ.data ?? []}
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
              disabled={liveLocked}
              loading={postMut.isPending}
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
