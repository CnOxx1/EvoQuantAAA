import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Grid,
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
import { CategoryBars } from "../components/CategoryBars";
import { HorizontalBars } from "../components/HorizontalBars";
import { PieChart } from "../components/PieChart";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

function breachLabel(b: JsonMap, i: number): string {
  return String(
    b.rule || b.code || b.rule_code || b.type || b.name || `breach_${i + 1}`,
  );
}

export function RiskPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  // Kill is an emergency control — allow even when env=live
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

  const resultSlices = useMemo(() => {
    const map: Record<string, number> = {};
    for (const r of decQ.data ?? []) {
      const st = String(r.status || "unknown");
      const key = st.includes("reject")
        ? "rejected"
        : st.includes("approv")
          ? "approved"
          : st;
      map[key] = (map[key] || 0) + 1;
    }
    return Object.entries(map).map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
      color: k.includes("reject") ? "#f53f3f" : "#00b42a",
    }));
  }, [decQ.data]);

  const breachCountBars = useMemo(() => {
    const buckets = { "0": 0, "1": 0, "2–3": 0, "4+": 0 };
    for (const r of decQ.data ?? []) {
      const n = Number(r.breach_count ?? 0);
      if (n <= 0) buckets["0"] += 1;
      else if (n === 1) buckets["1"] += 1;
      else if (n <= 3) buckets["2–3"] += 1;
      else buckets["4+"] += 1;
    }
    return Object.entries(buckets).map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
      color: k === "0" ? "#00b42a" : "#f53f3f",
    }));
  }, [decQ.data]);

  const breachBars = useMemo(() => {
    const map: Record<string, number> = {};
    for (const [i, b] of breaches.entries()) {
      const label = breachLabel(b, i);
      map[label] = (map[label] || 0) + 1;
    }
    return Object.entries(map).map(([k, v]) => ({
      id: k,
      label: k,
      value: v,
      color: "#f53f3f",
    }));
  }, [breaches]);

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
          <Button
            status={on ? "default" : "danger"}
            loading={mut.isPending}
          >
            {on ? zh.closeKill : zh.openKill}
          </Button>
        </Popconfirm>
      </Space>
      {settings.env === "live" ? (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          当前 Settings 为 live：Kill 仍可操作（紧急开关）；其他写操作在别页锁定。
        </Typography.Text>
      ) : null}

      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col xs={24} md={10}>
          <PieChart
            title="决策结果"
            subtitle={`近 ${decQ.data?.length ?? 0} 条`}
            slices={resultSlices}
            height={200}
            emptyHint="暂无决策"
            loading={decQ.isLoading}
          />
        </Col>
        <Col xs={24} md={14}>
          <CategoryBars
            title="违规条数分布"
            subtitle="每条决策的 breach_count"
            items={breachCountBars}
            height={200}
            loading={decQ.isLoading}
          />
        </Col>
      </Row>

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
        width={560}
        title={`${zh.detail} ${decId}`}
        visible={Boolean(decId)}
        onCancel={() => setDecId("")}
        footer={null}
      >
        {detailQ.isLoading ? (
          <Typography.Text type="secondary">{zh.loading}</Typography.Text>
        ) : d ? (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
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
            <HorizontalBars
              title="本决策违规规则"
              items={breachBars}
              height={180}
              formatValue={(v) => String(v)}
              emptyHint={zh.ctxNone}
            />
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
