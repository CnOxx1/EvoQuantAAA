import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AutoComplete,
  Badge,
  Button,
  DatePicker,
  Drawer,
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
  IconMenuFold,
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
import {
  fetchOpenTradeDays,
  isOpenTradeDay,
} from "../lib/tradeCalendar";
import { zh } from "../i18n/zh";
import styles from "./Shell.module.css";

const MenuItem = Menu.Item;
const SubMenu = Menu.SubMenu;
const { Header, Sider, Content, Footer } = Layout;

type NavLeaf = { key: string; label: string };
type NavNode =
  | { key: string; label: string; icon: ReactNode; children?: undefined }
  | { key: string; label: string; icon: ReactNode; children: NavLeaf[] };

/** Sider depth nav; top bar is section hubs only. */
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
      { key: "/market/f10", label: "F10 资料" },
    ],
  },
  {
    key: "g-strategies",
    label: "策略研究",
    icon: <IconThunderbolt />,
    children: [
      { key: "/strategies", label: "策略注册" },
      { key: "/research", label: "研究实验" },
      { key: "/research/factors", label: "因子值" },
      { key: "/research/freezes", label: "证据冻结" },
      { key: "/signals", label: "生产信号" },
    ],
  },
  { key: "/backtest", label: "回测中心", icon: <IconExperiment /> },
  {
    key: "g-portfolio",
    label: "组合管理",
    icon: <IconApps />,
    children: [
      { key: "/portfolio", label: "组合构建" },
      { key: "/portfolio/capital", label: "资本配额" },
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
      { key: "/ops/schedule", label: "日更编排" },
      { key: "/data/quality", label: "数据质量" },
      { key: "/data/coverage", label: "覆盖率" },
      { key: "/data/universe", label: "Universe" },
      { key: "/data/ingest", label: "取数批次" },
      { key: "/data/process", label: "加工批次" },
    ],
  },
  {
    key: "g-system",
    label: "系统管理",
    icon: <IconSettings />,
    children: [
      { key: "/system/modules", label: "模块地图" },
      { key: "/system/params", label: "参考参数" },
      { key: "/system/adapters", label: "执行适配器" },
      { key: "/system/audit", label: "API 审计" },
      { key: "/settings", label: "连接与环境" },
    ],
  },
];

const TOP_LINKS: { key: string; label: string; match: (p: string) => boolean }[] = [
  { key: "/", label: "概览", match: (p) => p === "/" },
  {
    key: "/market/monitor",
    label: "市场",
    match: (p) => p.startsWith("/market"),
  },
  {
    key: "/strategies",
    label: "策略",
    match: (p) =>
      p.startsWith("/strategies") ||
      p.startsWith("/research") ||
      p.startsWith("/signals"),
  },
  { key: "/backtest", label: "回测", match: (p) => p.startsWith("/backtest") },
  {
    key: "/portfolio",
    label: "组合",
    match: (p) => p.startsWith("/portfolio") || p.startsWith("/ledger"),
  },
  { key: "/trade", label: "交易", match: (p) => p.startsWith("/trade") },
  { key: "/risk", label: "风控", match: (p) => p.startsWith("/risk") },
  {
    key: "/ops",
    label: "数据",
    match: (p) => p.startsWith("/ops") || p.startsWith("/data"),
  },
  {
    key: "/system/modules",
    label: "系统",
    match: (p) => p.startsWith("/settings") || p.startsWith("/system"),
  },
];

const ENV_ZH: Record<string, string> = {
  research: zh.envResearch,
  paper: zh.envPaper,
  live: zh.envLive,
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

function NavMenu({
  selected,
  openKeys,
  setOpenKeys,
  onNavigate,
}: {
  selected: string;
  openKeys: string[];
  setOpenKeys: (keys: string[]) => void;
  onNavigate: (key: string) => void;
}) {
  return (
    <Menu
      selectedKeys={[selected]}
      openKeys={openKeys}
      onClickSubMenu={(_, keys) => setOpenKeys(keys)}
      onClickMenuItem={(key) => onNavigate(key)}
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
  );
}

export function Shell({
  settings,
  kill,
  connected,
  onRefresh,
  cfg,
  onAsOfChange,
}: {
  settings: Settings;
  kill: KillStatus | undefined;
  connected: boolean;
  onRefresh: () => void;
  cfg: ClientConfig;
  onSettingsChange?: (s: Settings) => void;
  onAsOfChange?: (day: string) => void;
}) {
  const loc = useLocation();
  const nav = useNavigate();
  const selected = resolveSelected(loc.pathname);
  const [openKeys, setOpenKeys] = useState(() => openKeysForPath(loc.pathname));
  const [clock, setClock] = useState(nowCnLabel);
  const [searchQ, setSearchQ] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const killOn = isKillOn(kill);
  const topActive = TOP_LINKS.find((t) => t.match(loc.pathname))?.key;
  const liveLocked = settings.env === "live";

  const searchRes = useQuery({
    queryKey: ["sec-search", cfg.apiBase, searchQ, settings.asOf],
    queryFn: () =>
      searchSecurities(cfg, { q: searchQ, asOf: settings.asOf, limit: 12 }),
    enabled: connected && searchQ.trim().length >= 1,
  });

  const calQ = useQuery({
    queryKey: ["trade-days", cfg.apiBase],
    queryFn: () => fetchOpenTradeDays(cfg),
    enabled: connected,
    staleTime: 60_000,
  });
  const openDays = calQ.data ?? [];
  const asOfOpen = settings.asOf
    ? isOpenTradeDay(openDays, settings.asOf)
    : false;

  useEffect(() => {
    setOpenKeys(openKeysForPath(loc.pathname));
    setMobileNav(false);
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

  const goMenu = (key: string) => {
    nav(key);
    setMobileNav(false);
  };

  return (
    <Layout className={styles.root}>
      <Header className={styles.header}>
        <div className={styles.headerLeft}>
          <Button
            className={styles.menuBtn}
            size="mini"
            type="text"
            icon={<IconMenuFold />}
            onClick={() => setMobileNav(true)}
            aria-label="打开导航"
          />
          <Typography.Text className={styles.brand}>EvoQuantAAA</Typography.Text>
          <nav className={styles.topNav} aria-label="分区">
            {TOP_LINKS.map((t) => (
              <button
                key={t.key}
                type="button"
                className={
                  topActive === t.key ? styles.topNavActive : styles.topNavItem
                }
                onClick={() => nav(t.key)}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
        <Space size={8} className={styles.headerRight}>
          <div className={styles.searchWrap}>
            <IconSearch className={styles.searchIcon} />
            <AutoComplete
              allowClear
              placeholder="代码/名称"
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
          <div className={styles.statusCluster}>
            <Tag size="small" color="arcoblue">
              {ENV_ZH[settings.env] || settings.env}
            </Tag>
            {liveLocked ? (
              <Tag size="small" color="red" title={zh.liveLocked}>
                锁定
              </Tag>
            ) : null}
            <Space size={4} className={styles.meta} align="center">
              <span className={styles.asOfLabel}>业务日</span>
              <DatePicker
                size="mini"
                style={{ width: 128 }}
                value={settings.asOf || undefined}
                onChange={(v) => {
                  if (v && onAsOfChange) onAsOfChange(String(v));
                }}
                disabledDate={(current) => {
                  if (!current || openDays.length === 0) return false;
                  return !openDays.includes(current.format("YYYY-MM-DD"));
                }}
              />
              {settings.asOf && openDays.length ? (
                <Tag
                  size="small"
                  color={asOfOpen ? "green" : "orangered"}
                  title={asOfOpen ? "开市日" : "非开市日"}
                >
                  {asOfOpen ? "开" : "休"}
                </Tag>
              ) : null}
            </Space>
            <span
              className={styles.killBadge}
              style={{ cursor: "pointer" }}
              title="打开风控 / Kill"
              onClick={() => nav("/risk")}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") nav("/risk");
              }}
              role="link"
              tabIndex={0}
            >
              <Badge
                status={killOn ? "error" : "success"}
                text={killOn ? "熔断" : "正常"}
              />
            </span>
          </div>
          <Button size="mini" onClick={onRefresh}>
            刷新
          </Button>
        </Space>
      </Header>
      <Layout className={styles.body}>
        <Sider width={188} className={styles.sider} breakpoint="lg" collapsible={false}>
          <NavMenu
            selected={selected}
            openKeys={openKeys}
            setOpenKeys={setOpenKeys}
            onNavigate={goMenu}
          />
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

      <Drawer
        width={260}
        title="导航"
        visible={mobileNav}
        onCancel={() => setMobileNav(false)}
        footer={null}
        className={styles.mobileDrawer}
      >
        <NavMenu
          selected={selected}
          openKeys={openKeys}
          setOpenKeys={setOpenKeys}
          onNavigate={goMenu}
        />
      </Drawer>
    </Layout>
  );
}
