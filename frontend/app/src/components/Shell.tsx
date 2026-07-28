import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AutoComplete,
  Badge,
  Button,
  Layout,
  Menu,
  Space,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  IconApps,
  IconDashboard,
  IconExperiment,
  IconFire,
  IconSafe,
  IconSearch,
  IconSettings,
  IconStorage,
  IconSwap,
  IconThunderbolt,
} from "@arco-design/web-react/icon";
import type { Settings } from "../state/settings";
import {
  isKillOn,
  searchSecurities,
  type ClientConfig,
  type KillStatus,
} from "../api/gateway";
import styles from "./Shell.module.css";

const MenuItem = Menu.Item;
const SubMenu = Menu.SubMenu;
const { Header, Sider, Content, Footer } = Layout;

type NavLeaf = { key: string; label: string };
type NavNode =
  | { key: string; label: string; icon: ReactNode; children?: undefined }
  | { key: string; label: string; icon: ReactNode; children: NavLeaf[] };

/** Aligns with terminal mockup IA; existing pages mapped under parents. */
const NAV: NavNode[] = [
  { key: "/", label: "概览", icon: <IconDashboard /> },
  {
    key: "g-market",
    label: "市场情报",
    icon: <IconFire />,
    children: [
      { key: "/market/overview", label: "行情总览" },
      { key: "/market/monitor", label: "市场监控" },
      { key: "/market/boards", label: "板块监控" },
      { key: "/market/events", label: "事件日历" },
      { key: "/market/calendar", label: "财经日历" },
    ],
  },
  {
    key: "g-strategies",
    label: "策略研究",
    icon: <IconThunderbolt />,
    children: [
      { key: "/strategies", label: "策略注册" },
      { key: "/research", label: "研究实验" },
    ],
  },
  { key: "/backtest", label: "回测中心", icon: <IconExperiment /> },
  {
    key: "g-portfolio",
    label: "组合管理",
    icon: <IconApps />,
    children: [
      { key: "/portfolio", label: "组合构建" },
      { key: "/ledger", label: "账本持仓" },
    ],
  },
  { key: "/trade", label: "交易执行", icon: <IconSwap /> },
  { key: "/risk", label: "风控监控", icon: <IconSafe /> },
  {
    key: "g-data",
    label: "数据中心",
    icon: <IconStorage />,
    children: [
      { key: "/ops", label: "运维告警" },
      { key: "/data/quality", label: "数据质量" },
      { key: "/data/coverage", label: "覆盖率" },
    ],
  },
  {
    key: "g-system",
    label: "系统管理",
    icon: <IconSettings />,
    children: [{ key: "/settings", label: "连接与环境" }],
  },
];

const TOP_LINKS: { key: string; label: string; match: (p: string) => boolean }[] = [
  { key: "/", label: "概览", match: (p) => p === "/" },
  {
    key: "/market/monitor",
    label: "市场情报",
    match: (p) => p.startsWith("/market"),
  },
  {
    key: "/strategies",
    label: "策略研究",
    match: (p) => p.startsWith("/strategies") || p.startsWith("/research"),
  },
  { key: "/backtest", label: "回测中心", match: (p) => p.startsWith("/backtest") },
  {
    key: "/portfolio",
    label: "组合管理",
    match: (p) => p.startsWith("/portfolio") || p.startsWith("/ledger"),
  },
  { key: "/trade", label: "交易执行", match: (p) => p.startsWith("/trade") },
  { key: "/risk", label: "风控监控", match: (p) => p.startsWith("/risk") },
  {
    key: "/ops",
    label: "数据中心",
    match: (p) => p.startsWith("/ops") || p.startsWith("/data"),
  },
  {
    key: "/settings",
    label: "系统管理",
    match: (p) => p.startsWith("/settings") || p.startsWith("/system"),
  },
];

const ENV_ZH: Record<string, string> = {
  research: "研究",
  paper: "纸面",
  live: "实盘",
};

function collectLeaves(nodes: NavNode[]): string[] {
  const out: string[] = [];
  for (const n of nodes) {
    if (n.children) {
      for (const c of n.children) out.push(c.key);
    } else {
      out.push(n.key);
    }
  }
  return out;
}

function resolveSelected(pathname: string): string {
  const leaves = collectLeaves(NAV).sort((a, b) => b.length - a.length);
  for (const key of leaves) {
    if (key === "/") {
      if (pathname === "/") return "/";
      continue;
    }
    if (pathname === key || pathname.startsWith(`${key}/`)) return key;
  }
  return "/";
}

function openKeysForPath(pathname: string): string[] {
  const open: string[] = [];
  for (const n of NAV) {
    if (!n.children) continue;
    const hit = n.children.some(
      (c) => pathname === c.key || pathname.startsWith(`${c.key}/`),
    );
    if (hit) open.push(n.key);
  }
  return open;
}

function nowCnLabel(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `CN ${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function Shell({
  settings,
  kill,
  connected,
  onRefresh,
  cfg,
}: {
  settings: Settings;
  kill: KillStatus | undefined;
  connected: boolean;
  onRefresh: () => void;
  cfg: ClientConfig;
}) {
  const loc = useLocation();
  const nav = useNavigate();
  const selected = resolveSelected(loc.pathname);
  const [openKeys, setOpenKeys] = useState(() =>
    Array.from(new Set(["g-market", ...openKeysForPath(loc.pathname)])),
  );
  const [clock, setClock] = useState(nowCnLabel);
  const [searchQ, setSearchQ] = useState("");
  const killOn = isKillOn(kill);
  const topActive = TOP_LINKS.find((t) => t.match(loc.pathname))?.key;

  const searchRes = useQuery({
    queryKey: ["sec-search", cfg.apiBase, searchQ, settings.asOf],
    queryFn: () =>
      searchSecurities(cfg, { q: searchQ, asOf: settings.asOf, limit: 12 }),
    enabled: connected && searchQ.trim().length >= 1,
  });

  useEffect(() => {
    setOpenKeys((prev) => {
      const next = openKeysForPath(loc.pathname);
      const merged = Array.from(new Set([...prev, ...next]));
      return merged;
    });
  }, [loc.pathname]);

  useEffect(() => {
    const id = window.setInterval(() => setClock(nowCnLabel()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const goSymbol = (sym: string) => {
    const code = sym.trim();
    if (!code) return;
    setSearchQ("");
    nav(`/market/monitor?symbol=${encodeURIComponent(code)}`);
  };

  const searchOptions = (searchRes.data?.items ?? []).map((it) => ({
    value: String(it.symbol ?? ""),
    name: `${it.symbol} ${it.name ?? ""}`.trim(),
  }));

  return (
    <Layout className={styles.root}>
      <Header className={styles.header}>
        <div className={styles.headerLeft}>
          <Typography.Text className={styles.brand}>EvoQuantAAA</Typography.Text>
          <nav className={styles.topNav}>
            {TOP_LINKS.map((t) => (
              <button
                key={t.key}
                type="button"
                className={topActive === t.key ? styles.topNavActive : styles.topNavItem}
                onClick={() => nav(t.key)}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
        <Space size={10} className={styles.headerRight}>
          <div className={styles.searchWrap}>
            <IconSearch className={styles.searchIcon} />
            <AutoComplete
              allowClear
              placeholder="代码/名称/关键字"
              className={styles.search}
              data={searchOptions}
              value={searchQ}
              onSearch={setSearchQ}
              onChange={setSearchQ}
              onSelect={(v) => goSymbol(String(v))}
              onPressEnter={() => {
                const first = searchOptions[0]?.value || searchQ.trim();
                if (first) goSymbol(first);
              }}
            />
          </div>
          <Tag size="small" color="arcoblue">
            {ENV_ZH[settings.env] || settings.env}
          </Tag>
          {settings.env === "live" ? (
            <Tag size="small" color="red">
              实盘界面默认锁定
            </Tag>
          ) : null}
          <Typography.Text type="secondary" className={styles.meta}>
            业务日 <code>{settings.asOf}</code>
          </Typography.Text>
          <Badge
            status={killOn ? "error" : "success"}
            text={killOn ? "熔断开启" : "熔断关闭"}
          />
          <Button size="mini" onClick={onRefresh}>
            刷新
          </Button>
        </Space>
      </Header>
      <Layout className={styles.body}>
        <Sider width={188} className={styles.sider}>
          <Menu
            selectedKeys={[selected]}
            openKeys={openKeys}
            onClickSubMenu={(_, keys) => setOpenKeys(keys)}
            onClickMenuItem={(key) => nav(key)}
            style={{ width: "100%", border: "none" }}
          >
            {NAV.map((item) =>
              item.children ? (
                <SubMenu
                  key={item.key}
                  title={
                    <span>
                      {item.icon}
                      {item.label}
                    </span>
                  }
                >
                  {item.children.map((c) => (
                    <MenuItem key={c.key}>{c.label}</MenuItem>
                  ))}
                </SubMenu>
              ) : (
                <MenuItem key={item.key}>
                  {item.icon}
                  {item.label}
                </MenuItem>
              ),
            )}
          </Menu>
          <div className={styles.note}>仅经 api_gateway · 禁止直连库</div>
        </Sider>
        <Content className={styles.content}>
          <Outlet />
        </Content>
      </Layout>
      <Footer className={styles.footer}>
        <Typography.Text type="secondary" className={styles.meta}>
          EvoQuantAAA · A股终端
        </Typography.Text>
        <Space size={12}>
          <Typography.Text type="secondary" className={styles.meta}>
            {clock}
          </Typography.Text>
          <Badge
            status={connected ? "success" : "error"}
            text={connected ? "已连接" : "未连接"}
          />
        </Space>
      </Footer>
    </Layout>
  );
}
