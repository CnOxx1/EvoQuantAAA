import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Typography } from "@arco-design/web-react";
import {
  listAbnormalMoves,
  listDragonTiger,
  listNews,
  type ClientConfig,
  type JsonMap,
} from "../api/gateway";
import { zh } from "../i18n/zh";
import { fmtAmt, fmtPct, n, s } from "../lib/format";
import styles from "./SymbolContext.module.css";

function bare(symbol: string): string {
  const u = symbol.trim().toUpperCase();
  for (const suf of [".SH", ".SZ", ".BJ"]) {
    if (u.endsWith(suf)) return u.slice(0, -suf.length);
  }
  return u;
}

function lastOf(
  series: { trade_date: string; value: number }[] | undefined,
): number | null {
  if (!series?.length) return null;
  const v = Number(series[series.length - 1]?.value);
  return Number.isFinite(v) ? v : null;
}

export function SymbolContext({
  cfg,
  connected,
  selected,
  tradeDate,
  lastBar,
  name,
  indSeries,
  activeCodes,
}: {
  cfg: ClientConfig;
  connected: boolean;
  selected: string;
  tradeDate: string;
  lastBar: JsonMap | null;
  name?: string;
  indSeries: Record<string, { trade_date: string; value: number }[]>;
  activeCodes: string[];
}) {
  const code = bare(selected);

  const newsQ = useQuery({
    queryKey: ["ctx-news", cfg.apiBase, code],
    queryFn: () => listNews(cfg, { symbol: code, limit: 6 }),
    enabled: connected && Boolean(code),
  });
  const abnQ = useQuery({
    queryKey: ["ctx-abn", cfg.apiBase, tradeDate],
    queryFn: () => listAbnormalMoves(cfg, { tradeDate, limit: 200 }),
    enabled: connected && Boolean(code) && Boolean(tradeDate),
    staleTime: 30_000,
  });
  const lhbQ = useQuery({
    queryKey: ["ctx-lhb", cfg.apiBase, tradeDate],
    queryFn: () => listDragonTiger(cfg, { tradeDate, limit: 100 }),
    enabled: connected && Boolean(code) && Boolean(tradeDate),
    staleTime: 30_000,
  });

  const abnHits = useMemo(
    () =>
      (abnQ.data ?? []).filter((r) => bare(String(r.symbol || "")) === code).slice(0, 4),
    [abnQ.data, code],
  );
  const lhbHits = useMemo(
    () =>
      (lhbQ.data ?? []).filter((r) => bare(String(r.symbol || "")) === code).slice(0, 3),
    [lhbQ.data, code],
  );

  const ret = fmtPct(
    lastBar?.ret_1d != null ? Number(lastBar.ret_1d) * 100 : undefined,
  );

  const indRows = useMemo(() => {
    return activeCodes
      .map((c) => {
        const v = lastOf(indSeries[c]);
        return { code: c, value: v };
      })
      .filter((x) => x.value != null);
  }, [activeCodes, indSeries]);

  if (!selected) {
    return (
      <div className={styles.root}>
        <div className={styles.head}>{zh.ctx}</div>
        <div className={styles.empty}>{zh.hintClick}</div>
      </div>
    );
  }

  return (
    <div className={styles.root}>
      <div className={styles.head}>
        <span>{zh.ctx}</span>
        <span className={styles.headMeta}>
          <code>{code}</code>
          {name ? <span className={styles.name}>{name}</span> : null}
        </span>
      </div>

      <div className={styles.body}>
        <section className={styles.sec}>
          <div className={styles.secTitle}>{zh.ctxQuote}</div>
          {lastBar ? (
            <>
              <div className={styles.quoteTop}>
                <span className={`mono ${ret.up ? "up" : ret.down ? "down" : ""}`}>
                  {n(lastBar.close, 2)}
                </span>
                <span className={ret.up ? "up" : ret.down ? "down" : ""}>
                  {ret.text}
                </span>
                <span className={styles.muted}>{s(lastBar.trade_date)}</span>
              </div>
              <div className={styles.grid}>
                <div>
                  <span className={styles.k}>{zh.open}</span>
                  <code>{n(lastBar.open, 2)}</code>
                </div>
                <div>
                  <span className={styles.k}>{zh.high}</span>
                  <code className="up">{n(lastBar.high, 2)}</code>
                </div>
                <div>
                  <span className={styles.k}>{zh.low}</span>
                  <code className="down">{n(lastBar.low, 2)}</code>
                </div>
                <div>
                  <span className={styles.k}>{zh.close}</span>
                  <code>{n(lastBar.close, 2)}</code>
                </div>
                <div>
                  <span className={styles.k}>{zh.vol}</span>
                  <code>{fmtAmt(lastBar.volume)}</code>
                </div>
                <div>
                  <span className={styles.k}>{zh.amount}</span>
                  <code>{fmtAmt(lastBar.amount)}</code>
                </div>
              </div>
              <div className={styles.flags}>
                {Number(lastBar.is_suspended) ? (
                  <span className={styles.flag}>{zh.suspended}</span>
                ) : null}
                {Number(lastBar.is_limit_up) ? (
                  <span className={`${styles.flag} up`}>{zh.limitUp}</span>
                ) : null}
                {Number(lastBar.is_limit_down) ? (
                  <span className={`${styles.flag} down`}>{zh.limitDown}</span>
                ) : null}
                {!Number(lastBar.can_buy) || !Number(lastBar.can_sell) ? (
                  <span className={styles.flag}>{zh.tradeRestricted}</span>
                ) : null}
              </div>
            </>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.noBars}
            </Typography.Text>
          )}
        </section>

        <section className={styles.sec}>
          <div className={styles.secTitle}>
            {zh.ctxInd} · {indRows.length}
          </div>
          {indRows.length ? (
            <div className={styles.indGrid}>
              {indRows.map((r) => (
                <div key={r.code} className={styles.indCell}>
                  <span className={styles.indCode}>{r.code}</span>
                  <code>{n(r.value, 4)}</code>
                </div>
              ))}
            </div>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.ctxIndEmpty}
            </Typography.Text>
          )}
        </section>

        <section className={styles.sec}>
          <div className={styles.secTitle}>
            {zh.ctxAbn} · {abnHits.length}
          </div>
          {abnHits.length ? (
            <ul className={styles.feed}>
              {abnHits.map((r, i) => (
                <li key={`${s(r.symbol)}-${i}`}>
                  <span className={styles.feedTag}>{s(r.change_type)}</span>
                  <span className={styles.feedMain}>
                    {s(r.event_time).slice(0, 16)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.ctxNone}
            </Typography.Text>
          )}
        </section>

        <section className={styles.sec}>
          <div className={styles.secTitle}>
            {zh.ctxLhb} · {lhbHits.length}
          </div>
          {lhbHits.length ? (
            <ul className={styles.feed}>
              {lhbHits.map((r, i) => {
                const p = fmtPct(r.pct_chg);
                return (
                  <li key={`${s(r.symbol)}-${i}`}>
                    <span className={p.up ? "up" : p.down ? "down" : ""}>
                      {p.text}
                    </span>
                    <span className={styles.feedMain}>
                      {zh.net} {fmtAmt(r.net_amount)}
                    </span>
                    <span className={styles.feedSub}>{s(r.reason)}</span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.ctxNone}
            </Typography.Text>
          )}
        </section>

        <section className={styles.sec}>
          <div className={styles.secTitle}>
            {zh.ctxNews} · {newsQ.data?.length ?? 0}
          </div>
          {newsQ.isLoading ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.loading}
            </Typography.Text>
          ) : newsQ.data?.length ? (
            <ul className={styles.feed}>
              {newsQ.data.map((r) => (
                <li key={s(r.source_news_id, s(r.title))}>
                  <span className={styles.feedTag}>{s(r.channel)}</span>
                  {r.url ? (
                    <a
                      className={styles.feedLink}
                      href={String(r.url)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {s(r.title)}
                    </a>
                  ) : (
                    <span className={styles.feedMain}>{s(r.title)}</span>
                  )}
                  <span className={styles.feedSub}>
                    {s(r.publish_time).slice(0, 16)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {zh.ctxNone}
            </Typography.Text>
          )}
        </section>
      </div>
    </div>
  );
}
