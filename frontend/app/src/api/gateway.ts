export type ClientConfig = {
  apiBase: string;
  token: string;
};

export type JsonMap = Record<string, unknown>;

type Envelope<T> = {
  ok: boolean;
  data?: T;
  error?: { code?: string; message?: string; detail?: string };
};

async function request<T>(
  cfg: ClientConfig,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (cfg.token) headers.set("Authorization", `Bearer ${cfg.token}`);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${cfg.apiBase.replace(/\/$/, "")}${path}`, {
    ...init,
    headers,
  });
  const body = (await res.json().catch(() => ({}))) as Envelope<T>;
  if (!res.ok || body.ok === false) {
    const msg =
      body.error?.message ||
      body.error?.detail ||
      body.error?.code ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body.data as T;
}

export async function health(cfg: ClientConfig) {
  const res = await fetch(`${cfg.apiBase.replace(/\/$/, "")}/health`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

export function listStrategies(cfg: ClientConfig, status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<JsonMap[]>(cfg, `/v1/strategies${q}`);
}

export function getStrategy(cfg: ClientConfig, version: string) {
  return request<JsonMap>(
    cfg,
    `/v1/strategies/${encodeURIComponent(version)}`,
  );
}

export function promoteStrategy(
  cfg: ClientConfig,
  version: string,
  body: JsonMap,
) {
  return request(cfg, `/v1/strategies/${encodeURIComponent(version)}/promote`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listPortfolios(
  cfg: ClientConfig,
  opts?: { status?: string; asOf?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.status) p.set("status", opts.status);
  if (opts?.asOf) p.set("as_of", opts.asOf);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<JsonMap[]>(cfg, `/v1/portfolios${q}`);
}

export function getPortfolio(cfg: ClientConfig, id: string) {
  return request<JsonMap>(cfg, `/v1/portfolios/${encodeURIComponent(id)}`);
}

export function buildPortfolio(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/portfolios/build", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type KillStatus = JsonMap;

export function getKill(cfg: ClientConfig) {
  return request<KillStatus>(cfg, "/v1/risk/kill");
}

export function setKill(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/risk/kill", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function isKillOn(kill?: KillStatus) {
  if (!kill) return false;
  const switches = (kill.kill_switches as JsonMap[] | undefined) ?? [];
  if (switches.length) {
    return switches.some(
      (s) =>
        String(s.scope_key) === "GLOBAL" &&
        (Number(s.is_on) === 1 || s.is_on === true),
    );
  }
  return Number(kill.is_on) === 1 || kill.is_on === true;
}

export function reviewPortfolio(cfg: ClientConfig, portfolioId: string) {
  return request(cfg, "/v1/risk/review", {
    method: "POST",
    body: JSON.stringify({ portfolio_id: portfolioId }),
  });
}

export function reviewDrafts(cfg: ClientConfig, asOf?: string) {
  return request(cfg, "/v1/risk/review", {
    method: "POST",
    body: JSON.stringify({ drafts: true, as_of: asOf || undefined }),
  });
}

export function listDecisions(cfg: ClientConfig, limit = 50) {
  return request<JsonMap[]>(cfg, `/v1/risk/decisions?limit=${limit}`);
}

export function getDecision(cfg: ClientConfig, id: string) {
  return request<JsonMap>(
    cfg,
    `/v1/risk/decisions/${encodeURIComponent(id)}`,
  );
}

export function listExecutions(cfg: ClientConfig, limit = 50) {
  return request<JsonMap[]>(cfg, `/v1/executions?limit=${limit}`);
}

export function getExecution(cfg: ClientConfig, id: string) {
  return request<JsonMap>(cfg, `/v1/executions/${encodeURIComponent(id)}`);
}

export function runExecution(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/executions/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listPending(cfg: ClientConfig, accountId?: string) {
  const q = accountId
    ? `?account_id=${encodeURIComponent(accountId)}&status=open`
    : "?status=open";
  return request<JsonMap[]>(cfg, `/v1/execution/pending${q}`);
}

export function resumePending(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/execution/pending/resume", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listResearchRuns(cfg: ClientConfig, limit = 50) {
  return request<JsonMap[]>(cfg, `/v1/research/runs?limit=${limit}`);
}

export function getResearchRun(cfg: ClientConfig, runId: string) {
  return request<JsonMap>(
    cfg,
    `/v1/research/runs/${encodeURIComponent(runId)}`,
  );
}

export function listSignalBatches(cfg: ClientConfig, limit = 50) {
  return request<JsonMap[]>(cfg, `/v1/signal/batches?limit=${limit}`);
}

export function runSignal(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/signal/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postLedger(cfg: ClientConfig, body: JsonMap) {
  return request(cfg, "/v1/ledger/post", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type PipelineStage = {
  name: string;
  ok: boolean;
  detail?: string;
};

export type PipelineStatus = {
  stages: PipelineStage[];
  counts: Record<string, number>;
  kill_on: boolean;
  dq_status: string;
  alert_levels: Record<string, number>;
};

export function getOpsPipeline(cfg: ClientConfig) {
  return request<PipelineStatus>(cfg, "/v1/ops/pipeline");
}

export function getMarketRankMeta(cfg: ClientConfig) {
  return request<{ trade_dates: string[]; rank_types: string[] }>(
    cfg,
    "/v1/market/ranks/meta",
  );
}

export function listMarketRanks(
  cfg: ClientConfig,
  opts: { tradeDate: string; rankType?: string; limit?: number },
) {
  const p = new URLSearchParams({ trade_date: opts.tradeDate });
  if (opts.rankType) p.set("rank_type", opts.rankType);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<JsonMap[]>(cfg, `/v1/market/ranks?${p}`);
}

export function listAbnormalMoves(
  cfg: ClientConfig,
  opts: { tradeDate: string; limit?: number },
) {
  const p = new URLSearchParams({ trade_date: opts.tradeDate });
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<JsonMap[]>(cfg, `/v1/market/abnormal?${p}`);
}

export function listNews(
  cfg: ClientConfig,
  opts: { channel?: string; symbol?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts.channel) p.set("channel", opts.channel);
  if (opts.symbol) p.set("symbol", opts.symbol);
  if (opts.limit) p.set("limit", String(opts.limit));
  const q = p.toString();
  return request<JsonMap[]>(cfg, `/v1/market/news${q ? `?${q}` : ""}`);
}

export function listDragonTiger(
  cfg: ClientConfig,
  opts: { tradeDate: string; limit?: number },
) {
  const p = new URLSearchParams({ trade_date: opts.tradeDate });
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<JsonMap[]>(cfg, `/v1/market/dragon-tiger?${p}`);
}

export type MarketBarsResponse = {
  symbol: string;
  factor_type: string;
  freq?: string;
  count: number;
  bars: JsonMap[];
};

export function listMarketBars(
  cfg: ClientConfig,
  opts: {
    symbol: string;
    start?: string;
    end?: string;
    factorType?: string;
    freq?: string;
    limit?: number;
  },
) {
  const p = new URLSearchParams({ symbol: opts.symbol });
  if (opts.start) p.set("start", opts.start);
  if (opts.end) p.set("end", opts.end);
  if (opts.factorType) p.set("factor_type", opts.factorType);
  if (opts.freq) p.set("freq", opts.freq);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<MarketBarsResponse>(cfg, `/v1/market/bars?${p}`);
}

export type IndicatorPoint = { trade_date: string; value: number };
export type IndicatorsResponse = {
  symbol: string;
  factor_type: string;
  codes: string[];
  count: number;
  series: Record<string, IndicatorPoint[]>;
};

export type IndicatorMetaItem = {
  code: string;
  count: number;
  category: string;
  category_zh: string;
  placement: "overlay" | "sub";
  style: "line" | "hist";
};

export type IndicatorsMetaResponse = {
  core_codes: string[];
  categories: string[];
  codes: IndicatorMetaItem[];
  total: number;
};

export function listMarketIndicators(
  cfg: ClientConfig,
  opts: {
    symbol: string;
    codes?: string[];
    start?: string;
    end?: string;
    factorType?: string;
    limit?: number;
  },
) {
  const p = new URLSearchParams({ symbol: opts.symbol });
  if (opts.codes?.length) p.set("codes", opts.codes.join(","));
  if (opts.start) p.set("start", opts.start);
  if (opts.end) p.set("end", opts.end);
  if (opts.factorType) p.set("factor_type", opts.factorType);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<IndicatorsResponse>(cfg, `/v1/market/indicators?${p}`);
}

export function getMarketIndicatorsMeta(
  cfg: ClientConfig,
  opts?: { symbol?: string },
) {
  const p = new URLSearchParams();
  if (opts?.symbol) p.set("symbol", opts.symbol);
  const q = p.toString() ? `?${p}` : "";
  return request<IndicatorsMetaResponse>(cfg, `/v1/market/indicators/meta${q}`);
}

export function getLedger(cfg: ClientConfig, accountId: string, asOf?: string) {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return request<JsonMap>(
    cfg,
    `/v1/ledger/accounts/${encodeURIComponent(accountId)}${q}`,
  );
}

export function listAlerts(cfg: ClientConfig, limit = 50) {
  return request<JsonMap[]>(cfg, `/v1/ops/alerts?limit=${limit}`);
}

export function listBacktestRuns(
  cfg: ClientConfig,
  opts?: { status?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.status) p.set("status", opts.status);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<JsonMap[]>(cfg, `/v1/backtest/runs${q}`);
}

export function getBacktestRun(cfg: ClientConfig, runId: string) {
  return request<JsonMap>(
    cfg,
    `/v1/backtest/runs/${encodeURIComponent(runId)}`,
  );
}

export function searchSecurities(
  cfg: ClientConfig,
  opts: { q: string; asOf?: string; limit?: number },
) {
  const p = new URLSearchParams({ q: opts.q });
  if (opts.asOf) p.set("as_of", opts.asOf);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<{ q: string; count: number; items: JsonMap[] }>(
    cfg,
    `/v1/market/search?${p}`,
  );
}

export function listBoards(
  cfg: ClientConfig,
  opts?: { tradeDate?: string; boardType?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.tradeDate) p.set("trade_date", opts.tradeDate);
  if (opts?.boardType) p.set("board_type", opts.boardType);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<{ trade_date?: string; count: number; items: JsonMap[] }>(
    cfg,
    `/v1/market/boards${q}`,
  );
}

export function listBoardHistory(
  cfg: ClientConfig,
  opts: {
    boardName: string;
    boardType?: string;
    start?: string;
    end?: string;
    limit?: number;
  },
) {
  const p = new URLSearchParams({ board_name: opts.boardName });
  if (opts.boardType) p.set("board_type", opts.boardType);
  if (opts.start) p.set("start", opts.start);
  if (opts.end) p.set("end", opts.end);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<{ board_name: string; count: number; bars: JsonMap[] }>(
    cfg,
    `/v1/market/boards/history?${p}`,
  );
}

export function listBoardMembers(
  cfg: ClientConfig,
  opts: {
    industryName?: string;
    industryCode?: string;
    asOf?: string;
    limit?: number;
  },
) {
  const p = new URLSearchParams();
  if (opts.industryName) p.set("industry_name", opts.industryName);
  if (opts.industryCode) p.set("industry_code", opts.industryCode);
  if (opts.asOf) p.set("as_of", opts.asOf);
  if (opts.limit) p.set("limit", String(opts.limit));
  return request<{ count: number; items: JsonMap[] }>(
    cfg,
    `/v1/market/boards/members?${p}`,
  );
}

export function listMarketEvents(
  cfg: ClientConfig,
  opts?: { start?: string; end?: string; symbol?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.start) p.set("start", opts.start);
  if (opts?.end) p.set("end", opts.end);
  if (opts?.symbol) p.set("symbol", opts.symbol);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<{ count: number; items: JsonMap[] }>(
    cfg,
    `/v1/market/events${q}`,
  );
}

export function listEconCalendar(
  cfg: ClientConfig,
  opts?: { start?: string; end?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.start) p.set("start", opts.start);
  if (opts?.end) p.set("end", opts.end);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<{
    start: string;
    end: string;
    trade_days: JsonMap[];
    macro_news: JsonMap[];
  }>(cfg, `/v1/market/calendar${q}`);
}

export function getF10(cfg: ClientConfig, symbol: string, asOf?: string) {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return request<JsonMap>(
    cfg,
    `/v1/market/f10/${encodeURIComponent(symbol)}${q}`,
  );
}

export function listDqRuns(
  cfg: ClientConfig,
  opts?: { scope?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.scope) p.set("scope", opts.scope);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<JsonMap[]>(cfg, `/v1/data/dq/runs${q}`);
}

export function getDqRun(cfg: ClientConfig, id: string) {
  return request<JsonMap>(cfg, `/v1/data/dq/runs/${encodeURIComponent(id)}`);
}

export function listDqGates(
  cfg: ClientConfig,
  opts?: { scope?: string; limit?: number },
) {
  const p = new URLSearchParams();
  if (opts?.scope) p.set("scope", opts.scope);
  if (opts?.limit) p.set("limit", String(opts.limit));
  const q = p.toString() ? `?${p}` : "";
  return request<JsonMap[]>(cfg, `/v1/data/dq/gates${q}`);
}

export function getDataCoverage(
  cfg: ClientConfig,
  opts: { start: string; end: string; symbols?: string },
) {
  const p = new URLSearchParams({ start: opts.start, end: opts.end });
  if (opts.symbols) p.set("symbols", opts.symbols);
  return request<JsonMap>(cfg, `/v1/data/coverage?${p}`);
}
