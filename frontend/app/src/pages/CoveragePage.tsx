import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DatePicker, Space, Table, Typography } from "@arco-design/web-react";
import { getDataCoverage, type ClientConfig } from "../api/gateway";
import { Heatmap } from "../components/Heatmap";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

function monthsAgo(n: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-01`;
}

export function CoveragePage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [range, setRange] = useState<string[]>([monthsAgo(5), settings.asOf]);

  useEffect(() => {
    setRange((prev) => [prev[0] || monthsAgo(5), settings.asOf || prev[1]]);
  }, [settings.asOf]);

  const q = useQuery({
    queryKey: ["coverage", cfg.apiBase, range[0], range[1]],
    queryFn: () => getDataCoverage(cfg, { start: range[0], end: range[1] }),
    enabled: connected && Boolean(range[0] && range[1]),
  });

  const months = (q.data?.months as string[] | undefined) ?? [];
  const matrix =
    (q.data?.matrix as Record<string, Record<string, number>> | undefined) ??
    {};
  const rowLabels = Object.keys(matrix);
  const values = useMemo(
    () => rowLabels.map((label) => months.map((m) => matrix[label]?.[m] ?? 0)),
    [rowLabels, months, matrix],
  );
  const rows = rowLabels.map((label) => ({
    label,
    ...Object.fromEntries(months.map((m) => [m, matrix[label]?.[m] ?? 0])),
  }));

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          覆盖率
        </Typography.Title>
        <DatePicker.RangePicker
          size="small"
          style={{ width: 260 }}
          value={range as unknown as never}
          onChange={(ds) => {
            if (Array.isArray(ds) && ds[0] && ds[1]) setRange(ds);
          }}
        />
      </Space>

      <div style={{ marginBottom: 16 }}>
        <Heatmap
          title="覆盖热力图"
          subtitle="颜色越深行数越多 · 空为缺口"
          rowLabels={rowLabels}
          colLabels={months}
          values={values}
          emptyHint="无覆盖矩阵"
          loading={q.isLoading}
        />
      </div>

      <Typography.Text bold>明细表</Typography.Text>
      <Table
        style={{ marginTop: 8 }}
        rowKey={(r) => s(r.label)}
        size="small"
        loading={q.isLoading}
        scroll={{ x: true }}
        data={rows}
        pagination={false}
        columns={[
          {
            title: "表",
            dataIndex: "label",
            width: 120,
            fixed: "left",
            render: (v) => s(v),
          },
          ...months.map((m) => ({
            title: m,
            dataIndex: m,
            width: 88,
            render: (v: unknown) => {
              const n = Number(v) || 0;
              return (
                <span
                  style={{
                    color: n === 0 ? "rgb(var(--red-6))" : undefined,
                  }}
                >
                  {n}
                </span>
              );
            },
          })),
        ]}
      />
    </div>
  );
}
