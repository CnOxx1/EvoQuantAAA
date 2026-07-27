from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any

from data_ingest.core_market.models import (
    ABNORMAL_CHANGE_TYPES,
    DEFAULT_RANK_TOP_N,
    RANK_TYPES,
    FetchBundle,
    FetchRequest,
)
from data_ingest.core_market.sources.base import CoreMarketSource
from data_ingest.ingest_common.parse import as_float, as_str, col_by_keywords
from shared.akshare_call import call_with_retry
from shared.db import get_conn

logger = logging.getLogger(__name__)


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 akshare，请执行: pip install -r requirements.txt"
        ) from exc
    return ak


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _normalize_bar_time(value: Any) -> str | None:
    """统一为 YYYY-MM-DD HH:MM:SS。"""
    if value is None:
        return None
    s = str(value).strip().replace("/", "-").replace("T", " ")
    if not s:
        return None
    if len(s) == 16 and s[10] == " ":  # YYYY-MM-DD HH:MM
        s = s + ":00"
    if len(s) >= 19:
        return s[:19]
    if len(s) == 10:
        return s + " 00:00:00"
    return s


def _parse_day(text: str) -> date:
    t = text.strip().replace("/", "-")
    if len(t) >= 10 and t[4] == "-":
        return date.fromisoformat(t[:10])
    if len(t) == 8 and t.isdigit():
        return date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    raise ValueError(f"非法日期: {text}")


def _iter_days(start: str, end: str) -> list[date]:
    s, e = _parse_day(start), _parse_day(end)
    if e < s:
        raise ValueError("end 必须 >= start")
    out: list[date] = []
    d = s
    while d <= e:
        out.append(d)
        d += timedelta(days=1)
    return out


def _plain_code(symbol: str) -> str:
    return symbol.split(".")[0].strip()


def _to_sina_stock(symbol: str) -> str:
    code = _plain_code(symbol)
    if code.startswith(("6", "5")):
        return f"sh{code}"
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    return f"sz{code}"


def _to_sina_index(symbol: str) -> str:
    code = _plain_code(symbol)
    if code.startswith("39"):
        return f"sz{code}"
    return f"sh{code}"


class AkshareCoreMarketSource(CoreMarketSource):
    """
    真实行情源（akshare）。

    - equity_1d   → stock_zh_a_hist（未复权）
    - adj_factor  → 未复权/前复权/后复权收盘比（qfq/hfq）
    - suspend     → stock_tfp_em（按日）
    - limit       → stock_zt_pool_em + stock_zt_pool_dtgc_em
    - index_1d    → stock_zh_index_daily（新浪）
    - corp_action → fhps 分红/送转 + 配股明细 + 复权因子变动点（P1）
    - market_rank → 本地日线排名 + 东财实时榜/人气榜（P1）
    - abnormal_move → stock_changes_em 盘口异动（P1；多为最近交易日快照）
    - limit → 涨跌停池 + 强势/炸板/昨日/次新池
    """

    source = "akshare"

    def __init__(self, *, request_pause: float = 0.12) -> None:
        self.request_pause = request_pause

    def fetch(self, request: FetchRequest) -> FetchBundle:
        ak = _require_akshare()
        dispatch = {
            "equity_1d": self._equity,
            "adj_factor": self._adj,
            "suspend": self._suspend,
            "limit": self._limit,
            "index_1d": self._index,
            "corp_action": self._corp,
            "market_rank": self._market_rank,
            "abnormal_move": self._abnormal_move,
            "board_1d": self._board_1d,
            "equity_15m": self._equity_15m,
            "equity_60m": self._equity_60m,
        }
        if request.kind not in dispatch:
            raise ValueError(f"unsupported kind: {request.kind}")
        rows = dispatch[request.kind](ak, request)
        logger.info("akshare market fetched kind=%s rows=%s", request.kind, len(rows))
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _pause(self) -> None:
        if self.request_pause > 0:
            time.sleep(self.request_pause)

    def _require_range(self, request: FetchRequest) -> tuple[str, str]:
        if not (request.start and request.end):
            raise ValueError(f"{request.kind} 必须提供 --start 与 --end")
        return request.start[:10], request.end[:10]

    def _require_symbols(self, request: FetchRequest) -> list[str]:
        symbols = [_plain_code(s) for s in request.symbols if s.strip()]
        if not symbols:
            raise ValueError(f"{request.kind} 必须提供 --symbol")
        return symbols

    def _equity(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        symbols = self._require_symbols(request)
        rows: list[dict] = []
        for symbol in symbols:
            df = self._fetch_equity_df(ak, symbol, start, end, adjust="")
            if df is None or getattr(df, "empty", True):
                logger.warning("equity_1d 空结果 symbol=%s", symbol)
                continue
            rows.extend(self._map_equity_df(df, symbol))
        if not rows:
            raise RuntimeError("equity_1d 未拉到任何 K 线")
        return rows

    def _equity_15m(self, ak: Any, request: FetchRequest) -> list[dict]:
        return self._equity_min(ak, request, period="15", freq="15m")

    def _equity_60m(self, ak: Any, request: FetchRequest) -> list[dict]:
        return self._equity_min(ak, request, period="60", freq="60m")

    def _equity_min(
        self, ak: Any, request: FetchRequest, *, period: str, freq: str
    ) -> list[dict]:
        """东财 hist_min_em 优先；失败回退新浪 minute（窗口更短）。"""
        start, end = self._require_range(request)
        symbols = self._require_symbols(request)
        start_dt = f"{start} 09:30:00"
        end_dt = f"{end} 15:00:00"
        rows: list[dict] = []
        for symbol in symbols:
            df = None
            try:
                df = call_with_retry(
                    lambda s=symbol: ak.stock_zh_a_hist_min_em(
                        symbol=s,
                        start_date=start_dt,
                        end_date=end_dt,
                        period=period,
                        adjust="",
                    ),
                    label=f"hist_min_em:{freq}:{symbol}",
                    attempts=3,
                    pause=self.request_pause,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("hist_min_em %s %s 失败: %s", freq, symbol, exc)
            if df is None or getattr(df, "empty", True):
                try:
                    df = call_with_retry(
                        lambda s=symbol: ak.stock_zh_a_minute(
                            symbol=_to_sina_stock(s),
                            period=period,
                            adjust="",
                        ),
                        label=f"sina_minute:{freq}:{symbol}",
                        attempts=2,
                        pause=self.request_pause,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("sina minute %s %s 失败: %s", freq, symbol, exc)
                    df = None
            if df is None or getattr(df, "empty", True):
                logger.warning("%s 空结果 symbol=%s", request.kind, symbol)
                continue
            mapped = self._map_min_df(df, symbol=symbol, freq=freq)
            # 按请求区间裁剪（新浪回退可能更长/更短）
            lo, hi = start_dt, end_dt
            mapped = [r for r in mapped if lo <= str(r["bar_time"]) <= hi]
            rows.extend(mapped)
        if not rows:
            raise RuntimeError(f"{request.kind} 未拉到任何分钟 K 线")
        return rows

    def _map_min_df(self, df: Any, *, symbol: str, freq: str) -> list[dict]:
        c_time = (
            col_by_keywords(df.columns, ("时间", "day", "datetime", "date"))
            or df.columns[0]
        )
        c_open = col_by_keywords(df.columns, ("开盘", "open"))
        c_close = col_by_keywords(df.columns, ("收盘", "close"))
        c_high = col_by_keywords(df.columns, ("最高", "high"))
        c_low = col_by_keywords(df.columns, ("最低", "low"))
        c_vol = col_by_keywords(df.columns, ("成交量", "volume"))
        c_amt = col_by_keywords(df.columns, ("成交额", "amount"))
        out: list[dict] = []
        for _, row in df.iterrows():
            bt = _normalize_bar_time(row[c_time])
            if not bt:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "bar_time": bt,
                    "freq": freq,
                    "open": as_float(row[c_open]) if c_open else None,
                    "high": as_float(row[c_high]) if c_high else None,
                    "low": as_float(row[c_low]) if c_low else None,
                    "close": as_float(row[c_close]) if c_close else None,
                    "volume": as_float(row[c_vol]) if c_vol else None,
                    "amount": as_float(row[c_amt]) if c_amt else None,
                    "source": self.source,
                }
            )
        return out

    def _fetch_equity_df(
        self, ak: Any, symbol: str, start: str, end: str, *, adjust: str
    ) -> Any:
        """东财 hist 优先，失败回退新浪 daily。"""
        s_ymd, e_ymd = _ymd(_parse_day(start)), _ymd(_parse_day(end))
        self._pause()
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=s_ymd,
                end_date=e_ymd,
                adjust=adjust,
            )
            if df is not None and not getattr(df, "empty", True):
                return df
        except Exception as exc:  # noqa: BLE001
            logger.warning("eastmoney hist %s adjust=%s 失败: %s", symbol, adjust, exc)

        sina_adjust = adjust  # '', qfq, hfq
        self._pause()
        df = ak.stock_zh_a_daily(
            symbol=_to_sina_stock(symbol),
            start_date=s_ymd,
            end_date=e_ymd,
            adjust=sina_adjust,
        )
        return df

    def _map_equity_df(self, df: Any, symbol: str) -> list[dict]:
        c_date = col_by_keywords(df.columns, ("日期", "date")) or df.columns[0]
        c_open = col_by_keywords(df.columns, ("开盘", "open"))
        c_close = col_by_keywords(df.columns, ("收盘", "close"))
        c_high = col_by_keywords(df.columns, ("最高", "high"))
        c_low = col_by_keywords(df.columns, ("最低", "low"))
        c_vol = col_by_keywords(df.columns, ("成交量", "volume"))
        c_amt = col_by_keywords(df.columns, ("成交额", "amount"))
        c_to = col_by_keywords(df.columns, ("换手率", "turnover"))
        out: list[dict] = []
        for _, r in df.iterrows():
            ds = as_str(r[c_date])
            if not ds:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "trade_date": ds,
                    "open": as_float(r[c_open]) if c_open is not None else None,
                    "high": as_float(r[c_high]) if c_high is not None else None,
                    "low": as_float(r[c_low]) if c_low is not None else None,
                    "close": as_float(r[c_close]) if c_close is not None else None,
                    "volume": as_float(r[c_vol]) if c_vol is not None else None,
                    "amount": as_float(r[c_amt]) if c_amt is not None else None,
                    "turnover": as_float(r[c_to]) if c_to is not None else None,
                    "source": self.source,
                }
            )
        return out

    def _adj(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        symbols = self._require_symbols(request)
        rows: list[dict] = []
        for symbol in symbols:
            closes: dict[str, dict[str, float]] = {}
            for adjust, key in (("", "raw"), ("qfq", "qfq"), ("hfq", "hfq")):
                try:
                    df = self._fetch_equity_df(ak, symbol, start, end, adjust=adjust)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("adj %s adjust=%s 失败: %s", symbol, adjust, exc)
                    continue
                if df is None or getattr(df, "empty", True):
                    continue
                c_date = col_by_keywords(df.columns, ("日期", "date")) or df.columns[0]
                c_close = col_by_keywords(df.columns, ("收盘", "close"))
                if c_close is None:
                    continue
                for _, r in df.iterrows():
                    ds = as_str(r[c_date])
                    close = as_float(r[c_close])
                    if not ds or close is None or close == 0:
                        continue
                    closes.setdefault(ds, {})[key] = close

            for ds, vals in sorted(closes.items()):
                raw = vals.get("raw")
                if raw is None or raw == 0:
                    continue
                if "qfq" in vals:
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": ds,
                            "factor_type": "qfq",
                            "factor": vals["qfq"] / raw,
                            "source": self.source,
                        }
                    )
                if "hfq" in vals:
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": ds,
                            "factor_type": "hfq",
                            "factor": vals["hfq"] / raw,
                            "source": self.source,
                        }
                    )
        if not rows:
            raise RuntimeError("adj_factor 未拉到因子")
        return rows

    def _suspend(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()
        trade_days = [d for d in _iter_days(start, end) if d.weekday() < 5]
        for i, day in enumerate(trade_days, start=1):
            ymd = _ymd(day)
            if i == 1 or i % 20 == 0 or i == len(trade_days):
                logger.info(
                    "suspend progress %s/%s day=%s rows=%s",
                    i,
                    len(trade_days),
                    day.isoformat(),
                    len(rows),
                )
            self._pause()
            try:
                df = ak.stock_tfp_em(date=ymd)
            except Exception as exc:  # noqa: BLE001
                logger.warning("suspend %s 失败: %s", ymd, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_code = col_by_keywords(df.columns, ("代码",)) or (
                df.columns[1] if df.shape[1] > 1 else df.columns[0]
            )
            c_type = col_by_keywords(df.columns, ("停牌期限", "类型"))
            c_reason = col_by_keywords(df.columns, ("停牌原因", "原因"))
            c_resume = col_by_keywords(df.columns, ("预计复牌", "复牌"))
            for _, r in df.iterrows():
                symbol = as_str(r[c_code])
                key = (symbol, day.isoformat())
                if not symbol or key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": day.isoformat(),
                        "event_type": "SUSPEND",
                        "suspend_type": as_str(r[c_type]) if c_type is not None else None,
                        "reason": as_str(r[c_reason]) if c_reason is not None else None,
                        "resume_date": as_str(r[c_resume]) if c_resume is not None else None,
                        "source": self.source,
                    }
                )
        # 允许某区间无停牌（仍 commit 空集）
        return rows

    def _limit(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        rows: list[dict] = []
        # CORE 长窗：仅 UP/DOWN；短窗（<=60 自然日）再拉强势/炸板/昨日/次新
        side_apis = [
            ("UP", "stock_zt_pool_em"),
            ("DOWN", "stock_zt_pool_dtgc_em"),
        ]
        span_days = (_parse_day(end) - _parse_day(start)).days
        if span_days <= 60:
            side_apis.extend(
                [
                    ("STRONG", "stock_zt_pool_strong_em"),
                    ("ZBGC", "stock_zt_pool_zbgc_em"),
                    ("PREVIOUS", "stock_zt_pool_previous_em"),
                    ("SUB_NEW", "stock_zt_pool_sub_new_em"),
                ]
            )
        trade_days = [d for d in _iter_days(start, end) if d.weekday() < 5]
        for i, day in enumerate(trade_days, start=1):
            ymd = _ymd(day)
            if i == 1 or i % 20 == 0 or i == len(trade_days):
                logger.info(
                    "limit progress %s/%s day=%s apis=%s rows=%s",
                    i,
                    len(trade_days),
                    day.isoformat(),
                    len(side_apis),
                    len(rows),
                )
            for event_type, api_name in side_apis:
                rows.extend(
                    self._limit_side(ak, ymd, day.isoformat(), event_type, api_name)
                )
        return rows

    def _limit_side(
        self, ak: Any, ymd: str, trade_date: str, event_type: str, api_name: str
    ) -> list[dict]:
        self._pause()
        try:
            df = getattr(ak, api_name)(date=ymd)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s %s 失败: %s", api_name, ymd, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("代码",)) or (
            df.columns[1] if df.shape[1] > 1 else df.columns[0]
        )
        c_close = col_by_keywords(df.columns, ("最新价", "收盘"))
        c_pct = col_by_keywords(df.columns, ("涨跌幅",))
        c_amt = col_by_keywords(df.columns, ("成交额", "封板资金", "成交额"))
        c_first = col_by_keywords(df.columns, ("首次封板", "首次", "入选理由"))
        c_last = col_by_keywords(df.columns, ("最后封板", "最后", "所属行业"))
        out: list[dict] = []
        for _, r in df.iterrows():
            symbol = as_str(r[c_code])
            if not symbol:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "trade_date": trade_date,
                    "event_type": event_type,
                    "close": as_float(r[c_close]) if c_close is not None else None,
                    "pct_chg": as_float(r[c_pct]) if c_pct is not None else None,
                    "amount": as_float(r[c_amt]) if c_amt is not None else None,
                    "first_time": as_str(r[c_first]) if c_first is not None else None,
                    "last_time": as_str(r[c_last]) if c_last is not None else None,
                    "source": self.source,
                }
            )
        return out

    def _index(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        indexes = [_plain_code(x) for x in (request.index_symbols or ["000300"])]
        s_day, e_day = _parse_day(start), _parse_day(end)
        rows: list[dict] = []
        for index_symbol in indexes:
            sina = _to_sina_index(index_symbol)
            self._pause()
            try:
                df = ak.stock_zh_index_daily(symbol=sina)
            except Exception as exc:  # noqa: BLE001
                logger.warning("index_1d %s 失败: %s", sina, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_date = col_by_keywords(df.columns, ("date", "日期")) or df.columns[0]
            c_open = col_by_keywords(df.columns, ("open", "开盘"))
            c_high = col_by_keywords(df.columns, ("high", "最高"))
            c_low = col_by_keywords(df.columns, ("low", "最低"))
            c_close = col_by_keywords(df.columns, ("close", "收盘"))
            c_vol = col_by_keywords(df.columns, ("volume", "成交量"))
            c_amt = col_by_keywords(df.columns, ("amount", "成交额"))
            for _, r in df.iterrows():
                ds = as_str(r[c_date])
                if not ds:
                    continue
                try:
                    d = _parse_day(ds)
                except ValueError:
                    continue
                if d < s_day or d > e_day:
                    continue
                rows.append(
                    {
                        "index_symbol": index_symbol,
                        "trade_date": d.isoformat(),
                        "open": as_float(r[c_open]) if c_open is not None else None,
                        "high": as_float(r[c_high]) if c_high is not None else None,
                        "low": as_float(r[c_low]) if c_low is not None else None,
                        "close": as_float(r[c_close]) if c_close is not None else None,
                        "volume": as_float(r[c_vol]) if c_vol is not None else None,
                        "amount": as_float(r[c_amt]) if c_amt is not None else None,
                        "source": self.source,
                    }
                )
        if not rows:
            raise RuntimeError("index_1d 未拉到数据")
        return rows

    def _corp(self, ak: Any, request: FetchRequest) -> list[dict]:
        """分红/送转/配股事件 + 复权因子变动点（仅因子变化日）。"""
        symbols = self._require_symbols(request)
        start, end = self._require_range(request)
        s_day, e_day = _parse_day(start), _parse_day(end)
        rows: list[dict] = []
        for symbol in symbols:
            rows.extend(self._corp_fhps(ak, symbol, s_day, e_day))
            rows.extend(self._corp_rights(ak, symbol, s_day, e_day))
            rows.extend(self._corp_adj_factor_change(ak, symbol, s_day, e_day))
        return rows

    def _corp_fhps(
        self, ak: Any, symbol: str, s_day: date, e_day: date
    ) -> list[dict]:
        self._pause()
        try:
            df = ak.stock_fhps_detail_em(symbol=symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("corp_action fhps %s 失败: %s", symbol, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_ex = col_by_keywords(df.columns, ("除权除息日",))
        c_reg = col_by_keywords(df.columns, ("股权登记日",))
        c_cash = col_by_keywords(df.columns, ("现金分红-现金分红比例", "现金分红比例"))
        c_cash_desc = col_by_keywords(df.columns, ("现金分红比例描述", "分红比例描述"))
        c_bonus = col_by_keywords(df.columns, ("送股比例",))
        c_transfer = col_by_keywords(df.columns, ("转股比例", "转增比例"))
        c_bonus_total = col_by_keywords(df.columns, ("送转总比例",))
        c_progress = col_by_keywords(df.columns, ("方案进度", "进度"))
        c_announce = col_by_keywords(df.columns, ("最新公告日期", "公告日期"))
        rows: list[dict] = []
        for _, r in df.iterrows():
            ex_raw = as_str(r[c_ex]) if c_ex is not None else ""
            if not ex_raw:
                continue
            try:
                ex_d = _parse_day(ex_raw)
            except ValueError:
                continue
            if ex_d < s_day or ex_d > e_day:
                continue
            cash = as_float(r[c_cash]) if c_cash is not None else None
            bonus = as_float(r[c_bonus]) if c_bonus is not None else None
            transfer = as_float(r[c_transfer]) if c_transfer is not None else None
            bonus_total = (
                as_float(r[c_bonus_total]) if c_bonus_total is not None else None
            )
            progress = as_str(r[c_progress]) if c_progress is not None else ""
            announce = as_str(r[c_announce]) if c_announce is not None else ""
            reg = as_str(r[c_reg]) if c_reg is not None else ""
            cash_desc = as_str(r[c_cash_desc]) if c_cash_desc is not None else ""
            base = {
                "announce_date": announce or None,
                "record_date": reg or None,
                "progress": progress or None,
                "cash_desc": cash_desc or None,
            }
            # 东财比例多为「每 10 股」口径
            if cash is not None and cash > 0:
                payload = {
                    **base,
                    "cash_per_10": cash,
                    "cash": round(cash / 10.0, 8),
                }
                rows.append(
                    {
                        "symbol": symbol,
                        "ex_date": ex_d.isoformat(),
                        "action_type": "DIVIDEND",
                        "raw_payload": json.dumps(payload, ensure_ascii=False),
                        "source": self.source,
                    }
                )
            if (bonus and bonus > 0) or (transfer and transfer > 0) or (
                bonus_total and bonus_total > 0
            ):
                payload = {
                    **base,
                    "bonus_ratio_per_10": bonus,
                    "transfer_ratio_per_10": transfer,
                    "bonus_total_per_10": bonus_total,
                }
                rows.append(
                    {
                        "symbol": symbol,
                        "ex_date": ex_d.isoformat(),
                        "action_type": "BONUS",
                        "raw_payload": json.dumps(payload, ensure_ascii=False),
                        "source": self.source,
                    }
                )
        return rows

    def _corp_rights(
        self, ak: Any, symbol: str, s_day: date, e_day: date
    ) -> list[dict]:
        self._pause()
        try:
            df = ak.stock_history_dividend_detail(symbol=symbol, indicator="配股")
        except Exception as exc:  # noqa: BLE001
            logger.warning("corp_action rights %s 失败: %s", symbol, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_ex = col_by_keywords(df.columns, ("除权除息日", "除权日", "配股除权日"))
        c_ratio = col_by_keywords(df.columns, ("配股比例", "配股"))
        c_price = col_by_keywords(df.columns, ("配股价格", "价格"))
        c_announce = col_by_keywords(df.columns, ("公告日期",))
        c_progress = col_by_keywords(df.columns, ("进度",))
        rows: list[dict] = []
        for _, r in df.iterrows():
            ex_raw = as_str(r[c_ex]) if c_ex is not None else ""
            if not ex_raw:
                continue
            try:
                ex_d = _parse_day(ex_raw)
            except ValueError:
                continue
            if ex_d < s_day or ex_d > e_day:
                continue
            payload = {
                "rights_ratio": as_float(r[c_ratio]) if c_ratio is not None else None,
                "rights_price": as_float(r[c_price]) if c_price is not None else None,
                "announce_date": as_str(r[c_announce]) if c_announce is not None else None,
                "progress": as_str(r[c_progress]) if c_progress is not None else None,
            }
            rows.append(
                {
                    "symbol": symbol,
                    "ex_date": ex_d.isoformat(),
                    "action_type": "RIGHTS",
                    "raw_payload": json.dumps(payload, ensure_ascii=False),
                    "source": self.source,
                }
            )
        return rows

    def _corp_adj_factor_change(
        self, ak: Any, symbol: str, s_day: date, e_day: date
    ) -> list[dict]:
        sina = _to_sina_stock(symbol)
        self._pause()
        try:
            df = ak.stock_zh_a_daily(
                symbol=sina,
                start_date="19900101",
                end_date="21000101",
                adjust="qfq-factor",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("corp_action factor %s 失败: %s", sina, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_date = col_by_keywords(df.columns, ("date", "日期")) or df.columns[0]
        c_factor = col_by_keywords(df.columns, ("qfq_factor", "factor")) or df.columns[-1]
        rows: list[dict] = []
        prev_factor: float | None = None
        # 按日期升序，便于检测变动点
        ordered = []
        for _, r in df.iterrows():
            ds = as_str(r[c_date])
            if not ds or ds.startswith("1900"):
                continue
            try:
                d = _parse_day(ds)
            except ValueError:
                continue
            factor = as_float(r[c_factor])
            if factor is None:
                continue
            ordered.append((d, factor))
        ordered.sort(key=lambda x: x[0])
        for d, factor in ordered:
            changed = prev_factor is not None and abs(factor - prev_factor) > 1e-12
            if changed and s_day <= d <= e_day:
                rows.append(
                    {
                        "symbol": symbol,
                        "ex_date": d.isoformat(),
                        "action_type": "ADJ_FACTOR_CHANGE",
                        "raw_payload": json.dumps(
                            {
                                "qfq_factor": factor,
                                "prev_qfq_factor": prev_factor,
                            },
                            ensure_ascii=False,
                        ),
                        "source": self.source,
                    }
                )
            prev_factor = factor
        return rows

    def _market_rank(self, ak: Any, request: FetchRequest) -> list[dict]:
        """涨跌幅/成交量/成交额/换手/人气排名。

        历史日优先用已入库 `raw_equity_bar_1d` 截面排序；
        当日或库内无截面时回退 `stock_zh_a_spot_em`；
        HOT 用人气榜 `stock_hot_rank_em`（仅 end/今日）。
        可选 `--symbol`/`--universe` 限制排名宇宙。
        """
        start, end = self._require_range(request)
        top_n = max(1, int(request.top_n or DEFAULT_RANK_TOP_N))
        allow = set(RANK_TYPES)
        rank_types = [t for t in (request.rank_types or list(RANK_TYPES)) if t in allow]
        if not rank_types:
            rank_types = list(RANK_TYPES)
        symbol_filter = (
            {_plain_code(s) for s in request.symbols if s.strip()}
            if request.symbols
            else None
        )
        end_day = _parse_day(end)
        today = date.today()
        rows: list[dict] = []
        for day in _iter_days(start, end):
            if day.weekday() >= 5:
                continue
            day_s = day.isoformat()
            quotes: list[dict[str, Any]] = []
            use_spot = bool(request.prefer_spot) and (
                day == end_day or day == today
            )
            if use_spot:
                quotes = self._rank_quotes_from_spot(ak, day_s, symbol_filter)
            if not quotes:
                quotes = self._rank_quotes_from_bars(day_s, symbol_filter)
            if not quotes and (day == end_day or day == today):
                quotes = self._rank_quotes_from_spot(ak, day_s, symbol_filter)
            if quotes:
                rows.extend(
                    self._emit_metric_ranks(
                        quotes, trade_date=day_s, rank_types=rank_types, top_n=top_n
                    )
                )
            if "HOT" in rank_types and (day == end_day or day == today):
                rows.extend(
                    self._hot_rank(
                        ak, trade_date=day_s, top_n=top_n, symbol_filter=symbol_filter
                    )
                )
        return rows

    def _rank_quotes_from_bars(
        self, trade_date: str, symbol_filter: set[str] | None
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT a.symbol, a.close, a.volume, a.amount, a.turnover,
                   (
                     SELECT b.close FROM raw_equity_bar_1d b
                     WHERE b.symbol = a.symbol AND b.source = a.source
                       AND b.trade_date < a.trade_date
                     ORDER BY b.trade_date DESC LIMIT 1
                   ) AS prev_close
            FROM raw_equity_bar_1d a
            WHERE a.trade_date = ? AND a.source = ?
        """
        params: list[Any] = [trade_date, self.source]
        if symbol_filter:
            placeholders = ",".join("?" for _ in symbol_filter)
            sql += f" AND a.symbol IN ({placeholders})"
            params.extend(sorted(symbol_filter))
        with get_conn() as conn:
            db_rows = conn.execute(sql, tuple(params)).fetchall()
        out: list[dict[str, Any]] = []
        for r in db_rows:
            symbol = as_str(r["symbol"])
            if not symbol:
                continue
            close = as_float(r["close"])
            prev = as_float(r["prev_close"])
            pct = None
            if close is not None and prev is not None and prev != 0:
                pct = (close / prev - 1.0) * 100.0
            out.append(
                {
                    "symbol": symbol,
                    "name": None,
                    "close": close,
                    "pct_chg": pct,
                    "volume": as_float(r["volume"]),
                    "amount": as_float(r["amount"]),
                    "turnover": as_float(r["turnover"]),
                }
            )
        return out

    def _call_with_retry(self, fn: Any, *, label: str, attempts: int = 3) -> Any:
        from shared.akshare_call import call_with_retry

        return call_with_retry(
            fn,
            label=label,
            attempts=attempts,
            pause=self.request_pause,
            backoff=0.6,
        )

    def _rank_quotes_from_spot(
        self, ak: Any, trade_date: str, symbol_filter: set[str] | None
    ) -> list[dict[str, Any]]:
        try:
            df = self._call_with_retry(
                lambda: ak.stock_zh_a_spot_em(), label="stock_zh_a_spot_em"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_rank spot %s 不可用: %s", trade_date, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("代码",)) or (
            df.columns[1] if df.shape[1] > 1 else df.columns[0]
        )
        c_name = col_by_keywords(df.columns, ("名称",))
        c_close = col_by_keywords(df.columns, ("最新价", "收盘"))
        c_pct = col_by_keywords(df.columns, ("涨跌幅",))
        c_vol = col_by_keywords(df.columns, ("成交量",))
        c_amt = col_by_keywords(df.columns, ("成交额",))
        c_turn = col_by_keywords(df.columns, ("换手率",))
        out: list[dict[str, Any]] = []
        for _, r in df.iterrows():
            symbol = as_str(r[c_code])
            if not symbol:
                continue
            if symbol_filter is not None and symbol not in symbol_filter:
                continue
            out.append(
                {
                    "symbol": symbol,
                    "name": as_str(r[c_name]) if c_name is not None else None,
                    "close": as_float(r[c_close]) if c_close is not None else None,
                    "pct_chg": as_float(r[c_pct]) if c_pct is not None else None,
                    "volume": as_float(r[c_vol]) if c_vol is not None else None,
                    "amount": as_float(r[c_amt]) if c_amt is not None else None,
                    "turnover": as_float(r[c_turn]) if c_turn is not None else None,
                }
            )
        logger.info(
            "market_rank spot trade_date=%s quotes=%s filter=%s",
            trade_date,
            len(out),
            len(symbol_filter) if symbol_filter else "ALL",
        )
        return out

    def _emit_metric_ranks(
        self,
        quotes: list[dict[str, Any]],
        *,
        trade_date: str,
        rank_types: list[str],
        top_n: int,
    ) -> list[dict]:
        specs: dict[str, tuple[str, bool]] = {
            "PCT_CHG_UP": ("pct_chg", True),
            "PCT_CHG_DOWN": ("pct_chg", False),
            "VOLUME": ("volume", True),
            "AMOUNT": ("amount", True),
            "TURNOVER": ("turnover", True),
        }
        rows: list[dict] = []
        for rank_type in rank_types:
            spec = specs.get(rank_type)
            if spec is None:
                continue
            metric_key, descending = spec
            scored = [q for q in quotes if q.get(metric_key) is not None]
            scored.sort(key=lambda q: q[metric_key], reverse=descending)
            for rank_no, q in enumerate(scored[:top_n], start=1):
                rows.append(
                    {
                        "trade_date": trade_date,
                        "rank_type": rank_type,
                        "rank_no": rank_no,
                        "symbol": q["symbol"],
                        "name": q.get("name"),
                        "metric_value": q.get(metric_key),
                        "close": q.get("close"),
                        "pct_chg": q.get("pct_chg"),
                        "volume": q.get("volume"),
                        "amount": q.get("amount"),
                        "turnover": q.get("turnover"),
                        "extra_json": None,
                        "source": self.source,
                    }
                )
        return rows

    def _hot_rank(
        self,
        ak: Any,
        *,
        trade_date: str,
        top_n: int,
        symbol_filter: set[str] | None,
    ) -> list[dict]:
        try:
            df = self._call_with_retry(
                lambda: ak.stock_hot_rank_em(), label="stock_hot_rank_em"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_rank HOT %s 失败: %s", trade_date, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("代码",)) or (
            df.columns[1] if df.shape[1] > 1 else df.columns[0]
        )
        c_name = col_by_keywords(df.columns, ("名称", "股票名称"))
        c_rank = col_by_keywords(df.columns, ("排名", "当前排名"))
        c_metric = col_by_keywords(df.columns, ("人气值", "热度", "关注"))
        rows: list[dict] = []
        seen: set[str] = set()
        for _, r in df.iterrows():
            symbol = as_str(r[c_code])
            if not symbol or symbol in seen:
                continue
            if symbol_filter is not None and symbol not in symbol_filter:
                continue
            seen.add(symbol)
            rank_no = len(rows) + 1
            if c_rank is not None:
                maybe = as_float(r[c_rank])
                if maybe is not None:
                    rank_no = int(maybe)
            metric = as_float(r[c_metric]) if c_metric is not None else float(rank_no)
            rows.append(
                {
                    "trade_date": trade_date,
                    "rank_type": "HOT",
                    "rank_no": rank_no,
                    "symbol": symbol,
                    "name": as_str(r[c_name]) if c_name is not None else None,
                    "metric_value": metric,
                    "close": None,
                    "pct_chg": None,
                    "volume": None,
                    "amount": None,
                    "turnover": None,
                    "extra_json": None,
                    "source": self.source,
                }
            )
            if len(rows) >= top_n:
                break
        return rows

    def _abnormal_move(self, ak: Any, request: FetchRequest) -> list[dict]:
        """盘口异动：东财 stock_changes_em（多为最近交易日快照）。

        trade_date 取 --end（建议填最近交易日）。可选 --change-type 过滤类型。
        """
        _, end = self._require_range(request)
        trade_date = end[:10]
        want_types = [t.strip() for t in (request.change_types or []) if t.strip()]
        if not want_types:
            want_types = list(ABNORMAL_CHANGE_TYPES)
        symbol_filter = (
            {_plain_code(s) for s in request.symbols if s.strip()}
            if request.symbols
            else None
        )
        rows: list[dict] = []
        for change_type in want_types:
            self._pause()
            try:
                df = self._call_with_retry(
                    lambda ct=change_type: ak.stock_changes_em(symbol=ct),
                    label=f"stock_changes_em:{change_type}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("abnormal_move %s 失败: %s", change_type, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_time = col_by_keywords(df.columns, ("时间",))
            c_code = col_by_keywords(df.columns, ("代码",)) or (
                df.columns[1] if df.shape[1] > 1 else df.columns[0]
            )
            c_name = col_by_keywords(df.columns, ("名称",))
            c_board = col_by_keywords(df.columns, ("板块",))
            c_info = col_by_keywords(df.columns, ("相关信息", "信息"))
            for i, r in df.iterrows():
                symbol = as_str(r[c_code])
                if not symbol:
                    continue
                if symbol_filter is not None and symbol not in symbol_filter:
                    continue
                event_time = as_str(r[c_time]) if c_time is not None else ""
                info = as_str(r[c_info]) if c_info is not None else ""
                event_id = f"{symbol}|{trade_date}|{change_type}|{event_time}|{i}"
                extra = None
                if c_board is not None:
                    board = as_str(r[c_board])
                    if board:
                        extra = json.dumps({"board": board}, ensure_ascii=False)
                rows.append(
                    {
                        "trade_date": trade_date,
                        "event_time": event_time or None,
                        "symbol": symbol,
                        "name": as_str(r[c_name]) if c_name is not None else None,
                        "change_type": change_type,
                        "related_info": info or None,
                        "extra_json": extra,
                        "source_event_id": event_id[:240],
                        "source": self.source,
                    }
                )
        return rows

    def _board_1d(self, ak: Any, request: FetchRequest) -> list[dict]:
        """行业/概念板块日线：stock_board_*_hist_em。"""
        start, end = self._require_range(request)
        start_ymd = start.replace("-", "")
        end_ymd = end.replace("-", "")
        types = [t.upper() for t in (request.board_types or [])] or ["INDUSTRY"]
        name_filter = {n.strip() for n in (request.board_names or []) if n.strip()}
        rows: list[dict] = []
        for board_type in types:
            if board_type == "INDUSTRY":
                name_fn = ak.stock_board_industry_name_em
                hist_fn = ak.stock_board_industry_hist_em
                period = "日k"
            elif board_type == "CONCEPT":
                name_fn = ak.stock_board_concept_name_em
                hist_fn = ak.stock_board_concept_hist_em
                period = "daily"
            else:
                logger.warning("未知 board_type=%s，跳过", board_type)
                continue
            try:
                listing = self._call_with_retry(
                    name_fn, label=f"board_name_{board_type.lower()}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("board_1d 列表失败 type=%s: %s", board_type, exc)
                continue
            if listing is None or getattr(listing, "empty", True):
                continue
            c_name = col_by_keywords(listing.columns, ("板块名称", "名称")) or listing.columns[1]
            c_code = col_by_keywords(listing.columns, ("板块代码", "代码"))
            boards: list[tuple[str, str | None]] = []
            for _, r in listing.iterrows():
                name = as_str(r[c_name])
                if not name:
                    continue
                if name_filter and name not in name_filter:
                    continue
                code = as_str(r[c_code]) if c_code is not None else None
                boards.append((name, code or None))
            for i, (name, code) in enumerate(boards, start=1):
                if i == 1 or i % 20 == 0 or i == len(boards):
                    logger.info(
                        "board_1d progress type=%s %s/%s name=%s",
                        board_type,
                        i,
                        len(boards),
                        name,
                    )
                try:
                    if board_type == "INDUSTRY":
                        df = self._call_with_retry(
                            lambda n=name: hist_fn(
                                symbol=n,
                                start_date=start_ymd,
                                end_date=end_ymd,
                                period=period,
                                adjust="",
                            ),
                            label=f"board_hist_{board_type}:{name}",
                        )
                    else:
                        df = self._call_with_retry(
                            lambda n=name: hist_fn(
                                symbol=n,
                                period=period,
                                start_date=start_ymd,
                                end_date=end_ymd,
                                adjust="",
                            ),
                            label=f"board_hist_{board_type}:{name}",
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("board_1d hist 失败 %s/%s: %s", board_type, name, exc)
                    continue
                if df is None or getattr(df, "empty", True):
                    continue
                c_date = col_by_keywords(df.columns, ("日期",)) or df.columns[0]
                c_open = col_by_keywords(df.columns, ("开盘",))
                c_high = col_by_keywords(df.columns, ("最高",))
                c_low = col_by_keywords(df.columns, ("最低",))
                c_close = col_by_keywords(df.columns, ("收盘",))
                c_vol = col_by_keywords(df.columns, ("成交量",))
                c_amt = col_by_keywords(df.columns, ("成交额",))
                c_pct = col_by_keywords(df.columns, ("涨跌幅",))
                c_to = col_by_keywords(df.columns, ("换手率",))
                for _, r in df.iterrows():
                    trade_date = as_str(r[c_date])[:10]
                    if not trade_date or trade_date < start or trade_date > end:
                        continue
                    rows.append(
                        {
                            "board_type": board_type,
                            "board_code": code,
                            "board_name": name,
                            "trade_date": trade_date,
                            "open": as_float(r[c_open]) if c_open is not None else None,
                            "high": as_float(r[c_high]) if c_high is not None else None,
                            "low": as_float(r[c_low]) if c_low is not None else None,
                            "close": as_float(r[c_close]) if c_close is not None else None,
                            "volume": as_float(r[c_vol]) if c_vol is not None else None,
                            "amount": as_float(r[c_amt]) if c_amt is not None else None,
                            "pct_chg": as_float(r[c_pct]) if c_pct is not None else None,
                            "turnover": as_float(r[c_to]) if c_to is not None else None,
                            "source": self.source,
                        }
                    )
        return rows
