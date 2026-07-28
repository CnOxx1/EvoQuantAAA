import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Select, Space, Table, Typography } from "@arco-design/web-react";
import {
  listBoardHistory,
  listBoardMembers,
  listBoards,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { fmtAmt, fmtPct, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function BoardsPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [boardType, setBoardType] = useState<string | undefined>();
  const [selected, setSelected] = useState<JsonMap | null>(null);

  const q = useQuery({
    queryKey: ["boards", cfg.apiBase, boardType],
    queryFn: () => listBoards(cfg, { boardType, limit: 200 }),
    enabled: connected,
  });

  const name = s(selected?.board_name, "");
  const histQ = useQuery({
    queryKey: ["board-hist", cfg.apiBase, name, selected?.board_type],
    queryFn: () =>
      listBoardHistory(cfg, {
        boardName: name,
        boardType: s(selected?.board_type) || undefined,
        limit: 60,
      }),
    enabled: connected && Boolean(name),
  });
  const memQ = useQuery({
    queryKey: ["board-mem", cfg.apiBase, name, settings.asOf],
    queryFn: () =>
      listBoardMembers(cfg, {
        industryName: name,
        asOf: settings.asOf,
        limit: 100,
      }),
    enabled: connected && Boolean(name),
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
      <Space style={{ marginBottom: 12 }} align="center">
        <Typography.Title heading={5} style={{ margin: 0 }}>
          板块监控
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder="板块类型"
          style={{ width: 140 }}
          value={boardType}
          onChange={setBoardType}
          options={[
            { label: "行业", value: "INDUSTRY" },
            { label: "概念", value: "CONCEPT" },
          ]}
        />
        <Typography.Text type="secondary">
          交易日 {s(q.data?.trade_date, "—")}
        </Typography.Text>
      </Space>
      <Table
        rowKey={(r) => `${s(r.board_type)}-${s(r.board_name)}`}
        size="small"
        loading={q.isLoading}
        data={q.data?.items ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        onRow={(r) => ({ onClick: () => setSelected(r) })}
        columns={[
          { title: "类型", dataIndex: "board_type", width: 90, render: (v) => s(v) },
          { title: "名称", dataIndex: "board_name", render: (v) => s(v) },
          {
            title: "涨跌%",
            dataIndex: "pct_chg",
            width: 90,
            render: (v) => fmtPct(v).text,
          },
          {
            title: "收盘",
            dataIndex: "close",
            width: 90,
            render: (v) => s(v),
          },
          {
            title: "成交额",
            dataIndex: "amount",
            width: 110,
            render: (v) => fmtAmt(v as number | null),
          },
        ]}
      />
      <Drawer
        width={640}
        title={name || "板块详情"}
        visible={Boolean(selected)}
        onCancel={() => setSelected(null)}
        footer={null}
      >
        <Typography.Text bold>近 60 日</Typography.Text>
        <Table
          style={{ marginTop: 8, marginBottom: 16 }}
          rowKey={(r) => s(r.trade_date)}
          size="mini"
          loading={histQ.isLoading}
          data={histQ.data?.bars ?? []}
          pagination={{ pageSize: 10, size: "mini" }}
          columns={[
            { title: "日期", dataIndex: "trade_date", render: (v) => s(v) },
            { title: "收盘", dataIndex: "close", render: (v) => s(v) },
            {
              title: "涨跌%",
              dataIndex: "pct_chg",
              render: (v) => fmtPct(v).text,
            },
            {
              title: "成交额",
              dataIndex: "amount",
              render: (v) => fmtAmt(v as number | null),
            },
          ]}
        />
        <Typography.Text bold>
          成分（行业映射，{memQ.data?.count ?? 0}）
        </Typography.Text>
        <Table
          style={{ marginTop: 8 }}
          rowKey={(r) => s(r.symbol)}
          size="mini"
          loading={memQ.isLoading}
          data={memQ.data?.items ?? []}
          pagination={{ pageSize: 10, size: "mini" }}
          columns={[
            { title: "代码", dataIndex: "symbol", render: (v) => s(v) },
            { title: "行业", dataIndex: "industry_name", render: (v) => s(v) },
            { title: "标准", dataIndex: "standard", render: (v) => s(v) },
          ]}
        />
      </Drawer>
    </div>
  );
}
