import { Outlet, useLocation, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import {
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
  IconBook,
  IconDashboard,
  IconExperiment,
  IconFire,
  IconSafe,
  IconSettings,
  IconStorage,
  IconSwap,
  IconThunderbolt,
} from "@arco-design/web-react/icon";
import type { Settings } from "../state/settings";
import { isKillOn, type KillStatus } from "../api/gateway";
import styles from "./Shell.module.css";

const MenuItem = Menu.Item;
const { Header, Sider, Content } = Layout;

const NAV: { key: string; label: string; icon: ReactNode }[] = [
  { key: "/", label: "总览", icon: <IconDashboard /> },
  { key: "/market", label: "市场情报", icon: <IconFire /> },
  { key: "/strategies", label: "策略", icon: <IconThunderbolt /> },
  { key: "/portfolio", label: "组合", icon: <IconApps /> },
  { key: "/risk", label: "风控", icon: <IconSafe /> },
  { key: "/research", label: "研究", icon: <IconExperiment /> },
  { key: "/trade", label: "交易", icon: <IconSwap /> },
  { key: "/ledger", label: "账本", icon: <IconBook /> },
  { key: "/ops", label: "运维", icon: <IconStorage /> },
  { key: "/settings", label: "设置", icon: <IconSettings /> },
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
  const loc = useLocation();
  const nav = useNavigate();
  const selected =
    NAV.find((n) =>
      n.key === "/" ? loc.pathname === "/" : loc.pathname.startsWith(n.key),
    )?.key || "/";
  const killOn = isKillOn(kill);

  return (
    <Layout className={styles.root}>
      <Header className={styles.header}>
        <Space size={12}>
          <Typography.Text className={styles.brand}>EvoQuantAAA</Typography.Text>
          <Tag size="small" color="arcoblue">
            {ENV_ZH[settings.env] || settings.env}
          </Tag>
          {settings.env === "live" ? (
            <Tag size="small" color="red">
              实盘界面默认锁定
            </Tag>
          ) : null}
        </Space>
        <Space size={12}>
          <Typography.Text type="secondary" className={styles.meta}>
            业务日 <code>{settings.asOf}</code>
          </Typography.Text>
          <Badge
            status={killOn ? "error" : "success"}
            text={killOn ? "熔断开启" : "熔断关闭"}
          />
          <Badge
            status={connected ? "success" : "error"}
            text={connected ? "已连接" : "未连接"}
          />
          <Button size="mini" onClick={onRefresh}>
            刷新
          </Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={168} className={styles.sider}>
          <Menu
            selectedKeys={[selected]}
            onClickMenuItem={(key) => nav(key)}
            style={{ width: "100%", border: "none" }}
          >
            {NAV.map((item) => (
              <MenuItem key={item.key}>
                {item.icon}
                {item.label}
              </MenuItem>
            ))}
          </Menu>
          <div className={styles.note}>仅经 api_gateway · 禁止直连库</div>
        </Sider>
        <Content className={styles.content}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
