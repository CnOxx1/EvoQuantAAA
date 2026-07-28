import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Drawer,
  Input,
  Message,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "@arco-design/web-react";
import {
  getF10,
  getMarketIndicatorsMeta,
  getMarketRankMeta,
  listAbnormalMoves,
  listDragonTiger,
  listMarketBars,
  listMarketIndicators,
  listMarketRanks,
  listNews,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import {
  ChartPanel,
  type CandlePoint,
  type ChartPoint,
  type LinePoint,
  type OverlayLine,
  type SubPane,
} from "../components/ChartPanel";
import { IndicatorPicker } from "../components/IndicatorPicker";
import { SymbolContext } from "../components/SymbolContext";
import {
  DEFAULT_ACTIVE,
  PRESETS,
  colorFor,
  placementOf,
  presetActive,
  styleOf,
  togglePreset,
  type IndicatorMetaItem,
} from "../lib/indicatorCatalog";
import { zh } from "../i18n/zh";
import { fmtAmt, fmtPct, s } from "../lib/format";
import type { Settings } from "../state/settings";
import styles from "./MarketPage.module.css";

type TabKey = "ranks" | "abnormal" | "news" | "lhb";

const TABLE_PAGE = {
  pageSize: 20,
  size: "mini" as const,
  showTotal: true,
  showJumper: true,
};

const RANK_ZH: Record<string, string> = {
  PCT_CHG_UP: zh.pctUp,
  PCT_CHG_DOWN: zh.pctDown,
  VOLUME: zh.volRank,
  AMOUNT: zh.amtRank,
  TURNOVER: zh.turnRank,
};

const CHANNEL_ZH: Record<string, string> = {
  official: zh.chOfficial,
  eastmoney: zh.chEm,
  policy: zh.chPolicy,
  forum: zh.chForum,
  mock: "mock",
};

export function MarketPage({
  cfg,
  settings,
  connected,
  initialTab = "ranks",
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
  initialTab?: TabKey;
}) {
  const [searchParams] = useSearchParams();
  const urlSymbol = (searchParams.get("symbol") || "").trim();
  const [tab, setTab] = useState<TabKey>(initialTab);
  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);
  const [tradeDate, setTradeDate] = useState("");
  const [rankType, setRankType] = useState("PCT_CHG_UP");
  const [newsChannel, setNewsChannel] = useState("");
  const [symbolQ, setSymbolQ] = useState("");
  const [abnFilter, setAbnFilter] = useState("");
  const [selected, setSelected] = useState(urlSymbol);
  const [barFreq, setBarFreq] = useState<"1d" | "15m" | "60m">("1d");
  const [f10Open, setF10Open] = useState(false);
  const [activeInd, setActiveInd] = useState<string[]>(DEFAULT_ACTIVE);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (urlSymbol) setSelected(urlSymbol);
  }, [urlSymbol]);

  const indMetaQ = useQuery({
    queryKey: ["ind-meta", cfg.apiBase],
    queryFn: () => getMarketIndicatorsMeta(cfg),
    enabled: connected,
    staleTime: 60_000,
  });
  const indSymMetaQ = useQuery({
    queryKey: ["ind-meta-sym", cfg.apiBase, selected],
    queryFn: () => getMarketIndicatorsMeta(cfg, { symbol: selected }),
    enabled: connected && Boolean(selected),
    staleTime: 30_000,
  });

  const catalog: IndicatorMetaItem[] = indMetaQ.data?.codes ?? [];
  const metaByCode = useMemo(() => {
    const m = new Map<string, IndicatorMetaItem>();
    for (const c of catalog) m.set(c.code, c);
    return m;
  }, [catalog]);
  const availableCodes = useMemo(
    () => new Set((indSymMetaQ.data?.codes ?? []).map((c) => c.code)),
    [indSymMetaQ.data],
  );

  const metaQ = useQuery({
    queryKey: ["market-meta", cfg.apiBase],
    queryFn: () => getMarketRankMeta(cfg),
    enabled: connected,
  });
  const dates = metaQ.data?.trade_dates ?? [];
  const types = metaQ.data?.rank_types ?? [];
  const effectiveDate = tradeDate || dates[0] || settings.asOf;
  const sym = symbolQ.trim();

  useEffect(() => {
    if (dates.length && (!tradeDate || !dates.includes(tradeDate))) {
      setTradeDate(dates[0]);
    }
  }, [dates, tradeDate]);

  useEffect(() => {
    if (types.length && !types.includes(rankType)) setRankType(types[0]);
  }, [types, rankType]);

  const ranksQ = useQuery({
    queryKey: ["ranks", cfg.apiBase, effectiveDate, rankType],
    queryFn: () =>
      listMarketRanks(cfg, {
        tradeDate: effectiveDate,
        rankType,
        limit: 100,
      }),
    enabled: connected && tab === "ranks" && Boolean(effectiveDate),
  });
  const abnQ = useQuery({
    queryKey: ["abn", cfg.apiBase, effectiveDate],
    queryFn: () =>
      listAbnormalMoves(cfg, { tradeDate: effectiveDate, limit: 200 }),
    enabled: connected && tab === "abnormal" && Boolean(effectiveDate),
  });
  const newsQ = useQuery({
    queryKey: ["news", cfg.apiBase, newsChannel, sym],
    queryFn: () =>
      listNews(cfg, {
        channel: newsChannel || undefined,
        symbol: sym || undefined,
        limit: 80,
      }),
    enabled: connected && tab === "news",
  });
  const lhbQ = useQuery({
    queryKey: ["lhb", cfg.apiBase, effectiveDate],
    queryFn: () =>
      listDragonTiger(cfg, { tradeDate: effectiveDate, limit: 100 }),
    enabled: connected && tab === "lhb" && Boolean(effectiveDate),
  });

  const ranks = useMemo(() => {
    let rows = ranksQ.data ?? [];
    if (sym) {
      rows = rows.filter(
        (r) =>
          String(r.symbol || "").includes(sym) ||
          String(r.name || "").includes(sym),
      );
    }
    return rows;
  }, [ranksQ.data, sym]);

  const abnTypeCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of abnQ.data ?? []) {
      const k = String(r.change_type || zh.other);
      m.set(k, (m.get(k) || 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [abnQ.data]);

  const abnRows = useMemo(() => {
    let rows = abnQ.data ?? [];
    if (abnFilter) {
      rows = rows.filter((r) => String(r.change_type) === abnFilter);
    }
    if (sym) {
      rows = rows.filter(
        (r) =>
          String(r.symbol || "").includes(sym) ||
          String(r.name || "").includes(sym),
      );
    }
    return rows;
  }, [abnQ.data, abnFilter, sym]);

  const lhbRows = useMemo(() => {
    let rows = lhbQ.data ?? [];
    if (sym) rows = rows.filter((r) => String(r.symbol || "").includes(sym));
    return rows;
  }, [lhbQ.data, sym]);

  useEffect(() => {
    if (!urlSymbol) setSelected("");
  }, [tab, effectiveDate, rankType, urlSymbol]);

  const barsQ = useQuery({
    queryKey: ["bars", cfg.apiBase, selected, effectiveDate, barFreq],
    queryFn: () =>
      listMarketBars(cfg, {
        symbol: selected,
        end: effectiveDate || undefined,
        factorType: "qfq",
        freq: barFreq,
        limit: barFreq === "1d" ? 180 : 480,
      }),
    enabled: connected && Boolean(selected),
  });

  const f10Q = useQuery({
    queryKey: ["f10", cfg.apiBase, selected, settings.asOf],
    queryFn: () => getF10(cfg, selected, settings.asOf),
    enabled: connected && Boolean(selected) && f10Open,
  });

  const indQ = useQuery({
    queryKey: [
      "indicators",
      cfg.apiBase,
      selected,
      effectiveDate,
      activeInd.join(","),
    ],
    queryFn: () =>
      listMarketIndicators(cfg, {
        symbol: selected,
        codes: activeInd,
        end: effectiveDate || undefined,
        factorType: "qfq",
        limit: 180,
      }),
    enabled:
      connected &&
      Boolean(selected) &&
      activeInd.length > 0 &&
      barFreq === "1d",
  });

  const candles: CandlePoint[] = useMemo(() => {
    const bars = barsQ.data?.bars ?? [];
    return bars
      .map((b) => {
        if (barFreq === "1d") {
          return {
            time: String(b.trade_date || "").slice(0, 10),
            open: Number(b.open),
            high: Number(b.high),
            low: Number(b.low),
            close: Number(b.close),
          };
        }
        const raw = String(b.bar_time || b.trade_date || "");
        const ts = Math.floor(new Date(raw.replace(" ", "T") + "+08:00").getTime() / 1000);
        return {
          time: ts,
          open: Number(b.open),
          high: Number(b.high),
          low: Number(b.low),
          close: Number(b.close),
        };
      })
      .filter((c) => {
        const timeOk =
          typeof c.time === "number"
            ? Number.isFinite(c.time) && c.time > 0
            : /^\d{4}-\d{2}-\d{2}$/.test(c.time);
        return (
          timeOk &&
          Number.isFinite(c.open) &&
          Number.isFinite(c.high) &&
          Number.isFinite(c.low) &&
          Number.isFinite(c.close)
        );
      });
  }, [barsQ.data, barFreq]);

  const toLine = (code: string): LinePoint[] =>
    (indQ.data?.series?.[code] ?? [])
      .map((p) => ({
        time: String(p.trade_date || "").slice(0, 10),
        value: Number(p.value),
      }))
      .filter(
        (p) =>
          typeof p.time === "string" &&
          /^\d{4}-\d{2}-\d{2}$/.test(p.time) &&
          Number.isFinite(p.value),
      );

  const overlays: OverlayLine[] = useMemo(() => {
    if (!selected || barFreq !== "1d") return [];
    return activeInd
      .filter((c) => placementOf(c, metaByCode) === "overlay")
      .map((code, i) => ({
        id: code,
        color: colorFor(i),
        data: toLine(code),
        lineWidth: code === "MA_20" || code === "BOLL_MID" ? 2 : 1,
      }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, activeInd, indQ.data, metaByCode, barFreq]);

  const subPane: SubPane = useMemo(() => {
    if (!selected || barFreq !== "1d") return { kind: "none" };
    const series = activeInd
      .filter((c) => placementOf(c, metaByCode) === "sub")
      .map((code, i) => ({
        id: code,
        color: colorFor(i + 4),
        data: toLine(code),
        style: styleOf(code, metaByCode),
      }));
    if (!series.length) return { kind: "none" };
    return { kind: "multi", series };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, activeInd, indQ.data, metaByCode, barFreq]);

  const lastBar = useMemo(() => {
    const bars = barsQ.data?.bars ?? [];
    if (!bars.length) return null;
    return bars[bars.length - 1] as JsonMap;
  }, [barsQ.data]);

  const selectedName = useMemo(() => {
    if (!selected) return "";
    const pools: JsonMap[] = [
      ...(ranksQ.data ?? []),
      ...(abnQ.data ?? []),
      ...(lhbQ.data ?? []),
    ];
    const hit = pools.find((r) => String(r.symbol || "") === selected);
    return hit ? s(hit.name, "") : "";
  }, [selected, ranksQ.data, abnQ.data, lhbQ.data]);

  const chartSeries: ChartPoint[] = useMemo(() => {
    if (tab === "ranks") {
      return ranks.slice(0, 40).map((r, i) => {
        const v = Number(r.pct_chg);
        return {
          time: (i + 1) * 86400,
          value: Number.isFinite(v) ? v : 0,
          color: v >= 0 ? "#f53f3f" : "#00b42a",
        };
      });
    }
    if (tab === "lhb") {
      return lhbRows.slice(0, 40).map((r, i) => {
        const v = Number(r.net_amount);
        const scaled = Number.isFinite(v) ? v / 1e8 : 0;
        return {
          time: (i + 1) * 86400,
          value: scaled,
          color: scaled >= 0 ? "#f53f3f" : "#00b42a",
        };
      });
    }
    if (tab === "abnormal") {
      return abnTypeCounts.map(([, c], i) => ({
        time: (i + 1) * 86400,
        value: c,
        color: "#165dff",
      }));
    }
    return [];
  }, [tab, ranks, lhbRows, abnTypeCounts]);

  if (!connected) {
    return (
      <div className="page">
        <Typography.Text type="secondary">{zh.notConnected}</Typography.Text>
      </div>
    );
  }

  return (
    <div className={`pageBleed ${styles.workbench}`}>
      <div className={styles.bar}>
        <Space size={8}>
          <Typography.Text className={styles.title}>{zh.marketIntel}</Typography.Text>
          <Tabs
            type="rounded"
            size="small"
            activeTab={tab}
            onChange={(k) => setTab(k as TabKey)}
            style={{ marginBottom: 0 }}
          >
            <Tabs.TabPane key="ranks" title={zh.ranks} />
            <Tabs.TabPane key="abnormal" title={zh.abnormal} />
            <Tabs.TabPane key="news" title={zh.news} />
            <Tabs.TabPane key="lhb" title={zh.lhb} />
          </Tabs>
        </Space>
        <Space size={8}>
          {tab !== "news" ? (
            <Select
              size="mini"
              style={{ width: 120 }}
              value={effectiveDate}
              onChange={setTradeDate}
              options={(dates.length ? dates : [effectiveDate]).map((d) => ({
                label: d,
                value: d,
              }))}
            />
          ) : (
            <Select
              size="mini"
              allowClear
              placeholder={zh.channel}
              style={{ width: 120 }}
              value={newsChannel || undefined}
              onChange={(v) => setNewsChannel(v || "")}
              options={Object.entries(CHANNEL_ZH).map(([k, v]) => ({
                label: v,
                value: k,
              }))}
            />
          )}
          <Input
            size="mini"
            style={{ width: 140 }}
            value={symbolQ}
            onChange={setSymbolQ}
            placeholder={zh.filter}
            allowClear
          />
        </Space>
      </div>

      {tab === "ranks" ? (
        <div className={styles.chips}>
          {(types.length ? types : Object.keys(RANK_ZH)).map((t) => (
            <button
              key={t}
              type="button"
              className={`${styles.chip} ${rankType === t ? styles.chipOn : ""}`}
              onClick={() => setRankType(t)}
            >
              {RANK_ZH[t] || t}
            </button>
          ))}
        </div>
      ) : null}

      {tab === "abnormal" ? (
        <div className={styles.chips}>
          <button
            type="button"
            className={`${styles.chip} ${!abnFilter ? styles.chipOn : ""}`}
            onClick={() => setAbnFilter("")}
          >
            {zh.all} {abnQ.data?.length ?? 0}
          </button>
          {abnTypeCounts.map(([t, c]) => (
            <button
              key={t}
              type="button"
              className={`${styles.chip} ${abnFilter === t ? styles.chipOn : ""}`}
              onClick={() => setAbnFilter(t)}
            >
              {t} {c}
            </button>
          ))}
        </div>
      ) : null}

      <div className={styles.split}>
        <div className={styles.list}>
          {tab === "ranks" ? (
            <Table
              rowKey={(r: JsonMap) => `${s(r.symbol)}-${s(r.rank_no)}`}
              size="small"
              pagination={TABLE_PAGE}
              loading={ranksQ.isLoading}
              data={ranks}
              scroll={{ x: 560 }}
              rowClassName={(r) =>
                s(r.symbol) === selected ? styles.rowOn : ""
              }
              onRow={(r) => ({
                onClick: () => setSelected(s(r.symbol, "")),
              })}
              columns={[
                {
                  title: "#",
                  dataIndex: "rank_no",
                  width: 56,
                  render: (v) => <span className="mono">{s(v)}</span>,
                },
                {
                  title: zh.symbol,
                  width: 120,
                  render: (_, r) => {
                    const name = s(r.name, "");
                    const showName = Boolean(name) && name !== "-" && name !== "\u2014";
                    return (
                      <div>
                        <div className="mono">{s(r.symbol)}</div>
                        {showName ? (
                          <div className={styles.sub}>{name}</div>
                        ) : null}
                      </div>
                    );
                  },
                },
                {
                  title: zh.chg,
                  width: 88,
                  render: (_, r) => {
                    const p = fmtPct(r.pct_chg);
                    return (
                      <span className={p.up ? "up" : p.down ? "down" : ""}>
                        {p.text}
                      </span>
                    );
                  },
                },
                {
                  title: zh.close,
                  width: 72,
                  render: (_, r) => (
                    <span className="mono">{Number(r.close).toFixed(2)}</span>
                  ),
                },
                {
                  title: zh.amount,
                  width: 96,
                  render: (_, r) => (
                    <span className="mono">{fmtAmt(r.amount)}</span>
                  ),
                },
              ]}
            />
          ) : null}

          {tab === "abnormal" ? (
            <Table
              rowKey={(r: JsonMap) =>
                `${s(r.source_event_id)}-${s(r.symbol)}-${s(r.event_time)}`
              }
              size="small"
              pagination={TABLE_PAGE}
              loading={abnQ.isLoading}
              data={abnRows}
              onRow={(r) => ({
                onClick: () => setSelected(s(r.symbol, "")),
              })}
              columns={[
                {
                  title: zh.time,
                  width: 150,
                  render: (_, r) => (
                    <span className="mono">{s(r.event_time)}</span>
                  ),
                },
                {
                  title: zh.symbol,
                  render: (_, r) => (
                    <div>
                      <div className="mono">{s(r.symbol)}</div>
                      <div className={styles.sub}>{s(r.name)}</div>
                    </div>
                  ),
                },
                {
                  title: zh.type,
                  width: 120,
                  render: (_, r) => (
                    <Tag size="small">{s(r.change_type)}</Tag>
                  ),
                },
                {
                  title: zh.info,
                  render: (_, r) => (
                    <span className={styles.clip}>{s(r.related_info)}</span>
                  ),
                },
              ]}
            />
          ) : null}

          {tab === "news" ? (
            <Table
              rowKey={(r: JsonMap) => s(r.source_news_id ?? r.title)}
              size="small"
              pagination={TABLE_PAGE}
              loading={newsQ.isLoading}
              data={newsQ.data ?? []}
              columns={[
                {
                  title: zh.time,
                  width: 150,
                  render: (_, r) => (
                    <span className="mono">{s(r.publish_time)}</span>
                  ),
                },
                {
                  title: zh.channel,
                  width: 90,
                  render: (_, r) =>
                    CHANNEL_ZH[String(r.channel)] || s(r.channel),
                },
                {
                  title: zh.title,
                  render: (_, r) =>
                    r.url ? (
                      <a href={String(r.url)} target="_blank" rel="noreferrer">
                        {s(r.title)}
                      </a>
                    ) : (
                      s(r.title)
                    ),
                },
              ]}
            />
          ) : null}

          {tab === "lhb" ? (
            <Table
              rowKey={(r: JsonMap) => `${s(r.symbol)}-${s(r.source_event_id)}`}
              size="small"
              pagination={TABLE_PAGE}
              loading={lhbQ.isLoading}
              data={lhbRows}
              onRow={(r) => ({
                onClick: () => setSelected(s(r.symbol, "")),
              })}
              columns={[
                {
                  title: zh.code,
                  width: 80,
                  render: (_, r) => (
                    <span className="mono">{s(r.symbol)}</span>
                  ),
                },
                {
                  title: zh.chg,
                  width: 88,
                  render: (_, r) => {
                    const p = fmtPct(r.pct_chg);
                    return (
                      <span className={p.up ? "up" : p.down ? "down" : ""}>
                        {p.text}
                      </span>
                    );
                  },
                },
                {
                  title: zh.net,
                  width: 88,
                  render: (_, r) => {
                    const x = Number(r.net_amount);
                    const cls = x > 0 ? "up" : x < 0 ? "down" : "";
                    return (
                      <span className={cls}>{fmtAmt(r.net_amount)}</span>
                    );
                  },
                },
                { title: zh.reason, render: (_, r) => s(r.reason) },
              ]}
            />
          ) : null}
        </div>

        <div className={styles.side}>
          {selected ? (
            <Space style={{ marginBottom: 8 }} size={8} wrap>
              <Select
                size="mini"
                value={barFreq}
                style={{ width: 88 }}
                onChange={(v) => setBarFreq(v as "1d" | "15m" | "60m")}
                options={[
                  { label: "日K", value: "1d" },
                  { label: "15m", value: "15m" },
                  { label: "60m", value: "60m" },
                ]}
              />
              <Button size="mini" type="outline" onClick={() => setF10Open(true)}>
                F10
              </Button>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {selectedName || selected}
              </Typography.Text>
            </Space>
          ) : null}
          <ChartPanel
            title={
              selected
                ? `${barFreq === "1d" ? zh.klineQfq : barFreq} ${selected}`
                : tab === "ranks"
                  ? zh.crossSection
                  : tab === "lhb"
                    ? zh.lhbNetYi
                    : tab === "abnormal"
                      ? zh.abnDist
                      : zh.newsPlaceholder
            }
            subtitle={
              selected
                ? barsQ.isLoading
                  ? zh.barsLoading
                  : indQ.isLoading && barFreq === "1d"
                    ? zh.indLoading
                    : `${barFreq} / n=${candles.length}${
                        barFreq === "1d" && activeInd.length
                          ? ` / ind=${activeInd.length}`
                          : ""
                      }`
                : tab === "ranks"
                  ? `${RANK_ZH[rankType] || rankType} / Top40`
                  : effectiveDate
            }
            mode={selected ? "candle" : "histogram"}
            candles={selected ? candles : []}
            overlays={selected ? overlays : []}
            subPane={selected ? subPane : { kind: "none" }}
            data={selected || tab === "news" ? [] : chartSeries}
            height={selected ? 420 : 280}
            emptyHint={
              selected
                ? barsQ.isLoading
                  ? zh.barsLoading
                  : zh.noBars
                : zh.hintClick
            }
            indicators={
              selected
                ? [
                    ...PRESETS.map((p) => ({
                      id: p.id,
                      label: p.label,
                      active: presetActive(activeInd, p),
                    })),
                    {
                      id: "all",
                      label: `+${catalog.length || ""}`,
                      active: pickerOpen,
                    },
                  ]
                : undefined
            }
            onToggleIndicator={(id) => {
              if (id === "all") {
                setPickerOpen(true);
                return;
              }
              const preset = PRESETS.find((p) => p.id === id);
              if (!preset) return;
              const { next, msg } = togglePreset(
                activeInd,
                preset,
                metaByCode,
              );
              if (msg) Message.warning(msg);
              setActiveInd(next);
            }}
          />
          <IndicatorPicker
            visible={pickerOpen}
            onClose={() => setPickerOpen(false)}
            catalog={catalog}
            available={availableCodes}
            active={activeInd}
            onChange={setActiveInd}
          />
          <SymbolContext
            cfg={cfg}
            connected={connected}
            selected={selected}
            tradeDate={effectiveDate}
            lastBar={lastBar}
            name={selectedName}
            indSeries={indQ.data?.series ?? {}}
            activeCodes={activeInd}
          />
          <Drawer
            width={480}
            title={`F10 ${selected}`}
            visible={f10Open}
            onCancel={() => setF10Open(false)}
            footer={null}
          >
            {f10Q.isLoading ? (
              <Typography.Text type="secondary">加载中…</Typography.Text>
            ) : f10Q.data ? (
              <Space direction="vertical" style={{ width: "100%" }} size={12}>
                {(
                  [
                    ["上市资料", f10Q.data.listing],
                    ["行业", f10Q.data.industry],
                    ["估值", f10Q.data.valuation],
                    ["财务", f10Q.data.fundamentals],
                    ["股东", f10Q.data.holders],
                    ["股本", f10Q.data.share_capital],
                  ] as [string, unknown][]
                ).map(([title, block]) => (
                  <div key={title}>
                    <Typography.Text bold>{title}</Typography.Text>
                    <pre
                      style={{
                        margin: "6px 0 0",
                        fontSize: 12,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                      }}
                    >
                      {block ? JSON.stringify(block, null, 2) : "—"}
                    </pre>
                  </div>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">无资料</Typography.Text>
            )}
          </Drawer>
        </div>
      </div>
    </div>
  );
}
