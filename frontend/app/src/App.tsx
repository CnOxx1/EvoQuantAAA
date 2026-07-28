import { useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { ConfigProvider } from "@arco-design/web-react";
import zhCN from "@arco-design/web-react/es/locale/zh-CN";
import { Shell } from "./components/Shell";
import { getKill, health, type ClientConfig } from "./api/gateway";
import { loadSettings, type Settings } from "./state/settings";
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
            />
          }
        >
          <Route path="/" element={<OverviewPage {...pageProps} />} />

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
          <Route path="/market/calendar" element={<CalendarPage {...pageProps} />} />

          <Route path="/strategies" element={<StrategiesPage {...pageProps} />} />
          <Route path="/research" element={<ResearchPage {...pageProps} />} />
          <Route path="/backtest" element={<BacktestPage {...pageProps} />} />

          <Route path="/portfolio" element={<PortfolioPage {...pageProps} />} />
          <Route path="/ledger" element={<LedgerPage {...pageProps} />} />
          <Route path="/trade" element={<TradePage {...pageProps} />} />
          <Route path="/risk" element={<RiskPage {...pageProps} />} />

          <Route path="/ops" element={<OpsPage {...pageProps} />} />
          <Route path="/data/quality" element={<DataQualityPage {...pageProps} />} />
          <Route path="/data/coverage" element={<CoveragePage {...pageProps} />} />

          <Route
            path="/settings"
            element={
              <SettingsPage
                settings={settings}
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
