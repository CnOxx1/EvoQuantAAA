import { useQuery } from "@tanstack/react-query";
import { Table, Tag, Typography } from "@arco-design/web-react";
import { listCapitalAlloc, type ClientConfig } from "../api/gateway";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";

export function CapitalPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const q = useQuery({
    queryKey: ["capital", cfg.apiBase, settings.accountId],
    queryFn: () => listCapitalAlloc(cfg, settings.accountId),
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
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        资本配额
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        strategy_capital_alloc · 账户 <code>{settings.accountId}</code>
        （缺省等权）·{" "}
        <Tag size="small" color="gray">
          只读
        </Tag>
      </Typography.Paragraph>
      <Table
        rowKey={(r) => `${s(r.account_id)}-${s(r.strategy_version)}`}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        columns={[
          { title: "账户", dataIndex: "account_id", render: (v) => s(v) },
          {
            title: "策略版本",
            dataIndex: "strategy_version",
            render: (v) => <code>{s(v)}</code>,
          },
          {
            title: "权重",
            dataIndex: "capital_weight",
            width: 100,
            render: (v) => n(Number(v) * 100, 2) + "%",
          },
          { title: "更新", dataIndex: "updated_at", render: (v) => s(v) },
        ]}
        noDataElement="暂无登记配额（组合构建时按等权切分）"
      />
    </div>
  );
}
