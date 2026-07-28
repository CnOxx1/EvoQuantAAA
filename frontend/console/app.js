(function () {
  const $ = (id) => document.getElementById(id);

  function headers(json) {
    const h = { Accept: "application/json" };
    if (json) h["Content-Type"] = "application/json";
    const token = $("apiToken").value.trim();
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }

  function base() {
    return $("apiBase").value.replace(/\/$/, "");
  }

  function pretty(data) {
    return JSON.stringify(data, null, 2);
  }

  function showAction(title, payload) {
    $("actionBox").textContent = `${title}\n${pretty(payload)}`;
  }

  async function request(method, path, body) {
    const opts = { method, headers: headers(body !== undefined) };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(`${base()}${path}`, opts);
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
    if (!res.ok) {
      const detail = data.detail !== undefined ? data.detail : data;
      const err = new Error(`HTTP ${res.status}`);
      err.body = detail;
      err.status = res.status;
      throw err;
    }
    return data;
  }

  async function get(path) {
    return request("GET", path);
  }

  async function post(path, body) {
    return request("POST", path, body);
  }

  async function refresh() {
    const line = $("statusLine");
    line.className = "status";
    line.textContent = "加载中…";
    try {
      const health = await get("/health");
      if (!health.ok) throw new Error("health not ok");

      const [kill, strat, pf, ledger, alerts] = await Promise.all([
        get("/v1/risk/kill"),
        get("/v1/strategies?limit=30"),
        get("/v1/portfolios?limit=20"),
        get("/v1/ledger/accounts/paper_default"),
        get("/v1/ops/alerts?limit=20"),
      ]);

      $("killBox").textContent = pretty(kill.data ?? kill);
      $("stratBox").textContent = pretty(strat.data ?? strat);
      $("pfBox").textContent = pretty(pf.data ?? pf);
      $("ledgerBox").textContent = pretty(ledger.data ?? ledger);
      $("alertBox").textContent = pretty(alerts.data ?? alerts);

      line.className = "status ok";
      line.textContent = `已连接 ${base()} · ${new Date().toLocaleTimeString()}`;
    } catch (e) {
      line.className = "status err";
      line.textContent = `失败：${e.message}（请先启动 gateway，并确认 CORS/Token）`;
      console.error(e.body || e);
    }
  }

  $("killForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const submitter = ev.submitter;
    const isOn = submitter && submitter.value === "on";
    const scope = $("killScope").value.trim() || "GLOBAL";
    const reason = $("killReason").value.trim() || undefined;
    if (isOn && !confirm(`确认开启 Kill Switch？scope=${scope}`)) return;
    try {
      const body = await post("/v1/risk/kill", {
        scope,
        is_on: !!isOn,
        reason,
      });
      showAction(`Kill ${isOn ? "ON" : "OFF"} · ${scope}`, body.data ?? body);
      await refresh();
    } catch (e) {
      showAction(`Kill 失败 HTTP ${e.status || "?"}`, e.body || { message: e.message });
    }
  });

  $("promoteForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const version = $("promoteVersion").value.trim();
    const to = $("promoteTo").value;
    const backtest = $("promoteBacktest").value.trim() || undefined;
    const reason = $("promoteReason").value.trim() || undefined;
    const skip = $("promoteSkipGates").checked;
    if (!version) {
      showAction("晋升校验失败", { message: "需要 strategy_version" });
      return;
    }
    if (skip && !reason) {
      showAction("晋升校验失败", { message: "跳过质量门必须填写原因" });
      return;
    }
    if (!confirm(`确认晋升 ${version} → ${to}${skip ? "（跳过质量门）" : ""}？`)) {
      return;
    }
    try {
      const body = await post(`/v1/strategies/${encodeURIComponent(version)}/promote`, {
        to,
        backtest_run: backtest,
        reason,
        skip_gates: skip,
      });
      showAction(`Promote ${version} → ${to}`, body.data ?? body);
      await refresh();
    } catch (e) {
      showAction(`Promote 失败 HTTP ${e.status || "?"}`, e.body || { message: e.message });
    }
  });

  $("reviewForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const portfolioId = $("reviewPortfolio").value.trim() || undefined;
    const drafts = $("reviewDrafts").checked;
    const asOf = $("reviewAsOf").value || undefined;
    const force = $("reviewForce").checked;
    if (!portfolioId && !drafts) {
      showAction("审核校验失败", {
        message: "请填写 portfolio_id，或勾选审核全部 draft",
      });
      return;
    }
    if (drafts && !asOf) {
      showAction("审核校验失败", { message: "批量 draft 需要 as_of" });
      return;
    }
    try {
      const body = await post("/v1/risk/review", {
        portfolio_id: portfolioId,
        drafts,
        as_of: asOf,
        force,
      });
      showAction("Risk review", body.data ?? body);
      await refresh();
    } catch (e) {
      showAction(`Review 失败 HTTP ${e.status || "?"}`, e.body || { message: e.message });
    }
  });

  $("btnRefresh").addEventListener("click", refresh);
  refresh();
})();
