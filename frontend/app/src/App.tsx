import { useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getHealth, getKill } from "./api/gateway";
import { Shell } from "./components/Shell";
import { OverviewPage } from "./pages/OverviewPage";
import { StrategiesPage } from "./pages/StrategiesPage";
import { RiskPage } from "./pages/RiskPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { SettingsPage } from "./pages/SettingsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { loadSettings, type Settings } from "./state/settings";

export default function App() {
  const [settings, setSettings] = useState<Settings>(() => loadSettings());
  const qc = useQueryClient();
  const cfg = useMemo(
    () => ({ apiBase: settings.apiBase, apiToken: settings.apiToken }),
    [settings.apiBase, settings.apiToken],
  );

  const healthQ = useQuery({
    queryKey: ["health", cfg.apiBase, cfg.apiToken],
    queryFn: () => getHealth(cfg),
    retry: 1,
    refetchInterval: 30_000,
  });
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase],
    queryFn: () => getKill(cfg),
    enabled: Boolean(healthQ.data?.ok),
    refetchInterval: 15_000,
  });

  const connected = Boolean(healthQ.data?.ok);

  return (
    <Routes>
      <Route
        element={
          <Shell
            settings={settings}
            kill={killQ.data}
            connected={connected}
            onRefresh={() => {
              void qc.invalidateQueries();
            }}
          />
        }
      >
        <Route
          index
          element={
            <OverviewPage
              cfg={cfg}
              settings={settings}
              connected={connected}
            />
          }
        />
        <Route
          path="strategies"
          element={<StrategiesPage cfg={cfg} connected={connected} />}
        />
        <Route
          path="portfolio"
          element={
            <PortfolioPage
              cfg={cfg}
              settings={settings}
              connected={connected}
            />
          }
        />
        <Route
          path="risk"
          element={<RiskPage cfg={cfg} connected={connected} />}
        />
        <Route
          path="settings"
          element={
            <SettingsPage settings={settings} onChange={setSettings} />
          }
        />
        <Route
          path="research"
          element={
            <PlaceholderPage
              title="Research"
              phase="F2"
              blurb="证据包 / freeze 只读浏览；待 research runs API。"
            />
          }
        />
        <Route
          path="trade"
          element={
            <PlaceholderPage
              title="Trade"
              phase="F2"
              blurb="execution / fills / pending 只读；默认不下单。"
            />
          }
        />
        <Route
          path="ledger"
          element={
            <PlaceholderPage
              title="Ledger"
              phase="F2"
              blurb="账户现金 / sleeve / 可卖深化视图。"
            />
          }
        />
        <Route
          path="ops"
          element={
            <PlaceholderPage
              title="Ops"
              phase="F2"
              blurb="告警确认 / coverage / schedule 状态。"
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
