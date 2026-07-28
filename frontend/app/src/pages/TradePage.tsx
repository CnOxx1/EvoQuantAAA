import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Space, Table, Tag, Typography } from "@arco-design/web-react";
import {
  getExecution,
  listExecutions,
  listPending,
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
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.trade}
      </Typography.Title>
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
          { title: zh.account, render: (_, r) => s(r.account_id) },
        ]}
      />
      {id ? (
        <Space direction="vertical" style={{ width: "100%", marginBottom: 12 }}>
          <Typography.Text>
            {zh.orders} � {id}
          </Typography.Text>
          <Table
            rowKey={(r) => `${s(r.order_id)}-${s(r.symbol)}`}
            size="small"
            data={orders}
            columns={[
              { title: zh.code, render: (_, r) => s(r.symbol) },
              { title: zh.side, render: (_, r) => s(r.side) },
              { title: zh.qty, render: (_, r) => s(r.qty ?? r.quantity) },
              { title: zh.status, render: (_, r) => s(r.status) },
            ]}
          />
          <Typography.Text>{zh.fills}</Typography.Text>
          <Table
            rowKey={(r) => `${s(r.fill_id)}-${s(r.symbol)}-${s(r.price)}`}
            size="small"
            data={fills}
            columns={[
              { title: zh.code, render: (_, r) => s(r.symbol) },
              { title: zh.price, render: (_, r) => s(r.price) },
              { title: zh.qty, render: (_, r) => s(r.qty ?? r.quantity) },
            ]}
          />
        </Space>
      ) : null}
      <Typography.Title heading={6}>{zh.pending}</Typography.Title>
      <Table
        rowKey={(r) =>
          `${s(r.pending_id)}-${s(r.symbol)}-${s(r.status)}`
        }
        size="small"
        loading={pendQ.isLoading}
        data={pendQ.data ?? []}
        columns={[
          { title: zh.code, render: (_, r) => s(r.symbol) },
          {
            title: zh.remaining,
            render: (_, r) => s(r.remaining_qty ?? r.qty),
          },
          { title: zh.status, render: (_, r) => s(r.status) },
        ]}
      />
    </div>
  );
}
