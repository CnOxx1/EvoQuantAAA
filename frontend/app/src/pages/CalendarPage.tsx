import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DatePicker, Space, Table, Tabs, Typography } from "@arco-design/web-react";
import { listEconCalendar, type ClientConfig } from "../api/gateway";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function CalendarPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [range, setRange] = useState<string[] | undefined>();
  const start = range?.[0];
  const end = range?.[1] || settings.asOf;

  const q = useQuery({
    queryKey: ["econ-cal", cfg.apiBase, start, end],
    queryFn: () => listEconCalendar(cfg, { start, end, limit: 200 }),
    enabled: connected,
  });

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
          财经日历
        </Typography.Title>
        <DatePicker.RangePicker
          size="small"
          style={{ width: 260 }}
          onChange={(ds) => setRange(Array.isArray(ds) ? ds : undefined)}
        />
      </Space>
      <Tabs defaultActiveTab="news">
        <Tabs.TabPane key="news" title={`宏观/政策资讯 (${q.data?.macro_news?.length ?? 0})`}>
          <Table
            rowKey={(r) => `${s(r.publish_time)}-${s(r.title)}-${s(r.source)}`}
            size="small"
            loading={q.isLoading}
            data={q.data?.macro_news ?? []}
            pagination={{ pageSize: 20, size: "mini", showTotal: true }}
            columns={[
              {
                title: "时间",
                dataIndex: "publish_time",
                width: 160,
                render: (v) => s(v),
              },
              { title: "频道", dataIndex: "channel", width: 90, render: (v) => s(v) },
              { title: "标题", dataIndex: "title", render: (v) => s(v) },
              { title: "来源", dataIndex: "source", width: 100, render: (v) => s(v) },
            ]}
          />
        </Tabs.TabPane>
        <Tabs.TabPane key="trade" title={`交易日历 (${q.data?.trade_days?.length ?? 0})`}>
          <Table
            rowKey={(r) => `${s(r.exchange)}-${s(r.trade_date)}`}
            size="small"
            loading={q.isLoading}
            data={q.data?.trade_days ?? []}
            pagination={{ pageSize: 20, size: "mini", showTotal: true }}
            columns={[
              { title: "日期", dataIndex: "trade_date", render: (v) => s(v) },
              { title: "交易所", dataIndex: "exchange", render: (v) => s(v) },
              {
                title: "开市",
                dataIndex: "is_open",
                render: (v) => (v ? "是" : "否"),
              },
              {
                title: "半日",
                dataIndex: "is_half_day",
                render: (v) => (v ? "是" : "—"),
              },
            ]}
          />
        </Tabs.TabPane>
      </Tabs>
    </div>
  );
}
