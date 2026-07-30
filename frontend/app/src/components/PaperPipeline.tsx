import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Message,
  Space,
  Steps,
  Typography,
} from "@arco-design/web-react";
import {
  buildPortfolio,
  getKill,
  isKillOn,
  listDqGates,
  listStrategies,
  postLedger,
  reviewDrafts,
  runExecution,
  runSignal,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import {
  dqStatusForAsOf,
  fetchOpenTradeDays,
  isOpenTradeDay,
  prevOpenDay,
} from "../lib/tradeCalendar";
import { zh } from "../i18n/zh";
import { s } from "../lib/format";
import type { Settings } from "../state/settings";

const STEP_LABELS = [
  zh.runSignal,
  zh.buildPortfolio,
  zh.reviewDrafts,
  zh.runExec,
  zh.postLedger,
];

function firstId(data: unknown, keys: string[]): string {
  const row = Array.isArray(data) ? data[0] : data;
  if (!row || typeof row !== "object") return "ok";
  const obj = row as JsonMap;
  for (const k of keys) {
    if (obj[k] != null && String(obj[k])) return String(obj[k]);
  }
  return s(obj.status, "ok");
}

function collectExecutionIds(data: unknown): string[] {
  const rows = Array.isArray(data) ? data : data ? [data] : [];
  const ids: string[] = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const id = (row as JsonMap).execution_id;
    if (id != null && String(id)) ids.push(String(id));
  }
  return ids;
}

export function PaperPipeline({
  cfg,
  settings,
  connected,
  onSnapAsOf,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
  onSnapAsOf?: (day: string) => void;
}) {
  const qc = useQueryClient();
  const liveLocked = settings.env === "live";
  const asOf = settings.asOf;
  const accountId = settings.accountId;
  const [chainStep, setChainStep] = useState(-1);
  const [chainLog, setChainLog] = useState<string[]>([]);
  const [chaining, setChaining] = useState(false);

  const paperQ = useQuery({
    queryKey: ["strategies-paper", cfg.apiBase],
    queryFn: () => listStrategies(cfg, "PAPER"),
    enabled: connected,
  });
  const paperCount = paperQ.data?.length ?? 0;

  const calQ = useQuery({
    queryKey: ["trade-days", cfg.apiBase],
    queryFn: () => fetchOpenTradeDays(cfg),
    enabled: connected,
    staleTime: 60_000,
  });
  const dqQ = useQuery({
    queryKey: ["dq-gates", cfg.apiBase],
    queryFn: () => listDqGates(cfg, { limit: 80 }),
    enabled: connected,
    staleTime: 30_000,
  });
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: connected,
    refetchInterval: 10_000,
  });

  const openDays = calQ.data ?? [];
  const tradeOk = asOf ? isOpenTradeDay(openDays, asOf) : false;
  const prev = asOf && openDays.length ? prevOpenDay(openDays, asOf) : null;
  const dq = dqStatusForAsOf(dqQ.data ?? [], asOf || "");
  const killOn = isKillOn(killQ.data);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["strategies"] });
    void qc.invalidateQueries({ queryKey: ["strategies-paper"] });
    void qc.invalidateQueries({ queryKey: ["portfolios"] });
    void qc.invalidateQueries({ queryKey: ["executions"] });
    void qc.invalidateQueries({ queryKey: ["pending"] });
    void qc.invalidateQueries({ queryKey: ["pipeline"] });
    void qc.invalidateQueries({ queryKey: ["decisions"] });
    void qc.invalidateQueries({ queryKey: ["ledger"] });
    void qc.invalidateQueries({ queryKey: ["signals-day"] });
    void qc.invalidateQueries({ queryKey: ["portfolios-day"] });
    void qc.invalidateQueries({ queryKey: ["dq-gates"] });
  };

  const signalMut = useMutation({
    mutationFn: () =>
      runSignal(cfg, { as_of: asOf, paper: true, live: false }),
    onSuccess: () => {
      Message.success(zh.runSignal);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });
  const buildMut = useMutation({
    mutationFn: () =>
      buildPortfolio(cfg, {
        as_of: asOf,
        account_id: accountId,
        paper: true,
        live: false,
        use_ledger_nav: true,
      }),
    onSuccess: () => {
      Message.success(zh.buildPortfolio);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });
  const reviewMut = useMutation({
    mutationFn: () => reviewDrafts(cfg, asOf),
    onSuccess: () => {
      Message.success(zh.reviewDrafts);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });
  const execMut = useMutation({
    mutationFn: async () => {
      const ex = await runExecution(cfg, {
        approved: true,
        as_of: asOf,
        account_id: accountId,
        adapter: "paper",
      });
      const ids = collectExecutionIds(ex);
      for (const executionId of ids) {
        try {
          await postLedger(cfg, { execution_id: executionId });
        } catch {
          /* already posted or empty fills — surface via later ledger */
        }
      }
      return { ex, posted: ids.length };
    },
    onSuccess: (r) => {
      Message.success(
        r.posted ? `${zh.runExec} · 已过账 ${r.posted}` : zh.runExec,
      );
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const blockers = useMemo(() => {
    const list: { key: string; text: ReactNode }[] = [];
    if (!connected) list.push({ key: "conn", text: zh.notConnected });
    if (liveLocked) list.push({ key: "live", text: zh.liveLocked });
    if (!asOf) {
      list.push({
        key: "asof",
        text: (
          <>
            未设置业务日 · <Link to="/settings">去设置</Link>
          </>
        ),
      });
    }
    if (asOf && openDays.length && !tradeOk) {
      list.push({
        key: "cal",
        text: (
          <>
            {asOf} 非开市日
            {prev ? (
              <>
                {" "}
                ·{" "}
                {onSnapAsOf ? (
                  <a
                    href="#snap"
                    onClick={(e) => {
                      e.preventDefault();
                      onSnapAsOf(prev);
                    }}
                  >
                    对齐 {prev}
                  </a>
                ) : (
                  <code>{prev}</code>
                )}
              </>
            ) : null}
            {" · "}
            <Link to="/market/calendar">交易日历</Link>
          </>
        ),
      });
    }
    if (asOf && !dqQ.isLoading && !dq.ok) {
      list.push({
        key: "dq",
        text: (
          <>
            DQ 未通过：{dq.detail} · <Link to="/data/quality">数据质量</Link> /{" "}
            <Link to="/ops/schedule">日更编排</Link>
          </>
        ),
      });
    }
    if (killOn) {
      list.push({
        key: "kill",
        text: (
          <>
            Kill Switch 已开启 · <Link to="/risk">去关闭</Link>
          </>
        ),
      });
    }
    if (connected && !paperQ.isLoading && paperCount === 0) {
      list.push({
        key: "paper",
        text: (
          <>
            没有 PAPER 策略 · <Link to="/strategies">去注册/晋升</Link>
          </>
        ),
      });
    }
    return list;
  }, [
    connected,
    liveLocked,
    asOf,
    paperCount,
    paperQ.isLoading,
    openDays.length,
    tradeOk,
    prev,
    onSnapAsOf,
    dq,
    dqQ.isLoading,
    killOn,
  ]);

  const disabled = blockers.length > 0;
  const busy =
    chaining ||
    signalMut.isPending ||
    buildMut.isPending ||
    reviewMut.isPending ||
    execMut.isPending;
  const disableReason = blockers.length
    ? "请先消除上方阻断条件"
    : undefined;

  const runAll = async () => {
    if (disabled) return;
    setChaining(true);
    setChainLog([]);
    const log: string[] = [];
    try {
      setChainStep(0);
      const sig = await runSignal(cfg, {
        as_of: asOf,
        paper: true,
        live: false,
      });
      log.push(`1. 信号 ok · ${firstId(sig, ["signal_batch_id", "batch_id"])}`);
      setChainLog([...log]);

      setChainStep(1);
      const pf = await buildPortfolio(cfg, {
        as_of: asOf,
        account_id: accountId,
        paper: true,
        live: false,
        use_ledger_nav: true,
      });
      log.push(`2. 组合 ok · ${firstId(pf, ["portfolio_id"])}`);
      setChainLog([...log]);

      setChainStep(2);
      const rv = await reviewDrafts(cfg, asOf);
      log.push(`3. 审核 ok · ${firstId(rv, ["count", "decision_id"])}`);
      setChainLog([...log]);

      setChainStep(3);
      const ex = await runExecution(cfg, {
        approved: true,
        as_of: asOf,
        account_id: accountId,
        adapter: "paper",
      });
      const ids = collectExecutionIds(ex);
      log.push(`4. 执行 ok · ${ids.join(",") || firstId(ex, ["execution_id"])}`);
      setChainLog([...log]);

      setChainStep(4);
      let posted = 0;
      for (const executionId of ids) {
        try {
          await postLedger(cfg, { execution_id: executionId });
          posted += 1;
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          log.push(`过账跳过 ${executionId} · ${msg}`);
          setChainLog([...log]);
        }
      }
      log.push(`5. 过账 ok · ${posted}/${ids.length}`);
      setChainLog([...log]);
      setChainStep(5);
      Message.success(zh.paperPipeDone);
      invalidate();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      log.push(`失败 · ${msg}`);
      setChainLog([...log]);
      Message.error(msg);
    } finally {
      setChaining(false);
    }
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <Typography.Title heading={6} style={{ marginTop: 0 }}>
        {zh.paperPipe}
      </Typography.Title>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        as_of={asOf || "—"} · account={accountId} · adapter=paper · PAPER=
        {paperQ.isLoading ? "…" : paperCount}
        {asOf ? ` · 开市=${tradeOk ? "是" : "否"} · DQ=${dq.status}` : ""}
        {killOn ? " · Kill=ON" : ""}
      </Typography.Text>
      {blockers.length ? (
        <Alert
          style={{ marginTop: 8 }}
          type="warning"
          content={
            <Space direction="vertical" size={2}>
              {blockers.map((b) => (
                <span key={b.key}>{b.text}</span>
              ))}
            </Space>
          }
        />
      ) : (
        <Alert
          style={{ marginTop: 8 }}
          type="success"
          content="前置条件已满足：可跑信号→组合→审核→执行→过账"
        />
      )}
      <Space wrap style={{ marginTop: 8 }}>
        <Button
          size="small"
          type="primary"
          disabled={disabled || busy}
          loading={chaining}
          title={disableReason}
          onClick={() => void runAll()}
        >
          {zh.paperPipeAll}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={signalMut.isPending}
          title={disableReason}
          onClick={() => signalMut.mutate()}
        >
          1. {zh.runSignal}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={buildMut.isPending}
          title={disableReason}
          onClick={() => buildMut.mutate()}
        >
          2. {zh.buildPortfolio}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={reviewMut.isPending}
          title={disableReason}
          onClick={() => reviewMut.mutate()}
        >
          3. {zh.reviewDrafts}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={execMut.isPending}
          title={disableReason}
          onClick={() => execMut.mutate()}
        >
          4–5. {zh.runExec}+{zh.postLedger}
        </Button>
      </Space>
      {chainStep >= 0 ? (
        <div style={{ marginTop: 12 }}>
          <Steps
            size="small"
            current={Math.min(chainStep, 4)}
            status={
              chaining
                ? "process"
                : chainLog.some((l) => l.startsWith("失败"))
                  ? "error"
                  : chainStep >= 5
                    ? "finish"
                    : "process"
            }
          >
            {STEP_LABELS.map((lab) => (
              <Steps.Step key={lab} title={lab} />
            ))}
          </Steps>
          <Typography.Paragraph
            style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}
            type="secondary"
          >
            {chainLog.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </Typography.Paragraph>
        </div>
      ) : null}
    </div>
  );
}
