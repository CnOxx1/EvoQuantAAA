import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Input,
  Message,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getDecision,
  getKill,
  isKillOn,
  listDecisions,
  setKill,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function RiskPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [decId, setDecId] = useState("");
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
  });
  const decQ = useQuery({
    queryKey: ["decisions", cfg.apiBase],
    queryFn: () => listDecisions(cfg, 50),
    enabled: connected,
  });
  const detailQ = useQuery({
    queryKey: ["decision", cfg.apiBase, decId],
    queryFn: () => getDecision(cfg, decId),
    enabled: connected && Boolean(decId),
  });
  const on = isKillOn(killQ.data);
  const mut = useMutation({
    mutationFn: (isOn: boolean) =>
      setKill(cfg, {
        scope: "GLOBAL",
        is_on: isOn,
        reason: reason || undefined,
      }),
    onSuccess: () => {
      Message.success(zh.killUpdated);
      void qc.invalidateQueries({ queryKey: ["kill"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const d = detailQ.data;
  const breaches = (d?.breaches as JsonMap[] | undefined) ?? [];

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
        {zh.risk}
      </Typography.Title>
      <Space style={{ marginBottom: 12 }} align="start">
        <Tag color={on ? "red" : "green"} size="large">
          Kill Switch / {on ? zh.on : zh.off}
        </Tag>
        <Input
          style={{ width: 240 }}
          placeholder={zh.opReason}
          value={reason}
          onChange={setReason}
        />
        <Popconfirm
          title={on ? zh.confirmOff : zh.confirmOn}
          onOk={() => mut.mutate(!on)}
        >
          <Button status={on ? "default" : "danger"} loading={mut.isPending}>
            {on ? zh.closeKill : zh.openKill}
          </Button>
        </Popconfirm>
      </Space>
      <Typography.Title heading={6}>{zh.decisions}</Typography.Title>
      <Table
        rowKey={(r) => s(r.decision_id)}
        size="small"
        loading={decQ.isLoading}
        data={decQ.data ?? []}
        onRow={(r) => ({
          onClick: () => setDecId(s(r.decision_id, "")),
        })}
        columns={[
          { title: zh.time, render: (_, r) => s(r.created_at ?? r.ts) },
          {
            title: zh.result,
            width: 100,
            render: (_, r) => (
              <Tag
                color={String(r.status).includes("reject") ? "red" : "green"}
              >
                {s(r.status)}
              </Tag>
            ),
          },
          { title: zh.portfolio, render: (_, r) => s(r.portfolio_id) },
          {
            title: zh.breaches,
            width: 80,
            render: (_, r) => s(r.breach_count),
          },
        ]}
      />

      <Drawer
        width={460}
        title={`${zh.detail} ${decId}`}
        visible={Boolean(decId)}
        onCancel={() => setDecId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div>
              <Tag
                color={String(d.status).includes("reject") ? "red" : "green"}
              >
                {s(d.status)}
              </Tag>{" "}
              <code>{s(d.portfolio_id)}</code>
            </div>
            <div>
              account <code>{s(d.account_id)}</code> / as_of {s(d.as_of_date)}
            </div>
            <div>
              <Typography.Text bold>
                {zh.breaches} · {breaches.length}
              </Typography.Text>
              {breaches.length ? (
                <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(breaches, null, 2)}
                </pre>
              ) : (
                <Typography.Text type="secondary">{zh.ctxNone}</Typography.Text>
              )}
            </div>
            <div>
              <Typography.Text bold>{zh.meta}</Typography.Text>
              <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(d.meta ?? {}, null, 2)}
              </pre>
            </div>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
