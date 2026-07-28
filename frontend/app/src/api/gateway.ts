import { apiRequest, type ClientConfig, unwrapData } from "./client";

export type { ClientConfig };

export type StrategyRow = Record<string, unknown> & {
  strategy_version?: string;
  status?: string;
  strategy_id?: string;
};

export type PortfolioRow = Record<string, unknown> & {
  portfolio_id?: string;
  status?: string;
  as_of_date?: string;
  as_of?: string;
  account_id?: string;
  strategy_version?: string;
};

export type KillStatus = Record<string, unknown> & {
  is_on?: boolean;
  scopes?: string[];
  kill_switches?: Array<Record<string, unknown>>;
  rows?: unknown[];
};

export function isKillOn(data: KillStatus | undefined | null): boolean {
  if (!data) return false;
  if (typeof data.is_on === "boolean") return data.is_on;
  const rows = (data.kill_switches || []) as Array<{ is_on?: number | boolean }>;
  return rows.some((r) => Number(r.is_on) === 1 || r.is_on === true);
}

export type DecisionRow = Record<string, unknown> & {
  decision_id?: string;
  portfolio_id?: string;
  status?: string;
  created_at?: string;
  reason?: string;
  message?: string;
};

export type AlertRow = Record<string, unknown> & {
  alert_id?: string;
  severity?: string;
  message?: string;
  title?: string;
  created_at?: string;
};

export type LedgerSnapshot = Record<string, unknown> & {
  account_id?: string;
  cash?: number;
  balance?: { cash?: number };
};

function asList<T>(env: unknown): T[] {
  const data = unwrapData(env);
  return Array.isArray(data) ? (data as T[]) : [];
}

export async function getHealth(cfg: ClientConfig) {
  return apiRequest<{ ok: boolean }>(cfg, "GET", "/health");
}

export async function listStrategies(cfg: ClientConfig, limit = 50) {
  return asList<StrategyRow>(
    await apiRequest(cfg, "GET", `/v1/strategies?limit=${limit}`),
  );
}

export async function listPortfolios(
  cfg: ClientConfig,
  opts?: { status?: string; asOf?: string; limit?: number },
) {
  const q = new URLSearchParams();
  q.set("limit", String(opts?.limit ?? 50));
  if (opts?.status) q.set("status", opts.status);
  if (opts?.asOf) q.set("as_of", opts.asOf);
  return asList<PortfolioRow>(
    await apiRequest(cfg, "GET", `/v1/portfolios?${q}`),
  );
}

export async function getPortfolio(cfg: ClientConfig, portfolioId: string) {
  return unwrapData(
    await apiRequest(cfg, "GET", `/v1/portfolios/${portfolioId}`),
  ) as Record<string, unknown>;
}

export async function getKill(cfg: ClientConfig): Promise<KillStatus> {
  return (unwrapData(await apiRequest(cfg, "GET", "/v1/risk/kill")) ||
    {}) as KillStatus;
}

export async function setKill(
  cfg: ClientConfig,
  body: { scope: string; is_on: boolean; reason?: string },
) {
  return apiRequest(cfg, "POST", "/v1/risk/kill", body);
}

export async function promoteStrategy(
  cfg: ClientConfig,
  version: string,
  body: {
    to: string;
    backtest_run?: string;
    reason?: string;
    skip_gates?: boolean;
    gate_version?: string;
  },
) {
  return apiRequest(cfg, "POST", `/v1/strategies/${version}/promote`, body);
}

export async function reviewRisk(
  cfg: ClientConfig,
  body: {
    portfolio_id?: string;
    drafts?: boolean;
    as_of?: string;
    force?: boolean;
  },
) {
  return apiRequest(cfg, "POST", "/v1/risk/review", body);
}

export async function listDecisions(cfg: ClientConfig, limit = 20) {
  return asList<DecisionRow>(
    await apiRequest(cfg, "GET", `/v1/risk/decisions?limit=${limit}`),
  );
}

export async function listAlerts(cfg: ClientConfig, limit = 20) {
  return asList<AlertRow>(
    await apiRequest(cfg, "GET", `/v1/ops/alerts?limit=${limit}`),
  );
}

export async function getLedger(
  cfg: ClientConfig,
  accountId: string,
  asOf?: string,
) {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return (unwrapData(
    await apiRequest(cfg, "GET", `/v1/ledger/accounts/${accountId}${q}`),
  ) || {}) as LedgerSnapshot;
}

export type ExecutionRow = Record<string, unknown> & {
  execution_id?: string;
  portfolio_id?: string;
  account_id?: string;
  status?: string;
  adapter?: string;
  as_of_date?: string;
  order_count?: number;
  fill_count?: number;
};

export type PendingRow = Record<string, unknown> & {
  pending_id?: string;
  symbol?: string;
  side?: string;
  qty_remaining?: number;
  status?: string;
};

export type ResearchRunRow = Record<string, unknown> & {
  run_id?: string;
  factor_code?: string;
  universe_code?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
};

export async function listExecutions(
  cfg: ClientConfig,
  opts?: { accountId?: string; limit?: number },
) {
  const q = new URLSearchParams();
  q.set("limit", String(opts?.limit ?? 50));
  if (opts?.accountId) q.set("account_id", opts.accountId);
  return asList<ExecutionRow>(
    await apiRequest(cfg, "GET", `/v1/executions?${q}`),
  );
}

export async function getExecution(cfg: ClientConfig, executionId: string) {
  return (unwrapData(
    await apiRequest(cfg, "GET", `/v1/executions/${executionId}`),
  ) || {}) as Record<string, unknown>;
}

export async function listPending(
  cfg: ClientConfig,
  opts?: { accountId?: string; status?: string; limit?: number },
) {
  const q = new URLSearchParams();
  q.set("limit", String(opts?.limit ?? 100));
  if (opts?.accountId) q.set("account_id", opts.accountId);
  if (opts?.status) q.set("status", opts.status);
  return asList<PendingRow>(
    await apiRequest(cfg, "GET", `/v1/execution/pending?${q}`),
  );
}

export async function listResearchRuns(cfg: ClientConfig, limit = 50) {
  return asList<ResearchRunRow>(
    await apiRequest(cfg, "GET", `/v1/research/runs?limit=${limit}`),
  );
}
