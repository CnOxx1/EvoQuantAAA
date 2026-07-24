from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any

from data_ingest.core_market.models import FetchBundle, FetchRequest
from data_ingest.core_market.sources.base import CoreMarketSource
from data_ingest.core_ref.sources._parse import as_float, as_str, col_by_keywords

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
        for day in _iter_days(start, end):
            # 停牌接口仅对交易日有意义；非交易日接口也可能返回空/报错
            if day.weekday() >= 5:
                continue
            ymd = _ymd(day)
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
        for day in _iter_days(start, end):
            if day.weekday() >= 5:
                continue
            ymd = _ymd(day)
            rows.extend(self._limit_side(ak, ymd, day.isoformat(), "UP", "stock_zt_pool_em"))
            rows.extend(
                self._limit_side(ak, ymd, day.isoformat(), "DOWN", "stock_zt_pool_dtgc_em")
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
        c_first = col_by_keywords(df.columns, ("首次封板", "首次"))
        c_last = col_by_keywords(df.columns, ("最后封板", "最后"))
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
