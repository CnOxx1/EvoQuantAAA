import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  DatePicker,
  Drawer,
  Form,
  Grid,
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
  listBacktestRuns,
  listStrategies,
  promoteStrategy,
  registerStrategy,
  runBacktest,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { PieChart } from "../components/PieChart";
import { countBy } from "../lib/chartAgg";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const { Row, Col } = Grid;

const STRAT_STATUS_COLORS: Record<string, string> = {
  DRAFT: "#86909c",
  BACKTESTED: "#165dff",
  PAPER: "#0fc6c2",
  LIVE: "#00b42a",
  RETIRED: "#c9cdd4",
};

const FACTOR_OPTS = [
  "MOM_20",
  "VAL_PE_PCT",
  "FLOW_NET_5",
  "TECH_RSI_14",
  "TECH_MACD_HIST",
  "TECH_MA20_BIAS",
];

const UNIVERSE_OPTS = ["TOP100", "SECTOR_LEADERS", "HS300", "ZZ500"];

function daysAgo(n: number, end?: string): string {
  const base = end ? new Date(`${end}T00:00:00`) : new Date();
  base.setDate(base.getDate() - n);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`;
}

function guideText(status: string): string {
  if (status === "DRAFT") return zh.guideDraft;
  if (status === "BACKTESTED") return zh.guideBacktested;
  if (status === "PAPER") return zh.guidePaper;
  if (status === "LIVE") return zh.guideLive;
  return "";
}

function nextPromoteTarget(status: string): string {
  if (status === "DRAFT") return "BACKTESTED";
  if (status === "BACKTESTED") return "PAPER";
  if (status === "PAPER") return "LIVE";
  return "RETIRED";
}

export function StrategiesPage({
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
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [regOpen, setRegOpen] = useState(false);
  const [version, setVersion] = useState("");
  const [fromStatus, setFromStatus] = useState("");
  const [to, setTo] = useState("PAPER");
  const [reason, setReason] = useState("");
  const [backtestRun, setBacktestRun] = useState("");
  const [btRange, setBtRange] = useState<string[]>([
    daysAgo(60, settings.asOf),
    settings.asOf || daysAgo(0),
  ]);
  const [detailId, setDetailId] = useState("");
  const [guide, setGuide] = useState<{ version: string; status: string } | null>(
    null,
  );
  const [regCode, setRegCode] = useState("FTN_MOM20");
  const [regFactor, setRegFactor] = useState("MOM_20");
  const [regTopN, setRegTopN] = useState("20");
  const [regReb, setRegReb] = useState("20");
  const [regUniverse, setRegUniverse] = useState("TOP100");
  const [regFactorType, setRegFactorType] = useState("qfq");
  const [regResearch, setRegResearch] = useState("");
  const [regBacktest, setRegBacktest] = useState("");
  const [regNote, setRegNote] = useState("");

  useEffect(() => {
    if (settings.asOf) {
      setBtRange((prev) => [prev[0] || daysAgo(60, settings.asOf), settings.asOf]);
    }
  }, [settings.asOf]);

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

  const btQ = useQuery({
    queryKey: ["backtest-committed", cfg.apiBase],
    queryFn: () => listBacktestRuns(cfg, { status: "committed", limit: 50 }),
    enabled: connected && open,
  });

  const openPromote = (row: JsonMap) => {
    const st = s(row.status);
    setVersion(s(row.strategy_version, ""));
    setFromStatus(st);
    setTo(nextPromoteTarget(st));
    setBacktestRun(s(row.backtest_run_id, ""));
    setReason("");
    setOpen(true);
  };

  const mut = useMutation({
    mutationFn: () =>
      promoteStrategy(cfg, version, {
        to,
        reason: reason || undefined,
        backtest_run: to === "BACKTESTED" ? backtestRun || undefined : undefined,
      }),
    onSuccess: (data) => {
      Message.success(zh.promoteOk);
      setOpen(false);
      const st = s((data as JsonMap).to_status, to);
      setGuide({ version, status: st });
      void qc.invalidateQueries({ queryKey: ["strategies"] });
      if (detailId) void qc.invalidateQueries({ queryKey: ["strategy"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const regMut = useMutation({
    mutationFn: () =>
      registerStrategy(cfg, {
        strategy_code: regCode.trim(),
        strategy_kind: "FACTOR_TOP_N",
        factor_code: regFactor,
        top_n: Number(regTopN) || 20,
        rebalance_days: Number(regReb) || 20,
        universe_code: regUniverse,
        factor_type: regFactorType,
        research_run_id: regResearch.trim() || undefined,
        backtest_run_id: regBacktest.trim() || undefined,
        note: regNote.trim() || undefined,
      }),
    onSuccess: (data) => {
      const ver = s((data as JsonMap).strategy_version);
      Message.success(`${zh.registerOk} · ${ver}`);
      setRegOpen(false);
      setGuide({ version: ver, status: "DRAFT" });
      setVersion(ver);
      setFromStatus("DRAFT");
      setTo("BACKTESTED");
      setOpen(true);
      void qc.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const btPromoteMut = useMutation({
    mutationFn: async () => {
      const row =
        q.data?.find((r) => s(r.strategy_version) === version) ||
        detailQ.data ||
        {};
      const params = (row.params as JsonMap | undefined) || {};
      if (!btRange[0] || !btRange[1]) {
        throw new Error("请选择回测区间");
      }
      const bt = await runBacktest(cfg, {
        strategy: "FACTOR_TOP_N",
        start: btRange[0],
        end: btRange[1],
        universe: s(params.universe_code, regUniverse),
        factor_type: s(params.factor_type, regFactorType),
        factor: s(params.factor_code, regFactor),
        top_n: Number(params.top_n) || Number(regTopN) || 20,
        rebalance_days: Number(params.rebalance_days) || Number(regReb) || 20,
        require_dq: true,
      });
      const runId = s(bt.run_id);
      if (!runId) throw new Error("回测未返回 run_id");
      Message.success(`${zh.btOk} · ${runId}`);
      setBacktestRun(runId);
      return promoteStrategy(cfg, version, {
        to: "BACKTESTED",
        backtest_run: runId,
        reason: reason || "auto backtest+promote",
      });
    },
    onSuccess: () => {
      Message.success(zh.promoteOk);
      setOpen(false);
      setGuide({ version, status: "BACKTESTED" });
      void qc.invalidateQueries({ queryKey: ["strategies"] });
      void qc.invalidateQueries({ queryKey: ["backtest"] });
      void qc.invalidateQueries({ queryKey: ["backtest-committed"] });
      if (detailId) void qc.invalidateQueries({ queryKey: ["strategy"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const paperMut = useMutation({
    mutationFn: (ver: string) =>
      promoteStrategy(cfg, ver, { to: "PAPER", reason: "ui quick promote" }),
    onSuccess: (_d, ver) => {
      Message.success(zh.promoteOk);
      setGuide({ version: ver, status: "PAPER" });
      void qc.invalidateQueries({ queryKey: ["strategies"] });
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const d = detailQ.data;
  const transitions = (d?.transitions as JsonMap[] | undefined) ?? [];
  const gates = (d?.gate_results as JsonMap[] | undefined) ?? [];

  const statusSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.status, "unknown"), {
        colors: STRAT_STATUS_COLORS,
      }),
    [q.data],
  );

  const kindSlices = useMemo(
    () =>
      countBy(q.data ?? [], (r) => s(r.strategy_kind, "?"), {
        defaultColor: "#722ed1",
      }),
    [q.data],
  );

  const btOptions = (btQ.data ?? []).map((r) => ({
    value: s(r.run_id),
    label: `${s(r.run_id)} · ${s(r.strategy_code)} · ${s(r.start_date)}→${s(r.end_date)}`,
  }));

  const promoteOkDisabled =
    liveLocked ||
    mut.isPending ||
    btPromoteMut.isPending ||
    (to === "BACKTESTED" && !backtestRun);
  const promoteHint = liveLocked
    ? zh.liveLocked
    : to === "BACKTESTED" && !backtestRun
      ? zh.needBacktest
      : to === "LIVE"
        ? "晋升 LIVE 需质量门通过；UI 在 live 环境会锁定写操作"
        : undefined;

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 8 }} wrap>
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
        <Button
          type="primary"
          size="small"
          disabled={liveLocked}
          title={liveLocked ? zh.liveLocked : undefined}
          onClick={() => setRegOpen(true)}
        >
          {zh.register}
        </Button>
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        注册 DRAFT → 回测并晋升 BACKTESTED → PAPER → 总览「一键跑通纸面」
      </Typography.Paragraph>

      {guide ? (
        <Alert
          style={{ marginBottom: 12 }}
          type="info"
          title={zh.guideTitle}
          content={
            <Space direction="vertical" size={4}>
              <Typography.Text>
                <code>{guide.version}</code> · {guide.status} ·{" "}
                {guideText(guide.status)}
              </Typography.Text>
              <Space wrap>
                {guide.status === "DRAFT" ? (
                  <Button
                    size="mini"
                    type="primary"
                    disabled={liveLocked}
                    onClick={() => {
                      setVersion(guide.version);
                      setFromStatus("DRAFT");
                      setTo("BACKTESTED");
                      setOpen(true);
                    }}
                  >
                    {zh.runBtPromote}
                  </Button>
                ) : null}
                {guide.status === "BACKTESTED" ? (
                  <Button
                    size="mini"
                    type="primary"
                    disabled={liveLocked || paperMut.isPending}
                    loading={paperMut.isPending}
                    onClick={() => paperMut.mutate(guide.version)}
                  >
                    {zh.promoteToPaper}
                  </Button>
                ) : null}
                {guide.status === "PAPER" || guide.status === "LIVE" ? (
                  <Link to="/">去总览跑纸面流水线 →</Link>
                ) : null}
                <Link to="/backtest">回测中心</Link>
              </Space>
            </Space>
          }
          closable
          onClose={() => setGuide(null)}
        />
      ) : null}

      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col xs={24} md={12}>
          <PieChart
            title="状态分布"
            slices={statusSlices}
            height={160}
            emptyHint="暂无策略"
            loading={q.isLoading}
          />
        </Col>
        <Col xs={24} md={12}>
          <PieChart
            title="策略类型"
            slices={kindSlices}
            height={160}
            emptyHint="暂无策略"
            loading={q.isLoading}
          />
        </Col>
      </Row>

      {liveLocked ? (
        <Typography.Text type="warning" style={{ display: "block", marginBottom: 8 }}>
          {zh.liveLocked}
        </Typography.Text>
      ) : null}

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
            width: 200,
            render: (_, r) => {
              const st = s(r.status);
              return (
                <Space size={4}>
                  <Button
                    size="mini"
                    type="primary"
                    disabled={liveLocked}
                    title={liveLocked ? zh.liveLocked : undefined}
                    onClick={(e) => {
                      e.stopPropagation();
                      openPromote(r);
                    }}
                  >
                    {zh.promote}
                  </Button>
                  {st === "BACKTESTED" ? (
                    <Button
                      size="mini"
                      disabled={liveLocked || paperMut.isPending}
                      onClick={(e) => {
                        e.stopPropagation();
                        paperMut.mutate(s(r.strategy_version, ""));
                      }}
                    >
                      PAPER
                    </Button>
                  ) : null}
                </Space>
              );
            },
          },
        ]}
      />

      <Drawer
        width={520}
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
            <Typography.Text type="secondary">
              {guideText(s(d.status))}
            </Typography.Text>
            <div>
              <Typography.Text type="secondary">research </Typography.Text>
              <code>{s(d.research_run_id)}</code>
            </div>
            <div>
              <Typography.Text type="secondary">backtest </Typography.Text>
              <code>{s(d.backtest_run_id)}</code>
            </div>
            <Space>
              <Button
                size="mini"
                type="primary"
                disabled={liveLocked}
                onClick={() => openPromote(d)}
              >
                {zh.promote}
              </Button>
              {s(d.status) === "BACKTESTED" ? (
                <Button
                  size="mini"
                  disabled={liveLocked}
                  onClick={() => paperMut.mutate(s(d.strategy_version, ""))}
                >
                  {zh.promoteToPaper}
                </Button>
              ) : null}
            </Space>
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
        title={zh.register}
        visible={regOpen}
        onCancel={() => setRegOpen(false)}
        onOk={() => regMut.mutate()}
        confirmLoading={regMut.isPending}
        okButtonProps={{ disabled: liveLocked || !regCode.trim() || !regFactor }}
      >
        <Form layout="vertical" size="small">
          <Form.Item label={zh.strategyCode} required>
            <Input
              value={regCode}
              onChange={setRegCode}
              placeholder="FTN_MOM20"
            />
          </Form.Item>
          <Form.Item label={zh.strategyKind}>
            <Input value="FACTOR_TOP_N" disabled />
          </Form.Item>
          <Form.Item label={zh.factorCode} required>
            <Select
              value={regFactor}
              onChange={setRegFactor}
              options={FACTOR_OPTS}
            />
          </Form.Item>
          <Form.Item label={zh.topN}>
            <Input value={regTopN} onChange={setRegTopN} />
          </Form.Item>
          <Form.Item label={zh.rebalanceDays}>
            <Input value={regReb} onChange={setRegReb} />
          </Form.Item>
          <Form.Item label={zh.universeCode}>
            <Select
              value={regUniverse}
              onChange={setRegUniverse}
              options={UNIVERSE_OPTS}
            />
          </Form.Item>
          <Form.Item label={zh.factorType}>
            <Select
              value={regFactorType}
              onChange={setRegFactorType}
              options={["qfq", "hfq"]}
            />
          </Form.Item>
          <Form.Item label={zh.researchRunOpt}>
            <Input value={regResearch} onChange={setRegResearch} />
          </Form.Item>
          <Form.Item label={zh.backtestRunOpt}>
            <Input value={regBacktest} onChange={setRegBacktest} />
          </Form.Item>
          <Form.Item label={zh.noteOpt}>
            <Input.TextArea
              value={regNote}
              onChange={setRegNote}
              autoSize={{ minRows: 2 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={zh.promote}
        visible={open}
        onCancel={() => setOpen(false)}
        footer={
          <Space>
            <Button onClick={() => setOpen(false)}>取消</Button>
            {to === "BACKTESTED" || fromStatus === "DRAFT" ? (
              <Button
                type="outline"
                loading={btPromoteMut.isPending}
                disabled={liveLocked || !btRange[0] || !btRange[1]}
                onClick={() => btPromoteMut.mutate()}
              >
                {zh.runBtPromote}
              </Button>
            ) : null}
            <Button
              type="primary"
              loading={mut.isPending}
              disabled={promoteOkDisabled}
              title={promoteHint}
              onClick={() => {
                if (to === "BACKTESTED" && !backtestRun) {
                  Message.warning(zh.needBacktest);
                  return;
                }
                mut.mutate();
              }}
            >
              {zh.promote}
            </Button>
          </Space>
        }
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
          {to === "BACKTESTED" ? (
            <>
              <Form.Item label={zh.pickBacktest} required>
                <Select
                  allowClear
                  showSearch
                  placeholder={zh.backtestRun}
                  value={backtestRun || undefined}
                  onChange={(v) => setBacktestRun(v || "")}
                  options={btOptions}
                  loading={btQ.isLoading}
                />
              </Form.Item>
              <Form.Item label={zh.btRange}>
                <DatePicker.RangePicker
                  style={{ width: "100%" }}
                  value={btRange as unknown as never}
                  onChange={(ds) => {
                    if (Array.isArray(ds) && ds[0] && ds[1]) setBtRange(ds);
                  }}
                />
              </Form.Item>
              <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
                无合适回测时可点「{zh.runBtPromote}」：按策略参数跑 FACTOR_TOP_N
                后自动晋升（需区间 DQ 已 passed）。
              </Typography.Paragraph>
            </>
          ) : null}
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
