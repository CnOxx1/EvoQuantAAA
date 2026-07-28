import { NavLink, Outlet } from "react-router-dom";
import { StatusPill } from "./StatusPill";
import type { Settings } from "../state/settings";
import { isKillOn, type KillStatus } from "../api/gateway";
import styles from "./Shell.module.css";

const NAV = [
  { to: "/", label: "总览", end: true },
  { to: "/strategies", label: "策略" },
  { to: "/portfolio", label: "组合" },
  { to: "/risk", label: "风控" },
  { to: "/research", label: "研究" },
  { to: "/trade", label: "交易" },
  { to: "/ledger", label: "账本" },
  { to: "/ops", label: "运维" },
  { to: "/settings", label: "设置" },
];

const ENV_ZH: Record<string, string> = {
  research: "研究",
  paper: "纸面",
  live: "实盘",
};

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
          <span className={styles.env}>
            {ENV_ZH[settings.env] || settings.env}
          </span>
          {settings.env === "live" ? (
            <span className={styles.liveWarn}>实盘界面默认锁定</span>
          ) : null}
        </div>
        <div className={styles.topMeta}>
          <span className={styles.metaItem}>
            业务日 <code className="mono">{settings.asOf}</code>
          </span>
          <span className={styles.metaItem}>
            熔断{" "}
            <StatusPill tone={killOn ? "failed" : "ok"}>
              {killOn ? "开启" : "关闭"}
            </StatusPill>
          </span>
          <StatusPill tone={connected ? "ok" : "failed"}>
            {connected ? "已连接" : "未连接"}
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
            仅经 api_gateway 取数 · 禁止直连数据库 · 本台不下单
          </p>
        </aside>
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
