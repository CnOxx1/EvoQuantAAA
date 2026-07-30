/**
 * Frontend functional smoke: API + Playwright page crawl.
 * Usage: node scripts/fe_smoke.mjs
 */
import { chromium } from "playwright";

const API = process.env.API_BASE || "http://127.0.0.1:8088";
const FE = process.env.FE_BASE || "http://127.0.0.1:5173";

const routes = [
  "/",
  "/strategies",
  "/backtest",
  "/research",
  "/research/factors",
  "/research/freezes",
  "/signals",
  "/portfolio",
  "/portfolio/capital",
  "/ledger",
  "/trade",
  "/risk",
  "/ops",
  "/ops/schedule",
  "/data/quality",
  "/data/coverage",
  "/data/universe",
  "/data/ingest",
  "/data/process",
  "/market/monitor",
  "/market/boards",
  "/market/events",
  "/market/calendar",
  "/market/f10",
  "/system/modules",
  "/system/adapters",
  "/system/params",
  "/system/audit",
  "/settings",
];

const apiGets = [
  "/health",
  "/v1/strategies",
  "/v1/backtest/runs?limit=5",
  "/v1/research/runs?limit=5",
  "/v1/research/factors",
  "/v1/research/freezes?limit=5",
  "/v1/signal/batches?limit=5",
  "/v1/portfolios?limit=5",
  "/v1/ledger/capital-alloc",
  "/v1/ledger/accounts",
  "/v1/risk/kill",
  "/v1/risk/decisions?limit=5",
  "/v1/executions?limit=5",
  "/v1/execution/pending?status=open",
  "/v1/execution/adapters",
  "/v1/ops/alerts?limit=5",
  "/v1/ops/pipeline",
  "/v1/ops/activity?limit=5",
  "/v1/ops/audit?limit=5",
  "/v1/data/dq/runs?limit=5",
  "/v1/data/dq/gates?limit=5",
  "/v1/data/ingest/batches?limit=5",
  "/v1/data/process/batches?limit=5",
  "/v1/universe/snapshots?limit=5",
  "/v1/modules",
  "/v1/ref/cost-params",
  "/v1/ref/risk-limits",
  "/v1/ref/promotion-gates",
  "/v1/market/ranks/meta",
  "/v1/market/boards?limit=5",
];

function unwrap(json) {
  if (json && typeof json === "object" && "ok" in json) {
    if (json.ok === false) {
      const msg = json.error?.message || json.error?.code || "ok=false";
      throw new Error(msg);
    }
    return json.data;
  }
  return json;
}

async function apiGet(path) {
  const res = await fetch(`${API}${path}`, {
    headers: { Accept: "application/json" },
  });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`non-json ${res.status}`);
  }
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${json?.error?.message || text.slice(0, 120)}`);
  }
  return unwrap(json);
}

const results = {
  api: { pass: [], fail: [] },
  pages: { pass: [], fail: [] },
  interactions: { pass: [], fail: [] },
};

console.log("=== API smoke ===");
for (const path of apiGets) {
  try {
    const data = await apiGet(path);
    const hint =
      Array.isArray(data)
        ? `n=${data.length}`
        : data && typeof data === "object"
          ? `keys=${Object.keys(data).slice(0, 4).join(",")}`
          : typeof data;
    results.api.pass.push(`${path} (${hint})`);
    console.log(`OK  ${path} ${hint}`);
  } catch (e) {
    results.api.fail.push(`${path} :: ${e.message}`);
    console.log(`FAIL ${path} :: ${e.message}`);
  }
}

// write smoke: register then list contains it (paper-safe)
console.log("\n=== Write smoke (register) ===");
const code = `FTN_SMOKE_${Date.now().toString(36).toUpperCase().slice(-6)}`;
try {
  const body = {
    strategy_code: code,
    strategy_kind: "FACTOR_TOP_N",
    factor_code: "MOM_20",
    top_n: 20,
    rebalance_days: 20,
    universe_code: "TOP100",
    factor_type: "qfq",
    note: "fe_smoke",
  };
  const res = await fetch(`${API}/v1/strategies`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  const data = unwrap(json);
  if (!data?.strategy_version) throw new Error("no strategy_version");
  results.interactions.pass.push(`register ${code} -> ${data.strategy_version}`);
  console.log(`OK  register ${code} -> ${data.strategy_version}`);
} catch (e) {
  results.interactions.fail.push(`register :: ${e.message}`);
  console.log(`FAIL register :: ${e.message}`);
}

console.log("\n=== Playwright page crawl ===");
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const consoleErrors = [];
const ignoreNoise = (text) =>
  text.includes("Accessing element.ref was removed in React 19") ||
  text.includes("Download the React DevTools");

page.on("pageerror", (err) => {
  if (!ignoreNoise(err.message)) consoleErrors.push(err.message);
});
page.on("console", (msg) => {
  if (msg.type() !== "error") return;
  const text = msg.text();
  if (ignoreNoise(text)) return;
  consoleErrors.push(text);
});

// seed settings so UI points at our gateway
await page.addInitScript((apiBase) => {
  localStorage.setItem(
    "evoquant.settings.v2",
    JSON.stringify({
      apiBase,
      token: "",
      asOf: "2026-07-23",
      accountId: "paper_default",
      env: "paper",
    }),
  );
}, API);

await page.goto(FE, { waitUntil: "domcontentloaded", timeout: 30000 });
await page.waitForTimeout(800);

for (const route of routes) {
  const before = consoleErrors.length;
  try {
    await page.goto(`${FE}${route}`, { waitUntil: "networkidle", timeout: 45000 });
    await page.waitForTimeout(400);
    const title = await page.locator(".page, .arco-typography, h5, h6").first().isVisible().catch(() => false);
    const bodyText = await page.locator("body").innerText();
    const notConnected = bodyText.includes("未连接网关") && !bodyText.includes("已连接");
    const crashed = bodyText.includes("Something went wrong") || bodyText.includes("Unhandled");
    const newErrs = consoleErrors.slice(before);
    if (crashed) throw new Error("page crash text");
    if (notConnected && route !== "/settings") {
      // allow brief connect race; recheck footer badge
      const connected = await page.getByText("已连接").count();
      if (!connected) throw new Error("未连接网关");
    }
    if (newErrs.length) {
      throw new Error(`console: ${newErrs.slice(0, 2).join(" | ")}`);
    }
    results.pages.pass.push(`${route}${title ? "" : " (no .page)"}`);
    console.log(`OK  ${route}`);
  } catch (e) {
    results.pages.fail.push(`${route} :: ${e.message}`);
    console.log(`FAIL ${route} :: ${e.message}`);
  }
}

// UI interactions on strategies
console.log("\n=== UI interactions ===");
try {
  await page.goto(`${FE}/strategies`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(500);
  const regBtn = page.getByRole("button", { name: "注册策略" });
  await regBtn.click({ timeout: 10000 });
  await page.waitForSelector(".arco-modal", { timeout: 10000 });
  const visible = await page.locator(".arco-modal").isVisible();
  if (!visible) throw new Error("register modal not visible");
  await page.locator(".arco-modal-close-icon, .arco-icon-close").first().click({ timeout: 5000 }).catch(async () => {
    await page.keyboard.press("Escape");
  });
  results.interactions.pass.push("strategies: open register modal");
  console.log("OK  strategies register modal");
} catch (e) {
  results.interactions.fail.push(`strategies modal :: ${e.message}`);
  console.log(`FAIL strategies modal :: ${e.message}`);
}

try {
  await page.goto(`${FE}/`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(500);
  const allBtn = page.getByRole("button", { name: /一键跑通纸面/ });
  const count = await allBtn.count();
  if (!count) throw new Error("一键跑通纸面 button missing");
  const disabled = await allBtn.first().isDisabled();
  results.interactions.pass.push(`overview: paper-all button present disabled=${disabled}`);
  console.log(`OK  overview paper-all button disabled=${disabled}`);
} catch (e) {
  results.interactions.fail.push(`overview paper-all :: ${e.message}`);
  console.log(`FAIL overview paper-all :: ${e.message}`);
}

try {
  await page.goto(`${FE}/backtest`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(400);
  const btn = page.getByRole("button", { name: /跑 FACTOR_TOP_N/ });
  if (!(await btn.count())) throw new Error("run backtest button missing");
  await btn.click();
  await page.waitForSelector(".arco-modal", { timeout: 10000 });
  results.interactions.pass.push("backtest: open run modal");
  console.log("OK  backtest run modal");
} catch (e) {
  results.interactions.fail.push(`backtest modal :: ${e.message}`);
  console.log(`FAIL backtest modal :: ${e.message}`);
}

await browser.close();

const summary = {
  api: { pass: results.api.pass.length, fail: results.api.fail.length },
  pages: { pass: results.pages.pass.length, fail: results.pages.fail.length },
  interactions: {
    pass: results.interactions.pass.length,
    fail: results.interactions.fail.length,
  },
};

console.log("\n=== SUMMARY ===");
console.log(JSON.stringify(summary, null, 2));
if (results.api.fail.length || results.pages.fail.length || results.interactions.fail.length) {
  console.log("\nFAILURES:");
  for (const f of [...results.api.fail, ...results.pages.fail, ...results.interactions.fail]) {
    console.log(` - ${f}`);
  }
  process.exitCode = 1;
} else {
  console.log("ALL PASSED");
}
