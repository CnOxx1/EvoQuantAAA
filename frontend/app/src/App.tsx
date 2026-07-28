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
import { LedgerPage } from "./pages/LedgerPage";
import { OpsPage } from "./pages/OpsPage";
import { TradePage } from "./pages/TradePage";
import { ResearchPage } from "./pages/ResearchPage";
import { MarketPage } from "./pages/MarketPage";
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
          path="research"
          element={<ResearchPage cfg={cfg} connected={connected} />}
        />
        <Route
          path="market"
          element={
            <MarketPage cfg={cfg} settings={settings} connected={connected} />
          }
        />
        <Route
          path="trade"
          element={
            <TradePage cfg={cfg} settings={settings} connected={connected} />
          }
        />
        <Route
          path="ledger"
          element={
            <LedgerPage cfg={cfg} settings={settings} connected={connected} />
          }
        />
        <Route
          path="ops"
          element={<OpsPage cfg={cfg} connected={connected} />}
        />
        <Route
          path="settings"
          element={
            <SettingsPage settings={settings} onChange={setSettings} />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
