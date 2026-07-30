import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Form,
  Input,
  Message,
  Select,
  Space,
  Tag,
  Typography,
} from "@arco-design/web-react";
import { health, type ClientConfig } from "../api/gateway";
import {
  fetchOpenTradeDays,
  isOpenTradeDay,
  prevOpenDay,
} from "../lib/tradeCalendar";
import { zh } from "../i18n/zh";
import { saveSettings, type Settings } from "../state/settings";

export function SettingsPage({
  settings,
  onSave,
  cfg,
  connected,
}: {
  settings: Settings;
  onSave: (s: Settings) => void;
  cfg?: ClientConfig;
  connected?: boolean;
}) {
  const [form, setForm] = useState<Settings>(settings);
  const apiCfg = cfg ?? { apiBase: form.apiBase, token: form.token };

  useEffect(() => {
    setForm(settings);
  }, [settings]);

  const calQ = useQuery({
    queryKey: ["trade-days", apiCfg.apiBase],
    queryFn: () => fetchOpenTradeDays(apiCfg),
    enabled: Boolean(connected ?? true) && Boolean(apiCfg.apiBase),
    staleTime: 60_000,
  });
  const openDays = calQ.data ?? [];
  const openSet = useMemo(() => new Set(openDays), [openDays]);
  const asOfOpen = form.asOf ? isOpenTradeDay(openDays, form.asOf) : false;
  const prev = form.asOf ? prevOpenDay(openDays, form.asOf) : null;

  return (
    <div className="page" style={{ maxWidth: 520 }}>
      <Typography.Title heading={5} style={{ marginTop: 0 }}>
        {zh.settings}
      </Typography.Title>
      <Form layout="vertical">
        <Form.Item label="API Base" required>
          <Input
            value={form.apiBase}
            onChange={(apiBase) => setForm({ ...form, apiBase })}
            placeholder="http://127.0.0.1:8088"
          />
        </Form.Item>
        <Form.Item label={zh.tokenOpt}>
          <Input.Password
            value={form.token}
            onChange={(token) => setForm({ ...form, token })}
          />
        </Form.Item>
        <Form.Item
          label={zh.asOf}
          required
          extra="纸面流水线、信号、编排、续撮依赖业务日；建议选 A 股开市日"
        >
          <Space direction="vertical" style={{ width: "100%" }}>
            <DatePicker
              style={{ width: "100%" }}
              value={form.asOf || undefined}
              onChange={(asOf) => setForm({ ...form, asOf: asOf || "" })}
              disabledDate={(current) => {
                if (!current || openSet.size === 0) return false;
                const iso = current.format("YYYY-MM-DD");
                return !openSet.has(iso);
              }}
            />
            <Space wrap>
              {form.asOf ? (
                <Tag color={asOfOpen ? "green" : "orangered"}>
                  {calQ.isLoading
                    ? "校验交易日…"
                    : openDays.length === 0
                      ? "无交易日历数据"
                      : asOfOpen
                        ? "开市日"
                        : "非开市日"}
                </Tag>
              ) : null}
              {!asOfOpen && prev ? (
                <Button
                  size="mini"
                  type="outline"
                  onClick={() => setForm({ ...form, asOf: prev })}
                >
                  对齐上一开市日 {prev}
                </Button>
              ) : null}
            </Space>
          </Space>
        </Form.Item>
        <Form.Item label={zh.defaultAccount}>
          <Input
            value={form.accountId}
            onChange={(accountId) => setForm({ ...form, accountId })}
          />
        </Form.Item>
        <Form.Item label={zh.env}>
          <Select
            value={form.env}
            onChange={(env) => setForm({ ...form, env })}
            options={[
              { label: zh.envResearch, value: "research" },
              { label: zh.envPaper, value: "paper" },
              { label: zh.envLive, value: "live" },
            ]}
          />
        </Form.Item>
        {form.env === "live" ? (
          <Typography.Paragraph type="warning">
            {zh.liveLocked}
          </Typography.Paragraph>
        ) : null}
        <Button
          type="primary"
          onClick={async () => {
            if (!form.asOf) {
              Message.warning(zh.needAsOf);
              return;
            }
            try {
              await health({ apiBase: form.apiBase, token: form.token });
            } catch {
              Message.warning("网关暂不可达，仍已保存本地设置");
            }
            if (openDays.length && !isOpenTradeDay(openDays, form.asOf)) {
              Message.warning(
                `业务日 ${form.asOf} 非开市日，编排可能 skipped；建议对齐交易日`,
              );
            }
            saveSettings(form);
            onSave(form);
            Message.success(zh.saved);
          }}
        >
          {zh.save}
        </Button>
      </Form>
    </div>
  );
}
