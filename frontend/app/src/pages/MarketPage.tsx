import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getMarketRankMeta,
  listAbnormalMoves,
  listDragonTiger,
  listMarketRanks,
  listNews,
  type ClientConfig,
} from "../api/gateway";
import { DataTable } from "../components/DataTable";
import { StatusPill } from "../components/StatusPill";
import { n, s } from "../lib/format";
import type { Settings } from "../state/settings";
import styles from "./pages.module.css";

type Tab = "ranks" | "abnormal" | "news" | "lhb";

const RANK_ZH: Record<string, string> = {
  PCT_CHG_UP: "涨幅榜",
  PCT_CHG_DOWN: "跌幅榜",
  VOLUME: "成交量榜",
  AMOUNT: "成交额榜",
  TURNOVER: "换手榜",
};

const CHANNEL_ZH: Record<string, string> = {
  official: "官方快讯",
  eastmoney: "东财",
  policy: "政策",
  forum: "论坛情绪",
  mock: "mock",
};

export function MarketPage({
  cfg,
  settings,
  connected,
}: {
  cfg: ClientConfig;
  settings: Settings;
  connected: boolean;
}) {
  const [tab, setTab] = useState<Tab>("ranks");
  const [tradeDate, setTradeDate] = useState(settings.asOf);
  const [rankType, setRankType] = useState("PCT_CHG_UP");
  const [newsChannel, setNewsChannel] = useState("");
  const [newsSymbol, setNewsSymbol] = useState("");

  const metaQ = useQuery({
    queryKey: ["market-rank-meta", cfg.apiBase],
    queryFn: () => getMarketRankMeta(cfg),
    enabled: connected,
  });

  const dates = metaQ.data?.trade_dates ?? [];
  const types = metaQ.data?.rank_types ?? [];

  useEffect(() => {
    if (!dates.length) return;
    if (!tradeDate || !dates.includes(tradeDate)) {
      setTradeDate(dates[0]);
    }
  }, [dates, tradeDate]);

  const effectiveDate = tradeDate || dates[0] || settings.asOf;

  const ranksQ = useQuery({
    queryKey: ["market-ranks", cfg.apiBase, effectiveDate, rankType],
    queryFn: () =>
      listMarketRanks(cfg, {
        tradeDate: effectiveDate,
        rankType: rankType || undefined,
        limit: 100,
      }),
    enabled: connected && tab === "ranks",
  });

  const abnQ = useQuery({
    queryKey: ["market-abnormal", cfg.apiBase, effectiveDate],
    queryFn: () =>
      listAbnormalMoves(cfg, { tradeDate: effectiveDate, limit: 150 }),
    enabled: connected && tab === "abnormal",
  });

  const newsQ = useQuery({
    queryKey: ["market-news", cfg.apiBase, newsChannel, newsSymbol],
    queryFn: () =>
      listNews(cfg, {
        channel: newsChannel || undefined,
        symbol: newsSymbol.trim() || undefined,
        limit: 80,
      }),
    enabled: connected && tab === "news",
  });

  const lhbQ = useQuery({
    queryKey: ["market-lhb", cfg.apiBase, effectiveDate],
    queryFn: () =>
      listDragonTiger(cfg, { tradeDate: effectiveDate, limit: 100 }),
    enabled: connected && tab === "lhb",
  });

  const abnTypes = useMemo(() => {
    const set = new Set<string>();
    for (const r of abnQ.data ?? []) {
      if (r.change_type) set.add(String(r.change_type));
    }
    return [...set];
  }, [abnQ.data]);

  const [abnFilter, setAbnFilter] = useState("");
  const abnRows = (abnQ.data ?? []).filter(
    (r) => !abnFilter || String(r.change_type) === abnFilter,
  );

  return (
    <div>
      <h1>市场情报</h1>
      <p className="lede">
        展示后端已落库的榜单 / 异动 / 新闻 / 龙虎榜，便于盘面分析。数据只读，不触发取数。
      </p>

      {!connected ? (
        <p className={styles.muted}>未连接网关，请先到「设置」填写 API 地址。</p>
      ) : (
        <>
          <div className={styles.toolbar}>
            {(tab === "ranks" || tab === "abnormal" || tab === "lhb") && (
              <label>
                交易日
                <select
                  value={effectiveDate}
                  onChange={(e) => setTradeDate(e.target.value)}
                >
                  {(dates.length ? dates : [effectiveDate]).map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {tab === "ranks" ? (
              <label>
                榜单类型
                <select
                  value={rankType}
                  onChange={(e) => setRankType(e.target.value)}
                >
                  {(types.length
                    ? types
                    : Object.keys(RANK_ZH)
                  ).map((t) => (
                    <option key={t} value={t}>
                      {RANK_ZH[t] || t}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {tab === "abnormal" ? (
              <label>
                异动类型
                <select
                  value={abnFilter}
                  onChange={(e) => setAbnFilter(e.target.value)}
                >
                  <option value="">全部</option>
                  {abnTypes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {tab === "news" ? (
              <>
                <label>
                  频道
                  <select
                    value={newsChannel}
                    onChange={(e) => setNewsChannel(e.target.value)}
                  >
                    <option value="">全部</option>
                    {Object.entries(CHANNEL_ZH).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  代码（可选）
                  <input
                    className="mono"
                    value={newsSymbol}
                    onChange={(e) => setNewsSymbol(e.target.value)}
                    placeholder="如 600000"
                  />
                </label>
              </>
            ) : null}
          </div>

          <div className={styles.btnRow} style={{ marginBottom: "0.85rem" }}>
            {(
              [
                ["ranks", "榜单"],
                ["abnormal", "异动"],
                ["news", "新闻"],
                ["lhb", "龙虎榜"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                className={tab === k ? styles.primary : styles.secondary}
                onClick={() => setTab(k)}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "ranks" ? (
            <section className={styles.panel}>
              <h2>
                {RANK_ZH[rankType] || rankType} · {effectiveDate}（
                {ranksQ.data?.length ?? 0}）
              </h2>
              <DataTable
                headers={[
                  "名次",
                  "代码",
                  "名称",
                  "涨跌幅%",
                  "收盘",
                  "成交量",
                  "成交额",
                  "换手",
                ]}
                empty="该日无榜单数据"
                isEmpty={(ranksQ.data ?? []).length === 0}
              >
                {(ranksQ.data ?? []).map((r) => (
                  <tr key={`${s(r.rank_type)}-${s(r.symbol)}-${s(r.rank_no)}`}>
                    <td>{n(r.rank_no, 0)}</td>
                    <td className="mono">{s(r.symbol)}</td>
                    <td>{s(r.name)}</td>
                    <td>{n(r.pct_chg, 2)}</td>
                    <td>{n(r.close)}</td>
                    <td>{n(r.volume, 0)}</td>
                    <td>{n(r.amount, 0)}</td>
                    <td>{n(r.turnover, 4)}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
          ) : null}

          {tab === "abnormal" ? (
            <section className={styles.panel}>
              <h2>
                盘口异动 · {effectiveDate}（{abnRows.length}）
              </h2>
              <DataTable
                headers={["时间", "代码", "名称", "类型", "相关信息"]}
                empty="该日无异动"
                isEmpty={abnRows.length === 0}
              >
                {abnRows.map((r, i) => (
                  <tr key={`${s(r.source_event_id)}-${i}`}>
                    <td className="mono">{s(r.event_time)}</td>
                    <td className="mono">{s(r.symbol)}</td>
                    <td>{s(r.name)}</td>
                    <td>
                      <StatusPill tone="info">{s(r.change_type)}</StatusPill>
                    </td>
                    <td className={styles.muted}>{s(r.related_info)}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
          ) : null}

          {tab === "news" ? (
            <section className={styles.panel}>
              <h2>新闻 / 舆情（{newsQ.data?.length ?? 0}）</h2>
              <DataTable
                headers={["时间", "频道", "代码", "标题", "来源"]}
                empty="暂无新闻"
                isEmpty={(newsQ.data ?? []).length === 0}
              >
                {(newsQ.data ?? []).map((r) => (
                  <tr key={s(r.source_news_id ?? r.title)}>
                    <td className="mono">{s(r.publish_time)}</td>
                    <td>
                      {CHANNEL_ZH[String(r.channel)] || s(r.channel)}
                    </td>
                    <td className="mono">{s(r.symbol)}</td>
                    <td>
                      {r.url ? (
                        <a href={String(r.url)} target="_blank" rel="noreferrer">
                          {s(r.title)}
                        </a>
                      ) : (
                        s(r.title)
                      )}
                      {r.summary ? (
                        <div className={styles.muted}>{s(r.summary)}</div>
                      ) : null}
                    </td>
                    <td>{s(r.media_source ?? r.source)}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
          ) : null}

          {tab === "lhb" ? (
            <section className={styles.panel}>
              <h2>
                龙虎榜 · {effectiveDate}（{lhbQ.data?.length ?? 0}）
              </h2>
              <DataTable
                headers={[
                  "代码",
                  "涨跌幅%",
                  "收盘",
                  "净额",
                  "买入",
                  "卖出",
                  "上榜原因",
                ]}
                empty="该日无龙虎榜"
                isEmpty={(lhbQ.data ?? []).length === 0}
              >
                {(lhbQ.data ?? []).map((r) => (
                  <tr key={`${s(r.symbol)}-${s(r.source_event_id)}`}>
                    <td className="mono">{s(r.symbol)}</td>
                    <td>{n(r.pct_chg, 2)}</td>
                    <td>{n(r.close)}</td>
                    <td>{n(r.net_amount, 0)}</td>
                    <td>{n(r.buy_amount, 0)}</td>
                    <td>{n(r.sell_amount, 0)}</td>
                    <td>{s(r.reason)}</td>
                  </tr>
                ))}
              </DataTable>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
