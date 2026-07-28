import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Input,
  Message,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getPortfolio,
  listPortfolios,
  reviewPortfolio,
  type ClientConfig,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function PortfolioPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const [id, setId] = useState("");
  const [status, setStatus] = useState("");
  const [asOf, setAsOf] = useState(settings.asOf || "");
  const listQ = useQuery({
    queryKey: ["portfolios", cfg.apiBase, status, asOf],
    queryFn: () =>
      listPortfolios(cfg, {
        status: status || undefined,
        asOf: asOf || undefined,
      }),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["portfolio", cfg.apiBase, id],
    queryFn: () => getPortfolio(cfg, id),
    enabled: connected && Boolean(id),
  });
  const mut = useMutation({
    mutationFn: () => reviewPortfolio(cfg, id),
    onSuccess: () => {
      Message.success(zh.reviewOk);
      void qc.invalidateQueries({ queryKey: ["portfolio"] });
      void qc.invalidateQueries({ queryKey: ["portfolios"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const positions =
    (detailQ.data?.positions as Record<string, unknown>[] | undefined) ?? [];

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
          {zh.portfolio}
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder={zh.filterStatus}
          style={{ width: 140 }}
          value={status || undefined}
          onChange={(v) => setStatus(v || "")}
          options={["draft", "approved", "executed", "rejected"]}
        />
        <Input
          size="small"
          style={{ width: 140 }}
          placeholder={zh.asOfFilter}
          value={asOf}
          onChange={setAsOf}
        />
      </Space>
      <Table
        rowKey={(r) => s(r.portfolio_id)}
        size="small"
        loading={listQ.isLoading}
        data={listQ.data ?? []}
        style={{ marginBottom: 12 }}
        onRow={(r) => ({
          onClick: () => setId(s(r.portfolio_id, "")),
        })}
        columns={[
          {
            title: "ID",
            render: (_, r) => <code>{s(r.portfolio_id)}</code>,
          },
          {
            title: zh.status,
            width: 110,
            render: (_, r) => <Tag>{s(r.status)}</Tag>,
          },
          { title: zh.account, render: (_, r) => s(r.account_id) },
          {
            title: "as_of",
            render: (_, r) => s(r.as_of_date ?? r.as_of),
          },
        ]}
      />
      {id ? (
        <>
          <Space style={{ marginBottom: 8 }}>
            <Typography.Text>
              {zh.holdings} / {id}
            </Typography.Text>
            <Button
              size="mini"
              type="primary"
              loading={mut.isPending}
              onClick={() => mut.mutate()}
            >
              {zh.submitReview}
            </Button>
          </Space>
          <Table
            rowKey={(r) => `${s(r.symbol)}-${s(r.target_shares ?? r.qty)}`}
            size="small"
            loading={detailQ.isLoading}
            data={positions}
            columns={[
              {
                title: zh.code,
                render: (_, r) => <code>{s(r.symbol)}</code>,
              },
              {
                title: zh.targetShares,
                render: (_, r) => s(r.target_shares ?? r.qty),
              },
              { title: zh.priceBasis, render: (_, r) => s(r.price ?? r.px) },
            ]}
          />
        </>
      ) : null}
    </div>
  );
}
