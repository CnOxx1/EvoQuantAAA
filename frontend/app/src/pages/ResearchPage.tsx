import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Drawer, Space, Table, Tag, Typography } from "@arco-design/web-react";
import {
  getResearchRun,
  listResearchRuns,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
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
        width={520}
        title={`${zh.detail} ${id}`}
        visible={Boolean(id)}
        onCancel={() => setId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div>
              <Tag>{s(d.status)}</Tag> {s(d.factor_code)} / {s(d.universe_code)}
            </div>
            <div>
              <Typography.Text type="secondary">
                {s(d.start_date)} .. {s(d.end_date)}
              </Typography.Text>
            </div>
            <div>
              <Typography.Text bold>{zh.meta}</Typography.Text>
              <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(d.meta ?? {}, null, 2)}
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
