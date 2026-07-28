import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DatePicker, Input, Space, Table, Tag, Typography } from "@arco-design/web-react";
import { listMarketEvents, type ClientConfig } from "../api/gateway";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const TYPE_ZH: Record<string, string> = {
  unlock: "解禁",
  corp_action: "公司行为",
  major_contract: "重大合同",
  announcement: "公告",
};

export function EventsPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [symbol, setSymbol] = useState("");
  const [range, setRange] = useState<string[] | undefined>();

  const start = range?.[0] || undefined;
  const end = range?.[1] || settings.asOf;

  const q = useQuery({
    queryKey: ["events", cfg.apiBase, start, end, symbol],
    queryFn: () =>
      listMarketEvents(cfg, {
        start,
        end,
        symbol: symbol.trim() || undefined,
        limit: 200,
      }),
    enabled: connected,
  });

  const data = useMemo(() => q.data?.items ?? [], [q.data]);

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          事件日历
        </Typography.Title>
        <DatePicker.RangePicker
          size="small"
          style={{ width: 260 }}
          onChange={(ds) => setRange(Array.isArray(ds) ? ds : undefined)}
        />
        <Input
          size="small"
          allowClear
          placeholder="标的代码"
          style={{ width: 120 }}
          value={symbol}
          onChange={setSymbol}
        />
      </Space>
      <Table
        rowKey={(r) =>
          `${s(r.event_date)}-${s(r.event_type)}-${s(r.symbol)}-${s(r.title)}`
        }
        size="small"
        loading={q.isLoading}
        data={data}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        columns={[
          { title: "日期", dataIndex: "event_date", width: 110, render: (v) => s(v) },
          {
            title: "类型",
            dataIndex: "event_type",
            width: 100,
            render: (v) => (
              <Tag size="small">{TYPE_ZH[s(v)] || s(v)}</Tag>
            ),
          },
          { title: "代码", dataIndex: "symbol", width: 90, render: (v) => s(v) },
          { title: "标题", dataIndex: "title", render: (v) => s(v) },
        ]}
      />
    </div>
  );
}
