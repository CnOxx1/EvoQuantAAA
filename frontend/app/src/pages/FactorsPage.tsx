import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  listFactorCatalog,
  listFactorDefs,
  listFactorValues,
  getMarketIndicatorsMeta,
  registerFactorDef,
  runResearchFactor,
  updateFactorDef,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { CategoryBars } from "../components/CategoryBars";
import { histogramBins } from "../lib/chartTime";
import { n, s } from "../lib/format";
import { zh } from "../i18n/zh";
import type { Settings } from "../state/settings";

const TEMPLATES = [
  { value: "TECH_PASS", label: "技术指标透传（目录任选）" },
  { value: "MOM", label: "MOM 动量 (lookback)" },
  { value: "VAL_PE_PCT", label: "VAL_PE_PCT PE分位" },
  { value: "FLOW_NET", label: "FLOW_NET 资金流 (lookback)" },
  { value: "TECH_RSI", label: "TECH_RSI 快捷 (period)" },
  { value: "TECH_MACD_HIST", label: "TECH_MACD_HIST 快捷" },
  { value: "TECH_MA_BIAS", label: "TECH_MA_BIAS 快捷 (period)" },
];

function daysAgo(nDays: number, end?: string): string {
  const base = end ? new Date(`${end}T00:00:00`) : new Date();
  base.setDate(base.getDate() - nDays);
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}`;
}

function defaultCode(
  template: string,
  lookback: number,
  period: number,
  indicatorCode: string,
): string {
  if (template === "TECH_PASS") {
    const ind = indicatorCode.trim().toUpperCase() || "RSI_14";
    return ind.startsWith("TECH_") ? ind : `TECH_${ind}`;
  }
  if (template === "MOM") return `MOM_${lookback}`;
  if (template === "FLOW_NET") return `FLOW_NET_${lookback}`;
  if (template === "TECH_RSI") return `TECH_RSI_${period}`;
  if (template === "TECH_MA_BIAS") return `TECH_MA${period}_BIAS`;
  if (template === "VAL_PE_PCT") return "VAL_PE_PCT";
  if (template === "TECH_MACD_HIST") return "TECH_MACD_HIST";
  return "FACTOR_NEW";
}

function paramsFor(
  template: string,
  lookback: number,
  period: number,
  indicatorCode: string,
): Record<string, string | number> {
  if (template === "TECH_PASS") {
    return { indicator_code: indicatorCode.trim().toUpperCase() || "RSI_14" };
  }
  if (template === "MOM" || template === "FLOW_NET") return { lookback };
  if (template === "TECH_RSI" || template === "TECH_MA_BIAS") return { period };
  return {};
}

export function FactorsPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const qc = useQueryClient();
  const liveLocked = settings.env === "live";
  const [factor, setFactor] = useState<string | undefined>();
  const [universe, setUniverse] = useState<string | undefined>("TOP100");
  const [asOf, setAsOf] = useState(settings.asOf);
  const [regOpen, setRegOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [runOpen, setRunOpen] = useState(false);
  const [editRow, setEditRow] = useState<JsonMap | null>(null);

  const [template, setTemplate] = useState("TECH_PASS");
  const [lookback, setLookback] = useState(30);
  const [period, setPeriod] = useState(14);
  const [indicatorCode, setIndicatorCode] = useState("RSI_14");
  const [indSearch, setIndSearch] = useState("");
  const [code, setCode] = useState("TECH_RSI_14");
  const [displayName, setDisplayName] = useState("");
  const [desc, setDesc] = useState("");
  const [runRange, setRunRange] = useState<string[]>([
    daysAgo(30, settings.asOf),
    settings.asOf || daysAgo(0),
  ]);
  const [runUniverse, setRunUniverse] = useState("TOP100");

  useEffect(() => {
    setAsOf(settings.asOf);
  }, [settings.asOf]);

  useEffect(() => {
    setCode(defaultCode(template, lookback, period, indicatorCode));
  }, [template, lookback, period, indicatorCode]);

  const defsQ = useQuery({
    queryKey: ["factor-defs", cfg.apiBase],
    queryFn: () => listFactorDefs(cfg, ""),
    enabled: connected,
  });
  const catQ = useQuery({
    queryKey: ["factor-catalog", cfg.apiBase],
    queryFn: () => listFactorCatalog(cfg),
    enabled: connected,
  });
  const indMetaQ = useQuery({
    queryKey: ["ind-meta", cfg.apiBase],
    queryFn: () => getMarketIndicatorsMeta(cfg),
    enabled: connected && (regOpen || editOpen),
    staleTime: 60_000,
  });

  const indOptions = useMemo(() => {
    const q = indSearch.trim().toUpperCase();
    const rows = indMetaQ.data?.codes ?? [];
    return rows
      .filter((r) => {
        if (!q) return true;
        return (
          r.code.toUpperCase().includes(q) ||
          r.category_zh.includes(indSearch) ||
          r.category.toUpperCase().includes(q)
        );
      })
      .slice(0, 200)
      .map((r) => ({
        value: r.code,
        label: `${r.code} · ${r.category_zh}`,
      }));
  }, [indMetaQ.data, indSearch]);

  const factorOpts = useMemo(() => {
    const codes = new Set<string>();
    for (const r of defsQ.data ?? []) {
      if (String(r.status || "ACTIVE").toUpperCase() !== "ACTIVE") continue;
      const c = String(r.factor_code ?? "");
      if (c) codes.add(c);
    }
    for (const r of catQ.data ?? []) {
      const c = String(r.factor_code ?? "");
      if (c) codes.add(c);
    }
    return Array.from(codes)
      .sort()
      .map((c) => ({ label: c, value: c }));
  }, [defsQ.data, catQ.data]);

  const univOpts = useMemo(() => {
    const codes = new Set<string>(["TOP100", "HS300", "ZZ500"]);
    for (const r of catQ.data ?? []) {
      if (factor && String(r.factor_code) !== factor) continue;
      const c = String(r.universe_code ?? "");
      if (c) codes.add(c);
    }
    return Array.from(codes)
      .sort()
      .map((c) => ({ label: c, value: c }));
  }, [catQ.data, factor]);

  const valQ = useQuery({
    queryKey: ["factor-values", cfg.apiBase, factor, universe, asOf],
    queryFn: () =>
      listFactorValues(cfg, {
        factorCode: factor!,
        universeCode: universe,
        asOf: asOf || undefined,
        limit: 200,
      }),
    enabled: connected && Boolean(factor),
  });

  const histBars = useMemo(() => {
    const vals = (valQ.data?.items ?? [])
      .map((r) => Number(r.value))
      .filter((v) => Number.isFinite(v));
    return histogramBins(vals, 16).map((b, i) => ({
      id: `b${i}`,
      label: b.label,
      value: b.value,
      color: "#165dff",
    }));
  }, [valQ.data]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["factor-defs"] });
    void qc.invalidateQueries({ queryKey: ["factor-catalog"] });
    void qc.invalidateQueries({ queryKey: ["factor-values"] });
  };

  const regMut = useMutation({
    mutationFn: () =>
      registerFactorDef(cfg, {
        factor_code: code.trim(),
        template,
        params: paramsFor(template, lookback, period, indicatorCode),
        display_name: displayName.trim() || code.trim(),
        description: desc.trim() || undefined,
        status: "ACTIVE",
      }),
    onSuccess: (row) => {
      Message.success(`已注册 ${s(row.factor_code)}`);
      setRegOpen(false);
      setFactor(s(row.factor_code, ""));
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const editMut = useMutation({
    mutationFn: () => {
      if (!editRow) throw new Error("无选中因子");
      const tmpl = String(editRow.template || "");
      return updateFactorDef(cfg, String(editRow.factor_code), {
        display_name: displayName.trim() || undefined,
        description: desc,
        params: paramsFor(tmpl, lookback, period, indicatorCode),
        status: String(editRow.status || "ACTIVE"),
      });
    },
    onSuccess: (row) => {
      Message.success(`已更新 ${s(row.factor_code)}`);
      setEditOpen(false);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const retireMut = useMutation({
    mutationFn: (row: JsonMap) =>
      updateFactorDef(cfg, String(row.factor_code), { status: "RETIRED" }),
    onSuccess: (row) => {
      Message.success(`已停用 ${s(row.factor_code)}`);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const runMut = useMutation({
    mutationFn: () =>
      runResearchFactor(cfg, {
        factor_code: factor,
        start: runRange[0],
        end: runRange[1],
        universe_code: runUniverse,
        factor_type: "qfq",
        require_dq: true,
      }),
    onSuccess: (row) => {
      Message.success(
        `计算完成 · ${s(row.factor_code)} · rows=${s(row.row_count)}`,
      );
      setRunOpen(false);
      invalidate();
    },
    onError: (e: Error) => Message.error(e.message),
  });

  const openEdit = (row: JsonMap) => {
    setEditRow(row);
    setDisplayName(s(row.display_name, ""));
    setDesc(s(row.description, ""));
    const p = (row.params as Record<string, unknown>) || {};
    setLookback(Number(p.lookback) || 20);
    setPeriod(Number(p.period) || 14);
    setIndicatorCode(String(p.indicator_code || "RSI_14"));
    setEditOpen(true);
  };

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">未连接网关</Typography.Text>
      </div>
    );
  }

  return (
    <div className="page">
      <Space style={{ marginBottom: 8 }} wrap>
        <Typography.Title heading={5} style={{ margin: 0 }}>
          因子管理
        </Typography.Title>
        <Button
          type="primary"
          size="small"
          disabled={liveLocked}
          title={liveLocked ? zh.liveLocked : undefined}
          onClick={() => setRegOpen(true)}
        >
          注册因子
        </Button>
        <Button
          size="small"
          disabled={liveLocked || !factor}
          title={
            liveLocked ? zh.liveLocked : !factor ? "先选择因子" : undefined
          }
          onClick={() => setRunOpen(true)}
        >
          计算/重算
        </Button>
        <Link to="/strategies" style={{ fontSize: 12 }}>
          去策略注册选用 →
        </Link>
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginTop: 0 }}>
        基于模板注册并计算；优先用「技术指标透传」从已落库指标目录（约 200+）选码，如 RSI_14 / MACD_HIST / BOLL_*。非任意公式 DSL。
      </Typography.Paragraph>

      <Typography.Text bold>因子定义</Typography.Text>
      <Table
        style={{ marginTop: 8, marginBottom: 16 }}
        rowKey={(r) => s(r.factor_code)}
        size="small"
        loading={defsQ.isLoading}
        data={defsQ.data ?? []}
        pagination={{ pageSize: 10, size: "mini" }}
        onRow={(r) => ({
          onClick: () => setFactor(s(r.factor_code, "")),
        })}
        columns={[
          {
            title: "代码",
            render: (_, r) => <code>{s(r.factor_code)}</code>,
          },
          { title: "名称", render: (_, r) => s(r.display_name) },
          { title: "模板", render: (_, r) => s(r.template) },
          {
            title: "参数",
            render: (_, r) => (
              <code style={{ fontSize: 12 }}>
                {JSON.stringify(r.params ?? {})}
              </code>
            ),
          },
          {
            title: "状态",
            width: 90,
            render: (_, r) => (
              <Tag color={String(r.status) === "ACTIVE" ? "green" : "gray"}>
                {s(r.status)}
                {Number(r.is_builtin) === 1 ? " ·内置" : ""}
              </Tag>
            ),
          },
          {
            title: "操作",
            width: 160,
            render: (_, r) => (
              <Space>
                <Button
                  size="mini"
                  disabled={liveLocked}
                  onClick={(e) => {
                    e.stopPropagation();
                    openEdit(r);
                  }}
                >
                  修改
                </Button>
                {Number(r.is_builtin) !== 1 &&
                String(r.status) === "ACTIVE" ? (
                  <Button
                    size="mini"
                    status="warning"
                    disabled={liveLocked}
                    onClick={(e) => {
                      e.stopPropagation();
                      retireMut.mutate(r);
                    }}
                  >
                    停用
                  </Button>
                ) : null}
              </Space>
            ),
          },
        ]}
      />

      <Typography.Text bold>已落库目录（按 universe）</Typography.Text>
      <Table
        style={{ marginTop: 8, marginBottom: 16 }}
        rowKey={(r) => `${s(r.factor_code)}-${s(r.universe_code)}`}
        size="small"
        loading={catQ.isLoading}
        data={catQ.data ?? []}
        pagination={{ pageSize: 8, size: "mini" }}
        onRow={(r) => ({
          onClick: () => {
            setFactor(s(r.factor_code, ""));
            setUniverse(s(r.universe_code, "") || undefined);
          },
        })}
        columns={[
          {
            title: "因子",
            dataIndex: "factor_code",
            render: (v) => <code>{s(v)}</code>,
          },
          { title: "universe", dataIndex: "universe_code", render: (v) => s(v) },
          {
            title: "行数",
            dataIndex: "row_count",
            width: 90,
            render: (v) => n(v, 0),
          },
          {
            title: "区间",
            render: (_, r) => `${s(r.min_date)} → ${s(r.max_date)}`,
          },
        ]}
      />

      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Text bold>截面</Typography.Text>
        <Select
          size="small"
          allowClear
          placeholder="factor_code"
          style={{ width: 160 }}
          value={factor}
          onChange={(v) => setFactor(v)}
          options={factorOpts}
        />
        <Select
          size="small"
          allowClear
          placeholder="universe"
          style={{ width: 140 }}
          value={universe}
          onChange={setUniverse}
          options={univOpts}
        />
        <Input
          size="small"
          style={{ width: 130 }}
          value={asOf}
          onChange={setAsOf}
          placeholder="as_of"
        />
      </Space>
      <Table
        rowKey={(r) => `${s(r.symbol)}-${s(r.trade_date)}`}
        size="small"
        loading={valQ.isLoading}
        data={valQ.data?.items ?? []}
        pagination={{ pageSize: 20, size: "mini", showTotal: true }}
        columns={[
          {
            title: "日期",
            dataIndex: "trade_date",
            width: 110,
            render: (v) => s(v),
          },
          { title: "标的", dataIndex: "symbol", width: 100, render: (v) => s(v) },
          { title: "值", dataIndex: "value", render: (v) => n(v, 6) },
          { title: "universe", dataIndex: "universe_code", render: (v) => s(v) },
        ]}
        noDataElement={factor ? "无截面 · 可点「计算/重算」" : "先选择因子"}
      />
      {factor ? (
        <div style={{ marginTop: 16 }}>
          <CategoryBars
            title="截面分布"
            subtitle={`${factor}${universe ? ` · ${universe}` : ""}`}
            items={histBars}
            height={200}
            emptyHint="无有效因子值"
          />
        </div>
      ) : null}

      <Modal
        title="注册因子"
        visible={regOpen}
        onCancel={() => setRegOpen(false)}
        onOk={() => regMut.mutate()}
        confirmLoading={regMut.isPending}
        okButtonProps={{ disabled: liveLocked || !code.trim() }}
      >
        <Form layout="vertical" size="small">
          <Form.Item label="模板" required>
            <Select
              value={template}
              onChange={setTemplate}
              options={TEMPLATES}
            />
          </Form.Item>
          {template === "TECH_PASS" ? (
            <Form.Item
              label="技术指标"
              required
              extra={`目录约 ${indMetaQ.data?.total ?? "…"} 个；可搜索如 RSI / MACD / BOLL`}
            >
              <Select
                showSearch
                allowCreate
                placeholder="选择或输入指标码"
                loading={indMetaQ.isLoading}
                value={indicatorCode}
                onChange={(v) => setIndicatorCode(String(v || "").toUpperCase())}
                onSearch={setIndSearch}
                options={indOptions}
                filterOption={false}
              />
            </Form.Item>
          ) : null}
          {template === "MOM" || template === "FLOW_NET" ? (
            <Form.Item label="lookback">
              <InputNumber
                min={2}
                max={250}
                value={lookback}
                onChange={(v) => setLookback(Number(v) || 20)}
              />
            </Form.Item>
          ) : null}
          {template === "TECH_RSI" || template === "TECH_MA_BIAS" ? (
            <Form.Item label="period">
              <InputNumber
                min={2}
                max={250}
                value={period}
                onChange={(v) => setPeriod(Number(v) || 14)}
              />
            </Form.Item>
          ) : null}
          <Form.Item label="factor_code" required>
            <Input value={code} onChange={setCode} />
          </Form.Item>
          <Form.Item label="显示名">
            <Input value={displayName} onChange={setDisplayName} />
          </Form.Item>
          <Form.Item label="说明">
            <Input.TextArea value={desc} onChange={setDesc} autoSize />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`修改 ${s(editRow?.factor_code)}`}
        visible={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={() => editMut.mutate()}
        confirmLoading={editMut.isPending}
      >
        <Form layout="vertical" size="small">
          <Form.Item label="显示名">
            <Input value={displayName} onChange={setDisplayName} />
          </Form.Item>
          {String(editRow?.template) === "TECH_PASS" ? (
            <Form.Item label="技术指标">
              <Select
                showSearch
                allowCreate
                loading={indMetaQ.isLoading}
                value={indicatorCode}
                onChange={(v) => setIndicatorCode(String(v || "").toUpperCase())}
                onSearch={setIndSearch}
                options={indOptions}
                filterOption={false}
              />
            </Form.Item>
          ) : null}
          {String(editRow?.template) === "MOM" ||
          String(editRow?.template) === "FLOW_NET" ? (
            <Form.Item label="lookback">
              <InputNumber
                min={2}
                max={250}
                value={lookback}
                onChange={(v) => setLookback(Number(v) || 20)}
              />
            </Form.Item>
          ) : null}
          {String(editRow?.template) === "TECH_RSI" ||
          String(editRow?.template) === "TECH_MA_BIAS" ? (
            <Form.Item label="period">
              <InputNumber
                min={2}
                max={250}
                value={period}
                onChange={(v) => setPeriod(Number(v) || 14)}
              />
            </Form.Item>
          ) : null}
          <Form.Item label="说明">
            <Input.TextArea value={desc} onChange={setDesc} autoSize />
          </Form.Item>
          <Typography.Text type="secondary">
            改参数后需重新「计算/重算」才会覆盖截面值。
          </Typography.Text>
        </Form>
      </Modal>

      <Modal
        title={`计算 ${factor || ""}`}
        visible={runOpen}
        onCancel={() => setRunOpen(false)}
        onOk={() => runMut.mutate()}
        confirmLoading={runMut.isPending}
        okButtonProps={{
          disabled: liveLocked || !factor || !runRange[0] || !runRange[1],
        }}
      >
        <Form layout="vertical" size="small">
          <Form.Item label="区间" required>
            <DatePicker.RangePicker
              style={{ width: "100%" }}
              value={runRange as [string, string]}
              onChange={(v) =>
                setRunRange(Array.isArray(v) ? (v as string[]) : [])
              }
            />
          </Form.Item>
          <Form.Item label="universe">
            <Select
              value={runUniverse}
              onChange={setRunUniverse}
              options={["TOP100", "HS300", "ZZ500", "SECTOR_LEADERS"]}
            />
          </Form.Item>
          <Typography.Text type="secondary">
            需区间 DQ gate passed；结果 UPSERT 到 research_factor_value。
          </Typography.Text>
        </Form>
      </Modal>
    </div>
  );
}
