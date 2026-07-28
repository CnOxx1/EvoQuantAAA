import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
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
  getStrategy,
  listStrategies,
  promoteStrategy,
  type ClientConfig,
  type JsonMap,
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
  const [detailId, setDetailId] = useState("");

  const q = useQuery({
    queryKey: ["strategies", cfg.apiBase, status],
    queryFn: () => listStrategies(cfg, status || undefined),
    enabled: connected,
  });

  const detailQ = useQuery({
    queryKey: ["strategy", cfg.apiBase, detailId],
    queryFn: () => getStrategy(cfg, detailId),
    enabled: connected && Boolean(detailId),
  });

  const mut = useMutation({
    mutationFn: () =>
      promoteStrategy(cfg, version, { to, reason: reason || undefined }),
    onSuccess: () => {
      Message.success(zh.promoteOk);
      setOpen(false);
      void qc.invalidateQueries({ queryKey: ["strategies"] });
      if (detailId) void qc.invalidateQueries({ queryKey: ["strategy"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const d = detailQ.data;
  const transitions = (d?.transitions as JsonMap[] | undefined) ?? [];
  const gates = (d?.gate_results as JsonMap[] | undefined) ?? [];

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
        rowKey={(r) => s(r.strategy_version)}
        size="small"
        loading={q.isLoading}
        data={q.data ?? []}
        onRow={(r) => ({
          onClick: () => setDetailId(s(r.strategy_version, "")),
        })}
        columns={[
          {
            title: zh.version,
            render: (_, r) => <code>{s(r.strategy_version)}</code>,
          },
          { title: zh.code, render: (_, r) => s(r.strategy_code) },
          {
            title: zh.status,
            width: 110,
            render: (_, r) => <Tag>{s(r.status)}</Tag>,
          },
          {
            title: zh.action,
            width: 90,
            render: (_, r) => (
              <Button
                size="mini"
                type="primary"
                onClick={(e) => {
                  e.stopPropagation();
                  setVersion(s(r.strategy_version, ""));
                  setOpen(true);
                }}
              >
                {zh.promote}
              </Button>
            ),
          },
        ]}
      />

      <Drawer
        width={480}
        title={`${zh.detail} ${detailId}`}
        visible={Boolean(detailId)}
        onCancel={() => setDetailId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }} size="medium">
            <div>
              <Tag>{s(d.status)}</Tag>{" "}
              <code>{s(d.strategy_code)}</code> / {s(d.strategy_kind)}
            </div>
            <div>
              <Typography.Text type="secondary">research </Typography.Text>
              <code>{s(d.research_run_id)}</code>
            </div>
            <div>
              <Typography.Text type="secondary">backtest </Typography.Text>
              <code>{s(d.backtest_run_id)}</code>
            </div>
            <div>
              <Typography.Text bold>{zh.params}</Typography.Text>
              <pre style={{ fontSize: 11, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(d.params ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              <Typography.Text bold>
                {zh.transitions} · {transitions.length}
              </Typography.Text>
              <Table
                size="mini"
                pagination={false}
                rowKey={(r) => s(r.transition_id)}
                data={transitions}
                columns={[
                  {
                    title: "from",
                    width: 90,
                    render: (_, r) => s(r.from_status),
                  },
                  {
                    title: "to",
                    width: 90,
                    render: (_, r) => s(r.to_status),
                  },
                  { title: zh.reason, render: (_, r) => s(r.reason) },
                ]}
              />
            </div>
            <div>
              <Typography.Text bold>
                {zh.gateResults} · {gates.length}
              </Typography.Text>
              <Table
                size="mini"
                pagination={false}
                rowKey={(r) => s(r.gate_id)}
                data={gates}
                columns={[
                  {
                    title: "to",
                    width: 90,
                    render: (_, r) => s(r.to_status),
                  },
                  {
                    title: zh.status,
                    width: 80,
                    render: (_, r) =>
                      r.skipped ? (
                        <Tag>{zh.skipped}</Tag>
                      ) : r.passed ? (
                        <Tag color="green">{zh.passed}</Tag>
                      ) : (
                        <Tag color="red">{zh.failedGate}</Tag>
                      ),
                  },
                  { title: zh.reason, render: (_, r) => s(r.reason) },
                ]}
              />
            </div>
          </Space>
        ) : (
          <Typography.Text type="secondary">{zh.noDetail}</Typography.Text>
        )}
      </Drawer>

      <Modal
        title={zh.promote}
        visible={open}
        onCancel={() => setOpen(false)}
        onOk={() => mut.mutate()}
        confirmLoading={mut.isPending}
      >
        <Form layout="vertical" size="small">
          <Form.Item label={zh.version}>
            <Input value={version} disabled />
          </Form.Item>
          <Form.Item label={zh.targetStatus}>
            <Select
              value={to}
              onChange={setTo}
              options={["BACKTESTED", "PAPER", "LIVE", "RETIRED"]}
            />
          </Form.Item>
          <Form.Item label={zh.reason}>
            <Input.TextArea
              value={reason}
              onChange={setReason}
              autoSize={{ minRows: 2 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
