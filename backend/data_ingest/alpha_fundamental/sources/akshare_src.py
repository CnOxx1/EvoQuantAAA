from __future__ import annotations

import logging
import math
import re
import time
from datetime import date
from typing import Any

from data_ingest.alpha_fundamental.models import (
    ALL_STATEMENT_TYPES,
    FetchBundle,
    FetchRequest,
)
from data_ingest.alpha_fundamental.sources.base import FundamentalSource
from data_ingest.ingest_common.parse import as_float, as_str, col_by_keywords

logger = logging.getLogger(__name__)

_META_COLS = {
    "SECUCODE",
    "SECURITY_CODE",
    "SECURITY_NAME_ABBR",
    "ORG_CODE",
    "ORG_TYPE",
    "REPORT_DATE",
    "REPORT_TYPE",
    "REPORT_DATE_NAME",
    "SECURITY_TYPE_CODE",
    "NOTICE_DATE",
    "UPDATE_DATE",
    "CURRENCY",
    "OPINION_TYPE",
    "OSOPINION_TYPE",
}

def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 akshare，请执行: pip install -r requirements.txt"
        ) from exc
    return ak


def _plain(symbol: str) -> str:
    s = symbol.strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    if s.startswith(("SH", "SZ", "BJ")) and len(s) >= 8:
        s = s[2:]
    return s.split(".")[0]


def _to_em_prefix(symbol: str) -> str:
    code = _plain(symbol)
    if code.startswith("6"):
        return f"SH{code}"
    if code.startswith(("4", "8", "9")):
        return f"BJ{code}"
    return f"SZ{code}"


def _to_em_dot(symbol: str) -> str:
    code = _plain(symbol)
    if code.startswith("6"):
        return f"{code}.SH"
    if code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _parse_day(text: str | None) -> date | None:
    if not text:
        return None
    t = as_str(text)
    if not t:
        return None
    if len(t) >= 10 and t[4] == "-":
        return date.fromisoformat(t[:10])
    if len(t) == 8 and t.isdigit():
        return date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    return None


def _finite(value: float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class AkshareFundamentalSource(FundamentalSource):
    """
    真实基本面源（akshare / 东财）。

    - statement  → profit/balance/cashflow_sheet_by_report_em（长表科目）
    - indicator  → stock_financial_analysis_indicator_em（回退新浪指标）
    - consensus  → stock_profit_forecast_em（全市场快照，asof=拉取日）
    - valuation  → stock_value_em（日频 PE/PB/市值）
    - holder     → stock_zh_a_gdhs_detail_em（股东户数）
    """

    source = "akshare"

    def __init__(
        self,
        *,
        request_pause: float = 0.15,
        max_periods: int = 8,
        skip_yoy: bool = True,
    ) -> None:
        self.request_pause = request_pause
        self.max_periods = max_periods
        self.skip_yoy = skip_yoy

    def fetch(self, request: FetchRequest) -> FetchBundle:
        ak = _require_akshare()
        if request.kind == "statement":
            rows = self._statement(ak, request)
        elif request.kind == "indicator":
            rows = self._indicator(ak, request)
        elif request.kind == "consensus":
            rows = self._consensus(ak, request)
        elif request.kind == "valuation":
            rows = self._valuation(ak, request)
        elif request.kind == "holder":
            rows = self._holder(ak, request)
        else:
            raise ValueError(f"unsupported kind: {request.kind}")
        logger.info(
            "akshare fundamental fetched kind=%s rows=%s", request.kind, len(rows)
        )
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _pause(self) -> None:
        if self.request_pause > 0:
            time.sleep(self.request_pause)

    def _call(self, fn: Any, *, label: str) -> Any:
        from shared.akshare_call import call_with_retry

        return call_with_retry(
            fn, label=label, attempts=3, pause=self.request_pause, backoff=0.6
        )

    def _require_symbols(self, request: FetchRequest) -> list[str]:
        symbols = [_plain(s) for s in request.symbols if s.strip()]
        if not symbols:
            raise ValueError(f"{request.kind} 必须提供 --symbol")
        return symbols

    def _in_range(self, day: date | None, start: str | None, end: str | None) -> bool:
        if day is None:
            return False
        if start:
            s = _parse_day(start)
            if s and day < s:
                return False
        if end:
            e = _parse_day(end)
            if e and day > e:
                return False
        return True

    def _statement(self, ak: Any, request: FetchRequest) -> list[dict]:
        symbols = self._require_symbols(request)
        types = [
            t.upper()
            for t in (request.statement_types or list(ALL_STATEMENT_TYPES))
            if t.upper() in ALL_STATEMENT_TYPES
        ]
        if not types:
            types = list(ALL_STATEMENT_TYPES)

        api_map = {
            "INCOME": ak.stock_profit_sheet_by_report_em,
            "BALANCE": ak.stock_balance_sheet_by_report_em,
            "CASHFLOW": ak.stock_cash_flow_sheet_by_report_em,
        }
        rows: list[dict] = []
        for symbol in symbols:
            em_sym = _to_em_prefix(symbol)
            for st in types:
                self._pause()
                try:
                    df = api_map[st](symbol=em_sym)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("statement %s %s 失败: %s", symbol, st, exc)
                    continue
                if df is None or getattr(df, "empty", True):
                    continue
                rows.extend(
                    self._melt_statement_df(
                        df, symbol=symbol, statement_type=st, request=request
                    )
                )
        if not rows:
            raise RuntimeError("statement 未拉到任何科目")
        return rows

    def _melt_statement_df(
        self, df: Any, *, symbol: str, statement_type: str, request: FetchRequest
    ) -> list[dict]:
        c_period = col_by_keywords(df.columns, ("REPORT_DATE", "报告期"))
        c_notice = col_by_keywords(df.columns, ("NOTICE_DATE", "公告日期"))
        c_rtype = col_by_keywords(df.columns, ("REPORT_TYPE", "报告类型"))
        c_ccy = col_by_keywords(df.columns, ("CURRENCY", "币种"))
        if c_period is None:
            raise RuntimeError(f"{statement_type} 缺少 REPORT_DATE")

        # 按报告期倒序，限制期数
        work = df.copy()
        work["_period"] = work[c_period].map(lambda x: as_str(x)[:10])
        work = work[work["_period"] != ""]
        if request.start or request.end:
            # 优先按公告日过滤；无公告日则按报告期
            def keep(row: Any) -> bool:
                notice = (
                    _parse_day(as_str(row[c_notice])) if c_notice is not None else None
                )
                period = _parse_day(row["_period"])
                if notice is not None:
                    return self._in_range(notice, request.start, request.end)
                return self._in_range(period, request.start, request.end)

            work = work[work.apply(keep, axis=1)]
        periods = sorted(work["_period"].unique(), reverse=True)[: self.max_periods]
        work = work[work["_period"].isin(periods)]

        item_cols = []
        for c in work.columns:
            cs = str(c)
            if cs in _META_COLS or cs == "_period":
                continue
            if self.skip_yoy and cs.endswith("_YOY"):
                continue
            item_cols.append(c)

        out: list[dict] = []
        for _, r in work.iterrows():
            report_period = as_str(r["_period"])[:10]
            announce = as_str(r[c_notice])[:10] if c_notice is not None else ""
            if not announce:
                announce = report_period
            report_type = as_str(r[c_rtype]) if c_rtype is not None else None
            currency = as_str(r[c_ccy]) if c_ccy is not None else "CNY"
            for c in item_cols:
                val = _finite(as_float(r[c]))
                if val is None:
                    continue
                out.append(
                    {
                        "symbol": symbol,
                        "statement_type": statement_type,
                        "report_period": report_period,
                        "announce_date": announce,
                        "item_code": str(c),
                        "item_value": val,
                        "currency": currency or "CNY",
                        "report_type": report_type,
                        "source": self.source,
                    }
                )
        return out

    def _indicator(self, ak: Any, request: FetchRequest) -> list[dict]:
        symbols = self._require_symbols(request)
        rows: list[dict] = []
        for symbol in symbols:
            df = None
            self._pause()
            try:
                df = ak.stock_financial_analysis_indicator_em(
                    symbol=_to_em_dot(symbol), indicator="按报告期"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("indicator_em %s 失败: %s，回退新浪", symbol, exc)
            if df is None or getattr(df, "empty", True):
                self._pause()
                start_year = (request.start or "2018")[:4]
                try:
                    df = ak.stock_financial_analysis_indicator(
                        symbol=symbol, start_year=start_year
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("indicator sina %s 失败: %s", symbol, exc)
                    continue
                rows.extend(self._melt_indicator_sina(df, symbol, request))
            else:
                rows.extend(self._melt_indicator_em(df, symbol, request))
        if not rows:
            raise RuntimeError("indicator 未拉到数据")
        return rows

    def _melt_indicator_em(
        self, df: Any, symbol: str, request: FetchRequest
    ) -> list[dict]:
        c_period = col_by_keywords(df.columns, ("REPORT_DATE", "报告期"))
        c_notice = col_by_keywords(df.columns, ("NOTICE_DATE", "公告日期"))
        if c_period is None:
            return []
        work = df.copy()
        work["_period"] = work[c_period].map(lambda x: as_str(x)[:10])
        if request.start or request.end:
            def keep(row: Any) -> bool:
                notice = (
                    _parse_day(as_str(row[c_notice])) if c_notice is not None else None
                )
                period = _parse_day(row["_period"])
                if notice is not None:
                    return self._in_range(notice, request.start, request.end)
                return self._in_range(period, request.start, request.end)

            work = work[work.apply(keep, axis=1)]
        periods = sorted(work["_period"].unique(), reverse=True)[: self.max_periods]
        work = work[work["_period"].isin(periods)]
        item_cols = [
            c
            for c in work.columns
            if str(c) not in _META_COLS
            and str(c) != "_period"
            and not (self.skip_yoy and str(c).endswith("_YOY"))
        ]
        out: list[dict] = []
        for _, r in work.iterrows():
            period = as_str(r["_period"])[:10]
            announce = as_str(r[c_notice])[:10] if c_notice is not None else None
            for c in item_cols:
                val = _finite(as_float(r[c]))
                if val is None:
                    continue
                out.append(
                    {
                        "symbol": symbol,
                        "report_period": period,
                        "announce_date": announce or None,
                        "indicator_code": str(c),
                        "indicator_value": val,
                        "source": self.source,
                    }
                )
        return out

    def _melt_indicator_sina(
        self, df: Any, symbol: str, request: FetchRequest
    ) -> list[dict]:
        c_period = col_by_keywords(df.columns, ("日期", "date")) or df.columns[0]
        work = df.copy()
        work["_period"] = work[c_period].map(lambda x: as_str(x)[:10])
        if request.start or request.end:
            work = work[
                work["_period"].map(
                    lambda p: self._in_range(_parse_day(p), request.start, request.end)
                )
            ]
        periods = sorted(work["_period"].unique(), reverse=True)[: self.max_periods]
        work = work[work["_period"].isin(periods)]
        out: list[dict] = []
        for _, r in work.iterrows():
            period = as_str(r["_period"])[:10]
            for c in work.columns:
                if str(c) in {str(c_period), "_period"}:
                    continue
                val = _finite(as_float(r[c]))
                if val is None:
                    continue
                out.append(
                    {
                        "symbol": symbol,
                        "report_period": period,
                        "announce_date": None,
                        "indicator_code": str(c),
                        "indicator_value": val,
                        "source": self.source,
                    }
                )
        return out

    def _consensus(self, ak: Any, request: FetchRequest) -> list[dict]:
        asof = (request.end or date.today().isoformat())[:10]
        version = asof
        want = {_plain(s) for s in request.symbols} if request.symbols else None

        self._pause()
        try:
            df = ak.stock_profit_forecast_em()
        except Exception as exc:  # noqa: BLE001
            logger.warning("profit_forecast_em 失败，回退同花顺逐票: %s", exc)
            return self._consensus_ths(ak, request, asof=asof, version=version)

        if df is None or getattr(df, "empty", True):
            return self._consensus_ths(ak, request, asof=asof, version=version)

        c_code = col_by_keywords(df.columns, ("代码", "code")) or (
            df.columns[1] if df.shape[1] > 1 else df.columns[0]
        )
        rows: list[dict] = []
        for _, r in df.iterrows():
            symbol = as_str(r[c_code])
            if not symbol:
                continue
            if want is not None and symbol not in want:
                continue
            for c in df.columns:
                cs = str(c)
                year = None
                m = re.search(r"(20\d{2})", cs)
                if m and ("每股收益" in cs or "EPS" in cs.upper() or "预测" in cs):
                    year = m.group(1)
                if year is None:
                    continue
                val = _finite(as_float(r[c]))
                if val is None:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "asof_date": asof,
                        "metric": "EPS",
                        "period_year": year,
                        "value": val,
                        "version": version,
                        "source": self.source,
                    }
                )
            # 评级家数
            for c in df.columns:
                cs = str(c)
                if "评级" in cs and "家" in cs:
                    val = _finite(as_float(r[c]))
                    if val is None:
                        continue
                    metric = "RATING_COUNT"
                    if "买入" in cs:
                        metric = "RATING_BUY"
                    elif "增持" in cs:
                        metric = "RATING_OVERWEIGHT"
                    elif "中性" in cs:
                        metric = "RATING_NEUTRAL"
                    elif "减持" in cs:
                        metric = "RATING_UNDERWEIGHT"
                    elif "卖出" in cs:
                        metric = "RATING_SELL"
                    rows.append(
                        {
                            "symbol": symbol,
                            "asof_date": asof,
                            "metric": metric,
                            "period_year": "NA",
                            "value": val,
                            "version": version,
                            "source": self.source,
                        }
                    )

        if not rows and want:
            # 全表过滤为空时再试同花顺
            return self._consensus_ths(ak, request, asof=asof, version=version)
        if not rows:
            raise RuntimeError("consensus 未拉到预期数据")
        return rows

    def _consensus_ths(
        self, ak: Any, request: FetchRequest, *, asof: str, version: str
    ) -> list[dict]:
        symbols = self._require_symbols(request)
        rows: list[dict] = []
        for symbol in symbols:
            self._pause()
            try:
                df = ak.stock_profit_forecast_ths(
                    symbol=symbol, indicator="预测年报每股收益"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("profit_forecast_ths %s 失败: %s", symbol, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_year = col_by_keywords(df.columns, ("年度", "year")) or df.columns[0]
            c_avg = col_by_keywords(df.columns, ("均值", "平均"))
            if c_avg is None and df.shape[1] > 3:
                c_avg = df.columns[3]
            for _, r in df.iterrows():
                year = as_str(r[c_year])[:4]
                val = _finite(as_float(r[c_avg])) if c_avg is not None else None
                if not year or val is None:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "asof_date": asof,
                        "metric": "EPS",
                        "period_year": year,
                        "value": val,
                        "version": version,
                        "source": self.source,
                    }
                )
        if not rows:
            raise RuntimeError("consensus 未拉到预期数据")
        return rows

    def _valuation(self, ak: Any, request: FetchRequest) -> list[dict]:
        """日频估值：stock_value_em（东财）；按 start/end 过滤。"""
        symbols = self._require_symbols(request)
        if not (request.start and request.end):
            raise ValueError("valuation 必须提供 --start 与 --end")
        rows: list[dict] = []
        for symbol in symbols:
            try:
                df = self._call(
                    lambda s=symbol: ak.stock_value_em(symbol=s),
                    label=f"stock_value_em:{symbol}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("valuation %s 失败: %s", symbol, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_date = col_by_keywords(df.columns, ("数据日期", "日期")) or df.columns[0]
            c_close = col_by_keywords(df.columns, ("当日收盘价", "收盘"))
            c_pe = col_by_keywords(df.columns, ("PE(TTM)", "市盈率"))
            c_pe_s = col_by_keywords(df.columns, ("PE(静)",))
            c_pb = col_by_keywords(df.columns, ("市净率", "PB"))
            c_ps = col_by_keywords(df.columns, ("市销率", "PS"))
            c_pcf = col_by_keywords(df.columns, ("市现率", "PCF"))
            c_peg = col_by_keywords(df.columns, ("PEG",))
            c_tmv = col_by_keywords(df.columns, ("总市值",))
            c_fmv = col_by_keywords(df.columns, ("流通市值",))
            c_ts = col_by_keywords(df.columns, ("总股本",))
            c_fs = col_by_keywords(df.columns, ("流通股本",))
            for _, r in df.iterrows():
                day = _parse_day(r[c_date])
                if not self._in_range(day, request.start, request.end):
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": day.isoformat() if day else as_str(r[c_date])[:10],
                        "close": _finite(as_float(r[c_close])) if c_close is not None else None,
                        "pe_ttm": _finite(as_float(r[c_pe])) if c_pe is not None else None,
                        "pe_static": _finite(as_float(r[c_pe_s])) if c_pe_s is not None else None,
                        "pb": _finite(as_float(r[c_pb])) if c_pb is not None else None,
                        "ps_ttm": _finite(as_float(r[c_ps])) if c_ps is not None else None,
                        "pcf_ttm": _finite(as_float(r[c_pcf])) if c_pcf is not None else None,
                        "peg": _finite(as_float(r[c_peg])) if c_peg is not None else None,
                        "total_mv": _finite(as_float(r[c_tmv])) if c_tmv is not None else None,
                        "float_mv": _finite(as_float(r[c_fmv])) if c_fmv is not None else None,
                        "total_shares": _finite(as_float(r[c_ts])) if c_ts is not None else None,
                        "float_shares": _finite(as_float(r[c_fs])) if c_fs is not None else None,
                        "source": self.source,
                    }
                )
        return rows

    def _holder(self, ak: Any, request: FetchRequest) -> list[dict]:
        """股东户数：stock_zh_a_gdhs_detail_em。"""
        symbols = self._require_symbols(request)
        rows: list[dict] = []
        for symbol in symbols:
            try:
                df = self._call(
                    lambda s=symbol: ak.stock_zh_a_gdhs_detail_em(symbol=s),
                    label=f"gdhs_detail:{symbol}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("holder %s 失败: %s", symbol, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_asof = col_by_keywords(df.columns, ("股东户数统计截止日", "截止日"))
            c_ann = col_by_keywords(df.columns, ("股东户数公告日期", "公告日期"))
            c_cnt = col_by_keywords(df.columns, ("股东户数-本次", "本次"))
            c_prev = col_by_keywords(df.columns, ("股东户数-上次", "上次"))
            c_chg = col_by_keywords(df.columns, ("股东户数-增减",))
            c_pct = col_by_keywords(df.columns, ("股东户数-增减比例", "增减比例"))
            c_avg_mv = col_by_keywords(df.columns, ("户均持股市值",))
            c_avg_sh = col_by_keywords(df.columns, ("户均持股数量",))
            c_tmv = col_by_keywords(df.columns, ("总市值",))
            c_ts = col_by_keywords(df.columns, ("总股本",))
            if c_asof is None:
                c_asof = df.columns[0]
            for _, r in df.iterrows():
                day = _parse_day(r[c_asof])
                if request.start or request.end:
                    if not self._in_range(day, request.start, request.end):
                        continue
                asof = day.isoformat() if day else as_str(r[c_asof])[:10]
                if not asof:
                    continue
                ann = None
                if c_ann is not None:
                    ad = _parse_day(r[c_ann])
                    ann = ad.isoformat() if ad else as_str(r[c_ann])[:10] or None
                rows.append(
                    {
                        "symbol": symbol,
                        "asof_date": asof,
                        "announce_date": ann,
                        "holder_count": _finite(as_float(r[c_cnt])) if c_cnt is not None else None,
                        "holder_count_prev": _finite(as_float(r[c_prev])) if c_prev is not None else None,
                        "holder_change": _finite(as_float(r[c_chg])) if c_chg is not None else None,
                        "holder_change_pct": _finite(as_float(r[c_pct])) if c_pct is not None else None,
                        "avg_market_cap": _finite(as_float(r[c_avg_mv])) if c_avg_mv is not None else None,
                        "avg_shares": _finite(as_float(r[c_avg_sh])) if c_avg_sh is not None else None,
                        "total_mv": _finite(as_float(r[c_tmv])) if c_tmv is not None else None,
                        "total_shares": _finite(as_float(r[c_ts])) if c_ts is not None else None,
                        "source": self.source,
                    }
                )
        return rows
