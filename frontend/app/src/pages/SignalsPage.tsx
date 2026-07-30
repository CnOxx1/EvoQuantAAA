import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Message,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getSignalBatch,
  listSignalBatches,
  runSignal,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { zh } from "../i18n/zh";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function SignalsPage({
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
  const q = useQuery({
    queryKey: ["signal-batches", cfg.apiBase],
    queryFn: () => listSignalBatches(cfg, 80),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["signal-batch", cfg.apiBase, id],
    queryFn: () => getSignalBatch(cfg, id),
    enabled: connected && Boolean(id),
  });

  const runMut = useMutation({
    mutationFn: () =>
      runSignal(cfg, {
        as_of: settings.asOf,
        paper: true,
        live: false,
      }),
    onSuccess: () => {
      Message.success(zh.runSignal);
      void qc.invalidateQueries({ queryKey: ["signal-batches"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const weights = (detailQ.data?.weights as JsonMap[] | undefined) ?? [];

  const weightSlices = useMemo(
    () =>
      weights.map((w) => ({
        id: `${s(w.symbol)}-${s(w.trade_date)}`,
        label: s(w.symbol),
        value: Math.max(0, Number(w.weight) || 0),
      })),
    [weights],
  );

  const signalBars = useMemo(
    () =>
      weights
        .map((w) => ({
          id: s(w.symbol, ""),
          label: s(w.symbol),
          value: Number(w.signal_value),
        }))
        .filter((x) => Number.isFinite(x.value)),
    [weights],
  );

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  const runDisabled = liveLocked || !settings.asOf || runMut.isPending;
  const runTitle = liveLocked
    ? zh.liveLocked
    : !settings.asOf
      ? zh.needAsOf
      : undefined;

  return (
    <div className="page">
      <Space style={{ marginBottom: 8 }} wrap>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          生产信号
        </Typography.Title>
        <Button
          type="primary"
          size="small"
          disabled={runDisabled}
          loading={runMut.isPending}
          title={runTitle}
          onClick={() => runMut.mutate()}
        >
          {zh.runSignal}（PAPER）
        </Button>
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        signal_prod · 需 PAPER/LIVE 策略；as_of={settings.asOf || "—"} ·{" "}
        <Link to="/">也可在总览纸面流水线跑</Link>
      </Typography.Paragraph>
      <Table
        rowKey={(r) => s(r.signal_batch_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        onRow={(r) => ({
          onClick: () => setId(s(r.signal_batch_id, "")),
        })}
        columns={[
          {
            title: "batch",
            dataIndex: "signal_batch_id",
            width: 180,
            render: (v) => <code>{s(v)}</code>,
          },
          {
            title: "策略版本",
            dataIndex: "strategy_version",
            render: (v) => s(v),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          {
            title: "as_of",
            dataIndex: "as_of_date",
            width: 110,
            render: (v) => s(v),
          },
          {
            title: "universe",
            dataIndex: "universe_code",
            render: (v) => s(v),
          },
          {
            title: "行数",
            dataIndex: "row_count",
            width: 80,
            render: (v) => n(v, 0),
          },
          {
            title: "创建",
            dataIndex: "created_at",
            render: (v) => s(v),
          },
        ]}
      />

      <Drawer
        width={800}
        title={`信号 ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Typography.Text>
            版本 <code>{s(detailQ.data?.strategy_version)}</code> · 状态{" "}
            <Tag size="small">{s(detailQ.data?.status)}</Tag>
          </Typography.Text>
          <PieChart
            title="权重饼图"
            subtitle={`${weights.length} 只`}
            slices={weightSlices}
            height={220}
            emptyHint={detailQ.isLoading ? "加载中…" : "无权重"}
          />
          <HorizontalBars
            title="信号值排名"
            items={signalBars}
            height={240}
            formatValue={(v) => n(v, 4)}
            emptyHint="无信号值"
          />
          <Table
            rowKey={(r) => `${s(r.symbol)}-${s(r.trade_date)}`}
            size="mini"
            loading={detailQ.isLoading}
            data={weights}
            pagination={{ pageSize: 12, size: "mini" }}
            columns={[
              { title: "日期", dataIndex: "trade_date", render: (v) => s(v) },
              { title: "标的", dataIndex: "symbol", render: (v) => s(v) },
              {
                title: "权重",
                dataIndex: "weight",
                render: (v) => n(Number(v) * 100, 2) + "%",
              },
              {
                title: "信号值",
                dataIndex: "signal_value",
                render: (v) => n(v, 4),
              },
            ]}
          />
        </Space>
      </Drawer>
    </div>
  );
}
