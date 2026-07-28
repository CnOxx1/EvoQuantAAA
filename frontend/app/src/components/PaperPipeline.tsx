import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, Message, Space, Typography } from "@arco-design/web-react";
import {
  buildPortfolio,
  reviewDrafts,
  runExecution,
  runSignal,
  type ClientConfig,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import type { Settings } from "../state/settings";

export function PaperPipeline({
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
  const asOf = settings.asOf;
  const accountId = settings.accountId;

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["strategies"] });
    void qc.invalidateQueries({ queryKey: ["portfolios"] });
    void qc.invalidateQueries({ queryKey: ["executions"] });
    void qc.invalidateQueries({ queryKey: ["pending"] });
    void qc.invalidateQueries({ queryKey: ["pipeline"] });
    void qc.invalidateQueries({ queryKey: ["decisions"] });
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
    mutationFn: () =>
      runExecution(cfg, {
        approved: true,
        as_of: asOf,
        account_id: accountId,
        adapter: "paper",
      }),
    onSuccess: () => {
      Message.success(zh.runExec);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const disabled = !connected || liveLocked || !asOf;
  const busy =
    signalMut.isPending ||
    buildMut.isPending ||
    reviewMut.isPending ||
    execMut.isPending;

  return (
    <div style={{ marginBottom: 12 }}>
      <Typography.Title heading={6} style={{ marginTop: 0 }}>
        {zh.paperPipe}
      </Typography.Title>
      {liveLocked ? (
        <Typography.Text type="warning">{zh.liveLocked}</Typography.Text>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          as_of={asOf || "—"} · account={accountId} · adapter=paper
        </Typography.Text>
      )}
      <Space wrap style={{ marginTop: 8 }}>
        <Button
          size="small"
          disabled={disabled}
          loading={signalMut.isPending}
          onClick={() => signalMut.mutate()}
        >
          1. {zh.runSignal}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={buildMut.isPending}
          onClick={() => buildMut.mutate()}
        >
          2. {zh.buildPortfolio}
        </Button>
        <Button
          size="small"
          disabled={disabled || busy}
          loading={reviewMut.isPending}
          onClick={() => reviewMut.mutate()}
        >
          3. {zh.reviewDrafts}
        </Button>
        <Button
          size="small"
          type="primary"
          disabled={disabled || busy}
          loading={execMut.isPending}
          onClick={() => execMut.mutate()}
        >
          4. {zh.runExec}
        </Button>
      </Space>
    </div>
  );
}
