import { NavLink, Outlet } from "react-router-dom";
import { StatusPill } from "./StatusPill";
import type { Settings } from "../state/settings";
import { isKillOn, type KillStatus } from "../api/gateway";
import styles from "./Shell.module.css";

const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/strategies", label: "Strategies" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/risk", label: "Risk" },
  { to: "/research", label: "Research" },
  { to: "/trade", label: "Trade" },
  { to: "/ledger", label: "Ledger" },
  { to: "/ops", label: "Ops" },
  { to: "/settings", label: "Settings" },
];

export function Shell({
  settings,
  kill,
  connected,
  onRefresh,
}: {
  settings: Settings;
  kill: KillStatus | undefined;
  connected: boolean;
  onRefresh: () => void;
}) {
  const killOn = isKillOn(kill);
  return (
    <div className={styles.app}>
      <header className={styles.top}>
        <div className={styles.brandBlock}>
          <span className={styles.brand}>EvoQuantAAA</span>
          <span className={styles.env}>{settings.env}</span>
          {settings.env === "live" ? (
            <span className={styles.liveWarn}>live UI 默认锁死</span>
          ) : null}
        </div>
        <div className={styles.topMeta}>
          <span className={styles.metaItem}>
            as-of <code className="mono">{settings.asOf}</code>
          </span>
          <span className={styles.metaItem}>
            Kill{" "}
            <StatusPill tone={killOn ? "failed" : "ok"}>
              {killOn ? "ON" : "OFF"}
            </StatusPill>
          </span>
          <StatusPill tone={connected ? "ok" : "failed"}>
            {connected ? "API" : "离线"}
          </StatusPill>
          <button type="button" className={styles.refresh} onClick={onRefresh}>
            刷新
          </button>
        </div>
      </header>
      <div className={styles.body}>
        <aside className={styles.side}>
          <nav className={styles.nav}>
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? `${styles.link} ${styles.active}` : styles.link
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <p className={styles.sideNote}>
            只经 api_gateway · 不直连库 · 执行默认只读
          </p>
        </aside>
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
