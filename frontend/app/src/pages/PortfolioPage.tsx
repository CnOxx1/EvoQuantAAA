import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Grid,
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
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { zh } from "../i18n/zh";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

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
  const liveLocked = settings.env === "live";
  const [id, setId] = useState("");
  const [status, setStatus] = useState("");
  const [asOf, setAsOf] = useState(settings.asOf || "");
  useEffect(() => {
    setAsOf(settings.asOf || "");
  }, [settings.asOf]);
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
  const portfolioStatus = s(detailQ.data?.status, "");
  const canReview =
    !liveLocked &&
    Boolean(id) &&
    (portfolioStatus === "draft" ||
      portfolioStatus === "DRAFT" ||
      portfolioStatus.toLowerCase() === "draft");
  const reviewTitle = liveLocked
    ? zh.liveLocked
    : !canReview && id
      ? "仅 draft 组合可提交审核"
      : undefined;

  const weightSlices = useMemo(() => {
    return positions
      .map((p) => {
        const w = Number(p.target_weight);
        const v = Number(p.target_value);
        const value = Number.isFinite(w) && w > 0 ? w : Number.isFinite(v) ? v : 0;
        return {
          id: s(p.symbol, ""),
          label: s(p.symbol),
          value,
        };
      })
      .filter((x) => x.value > 0 && x.id);
  }, [positions]);

  const shareBars = useMemo(
    () =>
      positions
        .map((p) => ({
          id: s(p.symbol, ""),
          label: s(p.symbol),
          value: Number(p.target_shares ?? p.qty) || 0,
        }))
        .filter((x) => x.value > 0),
    [positions],
  );

  const statusBars = useMemo(() => {
    const map: Record<string, number> = {};
    for (const r of listQ.data ?? []) {
      const st = String(r.status || "unknown");
      map[st] = (map[st] || 0) + 1;
    }
    const colors: Record<string, string> = {
      draft: "#86909c",
      approved: "#00b42a",
      executed: "#165dff",
      rejected: "#f53f3f",
    };
    return Object.entries(map).map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
      color: colors[k],
    }));
  }, [listQ.data]);

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
        <DatePicker
          size="small"
          style={{ width: 140 }}
          placeholder={zh.asOfFilter}
          value={asOf || undefined}
          onChange={(v) => setAsOf(v || "")}
        />
      </Space>

      {liveLocked ? (
        <Typography.Text type="warning" style={{ display: "block", marginBottom: 8 }}>
          {zh.liveLocked}
        </Typography.Text>
      ) : null}

      <div style={{ marginBottom: 12 }}>
        <PieChart
          title="组合状态分布"
          subtitle={`列表 ${listQ.data?.length ?? 0} 条`}
          slices={statusBars}
          height={180}
          emptyHint="暂无组合"
          loading={listQ.isLoading}
        />
      </div>

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
              disabled={!canReview}
              title={reviewTitle}
              onClick={() => mut.mutate()}
            >
              {zh.submitReview}
            </Button>
          </Space>
          <Row gutter={12} style={{ marginBottom: 12 }}>
            <Col xs={24} md={12}>
              <PieChart
                title="目标权重"
                subtitle="target_weight / value"
                slices={weightSlices}
                height={240}
                emptyHint="无持仓权重"
                loading={detailQ.isLoading}
              />
            </Col>
            <Col xs={24} md={12}>
              <HorizontalBars
                title="目标股数 Top"
                items={shareBars}
                height={240}
                formatValue={(v) => n(v, 0)}
                emptyHint="无目标股数"
                loading={detailQ.isLoading}
              />
            </Col>
          </Row>
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
                title: "权重",
                render: (_, r) => {
                  const w = Number(r.target_weight);
                  return Number.isFinite(w) ? `${(w * 100).toFixed(2)}%` : "—";
                },
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
