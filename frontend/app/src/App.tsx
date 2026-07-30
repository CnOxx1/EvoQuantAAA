import { useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { ConfigProvider } from "@arco-design/web-react";
import zhCN from "@arco-design/web-react/es/locale/zh-CN";
import { Shell } from "./components/Shell";
import { getKill, health, type ClientConfig } from "./api/gateway";
import { loadSettings, saveSettings, type Settings } from "./state/settings";
import { OverviewPage } from "./pages/OverviewPage";
import { MarketPage } from "./pages/MarketPage";
import { StrategiesPage } from "./pages/StrategiesPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { RiskPage } from "./pages/RiskPage";
import { ResearchPage } from "./pages/ResearchPage";
import { TradePage } from "./pages/TradePage";
import { LedgerPage } from "./pages/LedgerPage";
import { OpsPage } from "./pages/OpsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { BacktestPage } from "./pages/BacktestPage";
import { BoardsPage } from "./pages/BoardsPage";
import { EventsPage } from "./pages/EventsPage";
import { CalendarPage } from "./pages/CalendarPage";
import { DataQualityPage } from "./pages/DataQualityPage";
import { CoveragePage } from "./pages/CoveragePage";
import { ModulesPage } from "./pages/ModulesPage";
import { SignalsPage } from "./pages/SignalsPage";
import { UniversePage } from "./pages/UniversePage";
import { IngestPage } from "./pages/IngestPage";
import { AdaptersPage } from "./pages/AdaptersPage";
import { FreezesPage } from "./pages/FreezesPage";
import { ProcessPage } from "./pages/ProcessPage";
import { ParamsPage } from "./pages/ParamsPage";
import { CapitalPage } from "./pages/CapitalPage";
import { FactorsPage } from "./pages/FactorsPage";
import { F10Page } from "./pages/F10Page";
import { AuditPage } from "./pages/AuditPage";
import { SchedulePage } from "./pages/SchedulePage";

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

function AppInner() {
  const [settings, setSettings] = useState<Settings>(() => loadSettings());
  const cfg: ClientConfig = useMemo(
    () => ({ apiBase: settings.apiBase, token: settings.token }),
    [settings.apiBase, settings.token],
  );

  const healthQ = useQuery({
    queryKey: ["health", cfg.apiBase],
    queryFn: () => health(cfg),
    refetchInterval: 15_000,
  });
  const killQ = useQuery({
    queryKey: ["kill", cfg.apiBase, cfg.token],
    queryFn: () => getKill(cfg),
    enabled: healthQ.isSuccess,
    refetchInterval: 10_000,
  });

  const connected = healthQ.isSuccess;
  const refresh = () => {
    void qc.invalidateQueries();
  };

  const pageProps = { cfg, settings, connected };
  const setAsOf = (day: string) => {
    const next = { ...settings, asOf: day };
    saveSettings(next);
    setSettings(next);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Shell
              settings={settings}
              kill={killQ.data}
              connected={connected}
              onRefresh={refresh}
              cfg={cfg}
              onSettingsChange={setSettings}
              onAsOfChange={setAsOf}
            />
          }
        >
          <Route
            path="/"
            element={
              <OverviewPage
                {...pageProps}
                onSettingsChange={setSettings}
              />
            }
          />

          <Route path="/market" element={<Navigate to="/market/monitor" replace />} />
          <Route
            path="/market/overview"
            element={<MarketPage {...pageProps} initialTab="ranks" />}
          />
          <Route
            path="/market/monitor"
            element={<MarketPage {...pageProps} initialTab="abnormal" />}
          />
          <Route path="/market/boards" element={<BoardsPage {...pageProps} />} />
          <Route path="/market/events" element={<EventsPage {...pageProps} />} />
          <Route
            path="/market/calendar"
            element={
              <CalendarPage {...pageProps} onSettingsChange={setSettings} />
            }
          />
          <Route path="/market/f10" element={<F10Page {...pageProps} />} />

          <Route path="/strategies" element={<StrategiesPage {...pageProps} />} />
          <Route path="/research" element={<ResearchPage {...pageProps} />} />
          <Route path="/research/factors" element={<FactorsPage {...pageProps} />} />
          <Route path="/research/freezes" element={<FreezesPage {...pageProps} />} />
          <Route path="/signals" element={<SignalsPage {...pageProps} />} />
          <Route path="/backtest" element={<BacktestPage {...pageProps} />} />

          <Route path="/portfolio" element={<PortfolioPage {...pageProps} />} />
          <Route path="/portfolio/capital" element={<CapitalPage {...pageProps} />} />
          <Route path="/ledger" element={<LedgerPage {...pageProps} />} />
          <Route path="/trade" element={<TradePage {...pageProps} />} />
          <Route path="/risk" element={<RiskPage {...pageProps} />} />

          <Route path="/ops" element={<OpsPage {...pageProps} />} />
          <Route path="/ops/schedule" element={<SchedulePage {...pageProps} />} />
          <Route path="/data/quality" element={<DataQualityPage {...pageProps} />} />
          <Route path="/data/coverage" element={<CoveragePage {...pageProps} />} />
          <Route path="/data/universe" element={<UniversePage {...pageProps} />} />
          <Route path="/data/ingest" element={<IngestPage {...pageProps} />} />
          <Route path="/data/process" element={<ProcessPage {...pageProps} />} />

          <Route path="/system/modules" element={<ModulesPage {...pageProps} />} />
          <Route path="/system/adapters" element={<AdaptersPage {...pageProps} />} />
          <Route path="/system/params" element={<ParamsPage {...pageProps} />} />
          <Route path="/system/audit" element={<AuditPage {...pageProps} />} />
          <Route
            path="/settings"
            element={
              <SettingsPage
                settings={settings}
                cfg={cfg}
                connected={connected}
                onSave={(s) => {
                  setSettings(s);
                }}
              />
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ConfigProvider locale={zhCN}>
        <AppInner />
      </ConfigProvider>
    </QueryClientProvider>
  );
}
