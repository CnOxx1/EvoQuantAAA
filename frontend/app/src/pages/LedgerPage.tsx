import { useQuery } from "@tanstack/react-query";
import { Descriptions, Table, Typography } from "@arco-design/web-react";
import { getLedger, type ClientConfig } from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function LedgerPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["ledger", cfg.apiBase, settings.accountId, settings.asOf],
    queryFn: () => getLedger(cfg, settings.accountId, settings.asOf),
    enabled: connected,
  });

  const sleeves =
    (q.data?.sleeves as Record<string, unknown>[] | undefined) ??
    (q.data?.positions as Record<string, unknown>[] | undefined) ??
    [];

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
        {zh.ledger} � {settings.accountId}
      </Typography.Title>
      <Descriptions
        column={3}
        size="small"
        style={{ marginBottom: 12 }}
        data={[
          { label: zh.cash, value: s(q.data?.cash ?? q.data?.cash_balance) },
          { label: "as_of", value: s(settings.asOf) },
          { label: zh.status, value: s(q.data?.status) },
        ]}
      />
      <Table
        rowKey={(r) =>
          `${s(r.symbol)}-${s(r.strategy_version ?? r.sleeve)}-${s(r.shares ?? r.qty)}`
        }
        size="small"
        loading={q.isLoading}
        data={sleeves}
        columns={[
          { title: zh.code, render: (_, r) => <code>{s(r.symbol)}</code> },
          {
            title: zh.shares,
            render: (_, r) => s(r.shares ?? r.qty ?? r.quantity),
          },
          { title: zh.sellable, render: (_, r) => s(r.sellable ?? r.can_sell) },
          {
            title: zh.strategy,
            render: (_, r) => s(r.strategy_version ?? r.sleeve),
          },
        ]}
      />
    </div>
  );
}
