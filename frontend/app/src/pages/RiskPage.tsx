import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Input,
  Message,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getKill,
  isKillOn,
  listDecisions,
  setKill,
  type ClientConfig,
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
  const on = isKillOn(killQ.data);
  const mut = useMutation({
    mutationFn: (isOn: boolean) =>
      setKill(cfg, {
        scope: "global",
        is_on: isOn ? 1 : 0,
        reason: reason || undefined,
      }),
    onSuccess: () => {
      Message.success(zh.killUpdated);
      void qc.invalidateQueries({ queryKey: ["kill"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

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
        rowKey={(r) =>
          `${s(r.decision_id)}-${s(r.created_at ?? r.ts)}-${s(r.portfolio_id)}`
        }
        size="small"
        loading={decQ.isLoading}
        data={decQ.data ?? []}
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
          { title: zh.reason, render: (_, r) => s(r.reason ?? r.message) },
        ]}
      />
    </div>
  );
}
