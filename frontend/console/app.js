(function () {
  const $ = (id) => document.getElementById(id);

  function headers() {
    const h = { Accept: "application/json" };
    const token = $("apiToken").value.trim();
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }

  function base() {
    return $("apiBase").value.replace(/\/$/, "");
  }

  async function get(path) {
    const res = await fetch(`${base()}${path}`, { headers: headers() });
    const text = await res.text();
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      body = { raw: text };
    }
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.body = body;
      throw err;
    }
    return body;
  }

  function pretty(data) {
    return JSON.stringify(data, null, 2);
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

  $("btnRefresh").addEventListener("click", refresh);
  refresh();
})();
