import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Space, Table, Tag, Typography } from "@arco-design/web-react";
import {
  getResearchRun,
  listResearchRuns,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { zh } from "../i18n/zh";
import { fmtPct, n, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function ResearchPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [id, setId] = useState("");
  const q = useQuery({
    queryKey: ["research", cfg.apiBase],
    queryFn: () => listResearchRuns(cfg, 50),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["research-detail", cfg.apiBase, id],
    queryFn: () => getResearchRun(cfg, id),
    enabled: connected && Boolean(id),
  });

  const d = detailQ.data;
  const freezes = (d?.freezes as JsonMap[] | undefined) ?? [];
  const meta = (d?.meta as JsonMap | undefined) ?? {};
  const report = (meta.report as JsonMap | undefined) ?? {};
  const layers = (report.layers as JsonMap[] | undefined) ?? [];

  const layerBars = useMemo(
    () =>
      layers.map((layer, i) => {
        const qn = Number(layer.quantile ?? i + 1);
        const cum = Number(layer.cum_return);
        return {
          id: `Q${qn}`,
          label: `Q${qn}`,
          value: Number.isFinite(cum) ? cum * 100 : 0,
          color: qn >= 4 ? "#f53f3f" : qn <= 2 ? "#00b42a" : "#86909c",
        };
      }),
    [layers],
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
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.research}
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        research_lab · 实验 run 列表 ·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>{" "}
        新建实验请用 CLI / 研究脚本
      </Typography.Paragraph>
      <Table
        rowKey={(r) => s(r.run_id ?? r.research_run_id)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        onRow={(r) => ({
          onClick: () => setId(s(r.run_id ?? r.research_run_id, "")),
        })}
        columns={[
          {
            title: "run",
            render: (_, r) => (
              <code>{s(r.run_id ?? r.research_run_id)}</code>
            ),
          },
          {
            title: zh.factor,
            render: (_, r) => s(r.factor_code ?? r.factor),
          },
          {
            title: "universe",
            render: (_, r) => s(r.universe_code),
          },
          {
            title: zh.status,
            width: 100,
            render: (_, r) => <Tag>{s(r.status ?? r.conclusion)}</Tag>,
          },
        ]}
      />

      <Drawer
        width={640}
        title={`${zh.detail} ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }} size={14}>
            <div>
              <Tag>{s(d.status)}</Tag> {s(d.factor_code)} / {s(d.universe_code)}
            </div>
            <Typography.Text type="secondary">
              {s(d.start_date)} .. {s(d.end_date)}
            </Typography.Text>
            {report.ic_mean != null ? (
              <Space wrap>
                <Tag color="arcoblue">IC {n(report.ic_mean, 4)}</Tag>
                <Tag>ICIR {n(report.icir, 3)}</Tag>
                <Tag>胜率 {fmtPct(Number(report.ic_win_rate) * 100).text}</Tag>
                <Tag>天数 {s(report.ic_days)}</Tag>
                <Tag>
                  Q5−Q1 {fmtPct(Number(report.long_short_q5_q1) * 100).text}
                </Tag>
              </Space>
            ) : null}
            <CategoryBars
              title="分层累计收益 %"
              subtitle="Q1 低因子 → Q5 高因子"
              items={layerBars}
              height={200}
              formatValue={(v) => `${v.toFixed(1)}%`}
              emptyHint="无分层报告（先跑 research evaluate）"
            />
            <div>
              <Typography.Text bold>{zh.meta}</Typography.Text>
              <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(meta ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              <Typography.Text bold>
                {zh.freezes} · {freezes.length}
              </Typography.Text>
              <Table
                size="mini"
                pagination={false}
                rowKey={(r) => s(r.freeze_id)}
                data={freezes}
                columns={[
                  {
                    title: "freeze",
                    render: (_, r) => <code>{s(r.freeze_id)}</code>,
                  },
                  {
                    title: zh.status,
                    width: 80,
                    render: (_, r) => <Tag>{s(r.status)}</Tag>,
                  },
                  { title: "split", render: (_, r) => s(r.split_mode) },
                ]}
              />
            </div>
          </Space>
        ) : (
          <Typography.Text type="secondary">{zh.noDetail}</Typography.Text>
        )}
      </Drawer>
    </div>
  );
}
