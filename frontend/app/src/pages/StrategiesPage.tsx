import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Form,
  Input,
  Message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listStrategies,
  promoteStrategy,
  type ClientConfig,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

export function StrategiesPage({
  cfg,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [version, setVersion] = useState("");
  const [to, setTo] = useState("PAPER");
  const [reason, setReason] = useState("");

  const q = useQuery({
    queryKey: ["strategies", cfg.apiBase, status],
    queryFn: () => listStrategies(cfg, status || undefined),
    enabled: connected,
  });

  const mut = useMutation({
    mutationFn: () =>
      promoteStrategy(cfg, version, { to, reason: reason || undefined }),
    onSuccess: () => {
      Message.success(zh.promoteOk);
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["strategies"] });
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
      <Space style={{ marginBottom: 8 }}>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          {zh.strategy}
        </Typography.Title>
        <Select
          size="small"
          allowClear
          placeholder={zh.status}
          style={{ width: 140 }}
          value={status || undefined}
          onChange={(v) => setStatus(v || "")}
          options={["DRAFT", "BACKTESTED", "PAPER", "LIVE", "RETIRED"]}
        />
      </Space>
      <Table
        rowKey={(r) => s(r.strategy_version ?? r.version)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        columns={[
          {
            title: zh.version,
            render: (_, r) => (
              <code>{s(r.strategy_version ?? r.version)}</code>
            ),
          },
          { title: zh.name, render: (_, r) => s(r.name ?? r.strategy_id) },
          {
            title: zh.status,
            width: 110,
            render: (_, r) => <Tag>{s(r.status)}</Tag>,
          },
          {
            title: zh.action,
            width: 100,
            render: (_, r) => (
              <Button
                size="mini"
                type="text"
                onClick={() => {
                  setVersion(s(r.strategy_version ?? r.version, ""));
                  setOpen(true);
                }}
              >
                {zh.promote}
              </Button>
            ),
          },
        ]}
      />
      <Modal
        title={`${zh.promote} ${version}`}
        visible={open}
        onCancel={() => setOpen(false)}
        onOk={() => mut.mutate()}
        confirmLoading={mut.isPending}
      >
        <Form layout="vertical">
          <Form.Item label={zh.targetStatus}>
            <Select
              value={to}
              onChange={setTo}
              options={["BACKTESTED", "PAPER", "LIVE", "RETIRED"]}
            />
          </Form.Item>
          <Form.Item label={zh.reasonOpt}>
            <Input.TextArea value={reason} onChange={setReason} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
