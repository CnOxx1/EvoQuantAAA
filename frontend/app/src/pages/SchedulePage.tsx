import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Grid,
  Message,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listOpsActivity,
  runScheduleOnce,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { PieChart } from "../components/PieChart";
import { STATUS_COLORS, countBy } from "../lib/chartAgg";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

const KIND_COLOR: Record<string, string> = {
  ingest: "arcoblue",
  process: "purple",
  dq: "orangered",
  signal: "green",
  execution: "cyan",
  alert: "red",
};

const KIND_HEX: Record<string, string> = {
  ingest: "#165dff",
  process: "#722ed1",
  dq: "#f77234",
  signal: "#00b42a",
  execution: "#0fc6c2",
  alert: "#f53f3f",
};

export function SchedulePage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const liveLocked = settings.env === "live";
  const [last, setLast] = useState<JsonMap | null>(null);

  const actQ = useQuery({
    queryKey: ["ops-activity", cfg.apiBase],
    queryFn: () => listOpsActivity(cfg, 60),
    enabled: connected,
    refetchInterval: 20_000,
  });

  const mut = useMutation({
    mutationFn: (force: boolean) =>
      runScheduleOnce(cfg, {
        as_of: settings.asOf,
        universe: "TOP100",
        factor_type: "qfq",
        force,
      }),
    onSuccess: (data) => {
      setLast(data as JsonMap);
      const st = s((data as JsonMap).status, "ok");
      if (st === "skipped") {
        Message.warning(`schedule skipped · ${s((data as JsonMap).message, "")}`);
      } else {
        Message.success(`schedule ${st}`);
      }
      void qc.invalidateQueries({ queryKey: ["ops-activity"] });
      void qc.invalidateQueries({ queryKey: ["pipeline"] });
      void qc.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const scheduleDisabled =
    !connected || liveLocked || !settings.asOf || mut.isPending;
  const scheduleTitle = liveLocked
    ? zh.liveLocked
    : !settings.asOf
      ? zh.needAsOf
      : undefined;

  const confirmRun = (force: boolean) => {
    Modal.confirm({
      title: force ? "强制跑一轮日更编排？" : "跑一轮日更编排？",
      content: (
        <div>
          <p>
            将调用 <code>schedule --once</code>：as_of=
            <code>{settings.asOf}</code> · universe=TOP100
            {force ? " · force=true" : ""}。
          </p>
          <p>
            {force
              ? "强制模式会忽略非开市日跳过；仍可能触发外部取数，耗时较长。"
              : "可能触发外部取数，耗时较长；非开市日会 skipped（可用强制）。"}
          </p>
        </div>
      ),
      onOk: () => mut.mutateAsync(force),
    });
  };

  const steps = (last?.steps as JsonMap[] | undefined) ?? [];

  const kindBars = useMemo(
    () =>
      countBy(actQ.data ?? [], (r) => s(r.kind, "?")).map((x) => ({
        ...x,
        color: KIND_HEX[x.id] || "#165dff",
      })),
    [actQ.data],
  );

  const statusSlices = useMemo(
    () =>
      countBy(actQ.data ?? [], (r) => s(r.status, "unknown"), {
        colors: STATUS_COLORS,
      }),
    [actQ.data],
  );

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }} align="center">
        <Typography.Title heading={5} style={{ margin: 0 }}>
          日更编排
        </Typography.Title>
        <Button
          type="primary"
          size="small"
          disabled={scheduleDisabled}
          loading={mut.isPending}
          title={scheduleTitle}
          onClick={() => confirmRun(false)}
        >
          跑一轮 schedule
        </Button>
        <Button
          size="small"
          disabled={scheduleDisabled}
          loading={mut.isPending}
          title={scheduleTitle}
          onClick={() => confirmRun(true)}
        >
          强制跑（忽略休市）
        </Button>
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        orchestrator · 活动时间线（取数/加工/DQ/信号/执行/告警）
        {liveLocked ? ` · ${zh.liveLocked}` : ""}
        {!settings.asOf ? " · 请先设置业务日" : ""}
      </Typography.Paragraph>

      {last ? (
        <div style={{ marginBottom: 16 }}>
          <Typography.Text>
            最近一次：<code>{s(last.job_id)}</code> ·{" "}
            <Tag size="small">{s(last.status)}</Tag> {s(last.message, "")}
          </Typography.Text>
          {steps.length ? (
            <>
              <Space wrap style={{ marginTop: 8, marginBottom: 8 }}>
                {steps.map((st) => (
                  <Tag
                    key={s(st.name)}
                    size="small"
                    color={
                      String(st.status) === "ok"
                        ? "green"
                        : String(st.status) === "failed"
                          ? "red"
                          : "gray"
                    }
                  >
                    {s(st.name)} · {s(st.status)}
                  </Tag>
                ))}
              </Space>
              <Table
                rowKey={(r) => s(r.name)}
                size="mini"
                pagination={false}
                data={steps}
                columns={[
                  { title: "步骤", dataIndex: "name", render: (v) => s(v) },
                  {
                    title: "状态",
                    dataIndex: "status",
                    width: 90,
                    render: (v) => <Tag size="small">{s(v)}</Tag>,
                  },
                  { title: "消息", dataIndex: "message", render: (v) => s(v, "") },
                ]}
              />
            </>
          ) : null}
        </div>
      ) : null}

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={14}>
          <CategoryBars
            title="活动模块构成"
            items={kindBars}
            height={180}
            emptyHint="暂无活动"
            loading={actQ.isLoading}
          />
        </Col>
        <Col xs={24} md={10}>
          <PieChart
            title="活动状态"
            slices={statusSlices}
            height={180}
            emptyHint="暂无活动"
            loading={actQ.isLoading}
          />
        </Col>
      </Row>

      <Typography.Text bold>活动时间线</Typography.Text>
      <Table
        style={{ marginTop: 8 }}
        rowKey={(r) => `${s(r.kind)}-${s(r.ref_id)}-${s(r.created_at)}`}
        size="small"
        loading={actQ.isLoading}
        data={actQ.data ?? []}
        pagination={{ pageSize: 25, size: "mini", showTotal: true }}
        columns={[
          {
            title: "时间",
            dataIndex: "created_at",
            width: 180,
            render: (v) => s(v),
          },
          {
            title: "模块",
            dataIndex: "kind",
            width: 100,
            render: (v) => (
              <Tag size="small" color={KIND_COLOR[String(v)] || "gray"}>
                {s(v)}
              </Tag>
            ),
          },
          { title: "标签", dataIndex: "label", render: (v) => s(v) },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (v) => <Tag size="small">{s(v)}</Tag>,
          },
          {
            title: "ref",
            dataIndex: "ref_id",
            render: (v) => <code>{s(v)}</code>,
          },
        ]}
      />
    </div>
  );
}
