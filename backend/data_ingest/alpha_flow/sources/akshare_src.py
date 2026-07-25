from __future__ import annotations

import json
import logging
import math
import re
import time
from datetime import date, timedelta
from typing import Any

from data_ingest.alpha_flow.models import FetchBundle, FetchRequest
from data_ingest.alpha_flow.sources.base import FlowSource
from data_ingest.core_ref.sources._parse import as_float, as_str, col_by_keywords

logger = logging.getLogger(__name__)

_YI_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*亿")
_WAN_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*万")


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


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _finite(v: float | None) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return float(v)


def _parse_amount_cell(value: Any) -> float | None:
    """解析数值或『1.2亿』『300万』。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _finite(float(value))
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"--", "nan", "None"}:
        return None
    m = _YI_RE.search(text)
    if m:
        return float(m.group(1)) * 1e8
    m = _WAN_RE.search(text)
    if m:
        return float(m.group(1)) * 1e4
    return _finite(as_float(text))


def _market_of(code: str) -> str:
    if code.startswith(("6", "5")):
        return "sh"
    if code.startswith(("4", "8", "9")):
        return "bj"
    return "sz"


class AkshareFlowSource(FlowSource):
    """
    真实资金源（akshare）。

    - northbound   → stock_hsgt_hist_em（北向/沪/深）
    - stock_flow   → stock_individual_fund_flow（回退 hsgt 个股增持）
    - margin       → SSE/SZSE 市场汇总 + 明细（stock_margin_*_sse / *_szse）
    - dragon_tiger → stock_lhb_detail_em
    - dragon_tiger_seat → stock_lhb_hyyyb_em（每日活跃营业部）
    - block_trade  → stock_dzjy_mrmx
    """

    source = "akshare"

    def __init__(self, *, request_pause: float = 0.12, retries: int = 2) -> None:
        self.request_pause = request_pause
        self.retries = retries

    def fetch(self, request: FetchRequest) -> FetchBundle:
        ak = _require_akshare()
        dispatch = {
            "northbound": self._northbound,
            "stock_flow": self._stock_flow,
            "margin": self._margin,
            "dragon_tiger": self._dragon,
            "dragon_tiger_seat": self._dragon_seat,
            "block_trade": self._block,
        }
        if request.kind not in dispatch:
            raise ValueError(f"unsupported kind: {request.kind}")
        rows = dispatch[request.kind](ak, request)
        logger.info("akshare flow fetched kind=%s rows=%s", request.kind, len(rows))
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _pause(self) -> None:
        if self.request_pause > 0:
            time.sleep(self.request_pause)

    def _require_range(self, request: FetchRequest) -> tuple[date, date]:
        if not (request.start and request.end):
            raise ValueError(f"{request.kind} 必须提供 --start 与 --end")
        s, e = _parse_day(request.start), _parse_day(request.end)
        if not s or not e or e < s:
            raise ValueError("非法日期区间")
        return s, e

    def _in_range(self, day: date | None, start: date, end: date) -> bool:
        return day is not None and start <= day <= end

    def _call_with_retry(self, fn: Any, **kwargs: Any) -> Any:
        from shared.akshare_call import call_with_retry

        label = getattr(fn, "__name__", "akshare_call")
        return call_with_retry(
            lambda: fn(**kwargs),
            label=label,
            attempts=self.retries + 1,
            pause=self.request_pause,
            backoff=0.5,
        )

    def _northbound(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        mapping = (
            ("北向资金", "NORTHBOUND"),
            ("沪股通", "NORTHBOUND_SH"),
            ("深股通", "NORTHBOUND_SZ"),
        )
        rows: list[dict] = []
        for symbol_name, flow_type in mapping:
            try:
                df = self._call_with_retry(ak.stock_hsgt_hist_em, symbol=symbol_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("northbound %s 失败: %s", symbol_name, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_date = col_by_keywords(df.columns, ("日期", "date")) or df.columns[0]
            c_net = col_by_keywords(df.columns, ("净买", "净流入"))
            c_buy = col_by_keywords(df.columns, ("买入成交",))
            c_sell = col_by_keywords(df.columns, ("卖出成交",))
            # 列序回退：日期, 净买, 买入, 卖出
            if c_net is None and df.shape[1] > 1:
                c_net = df.columns[1]
            if c_buy is None and df.shape[1] > 2:
                c_buy = df.columns[2]
            if c_sell is None and df.shape[1] > 3:
                c_sell = df.columns[3]
            parsed: list[dict] = []
            for _, r in df.iterrows():
                day = _parse_day(as_str(r[c_date]))
                if day is None or day > end:
                    continue
                net = _finite(as_float(r[c_net])) if c_net is not None else None
                buy = _finite(as_float(r[c_buy])) if c_buy is not None else None
                sell = _finite(as_float(r[c_sell])) if c_sell is not None else None
                # 东财北向近年部分字段停更；无核心值则跳过
                if net is None and buy is None and sell is None:
                    continue
                # 接口单位多为亿元 → 转为元
                parsed.append(
                    {
                        "scope": "MARKET",
                        "trade_date": day.isoformat(),
                        "flow_type": flow_type,
                        "net_amount": None if net is None else net * 1e8,
                        "buy_amount": None if buy is None else buy * 1e8,
                        "sell_amount": None if sell is None else sell * 1e8,
                        "extra_json": json.dumps(
                            {"channel": symbol_name}, ensure_ascii=False
                        ),
                        "source": self.source,
                        "_day": day,
                    }
                )
            in_range = [r for r in parsed if start <= r["_day"] <= end]
            if not in_range and parsed:
                # 字段停更时回退到 end 之前最近若干有效交易日
                lookback = max(5, (end - start).days + 5)
                in_range = sorted(parsed, key=lambda x: x["_day"])[-lookback:]
                logger.warning(
                    "northbound %s 请求区间无有效值，回退最近 %s 个有效交易日",
                    symbol_name,
                    len(in_range),
                )
            for r in in_range:
                r.pop("_day", None)
                rows.append(r)

        # 仍无数据时，补当日 summary
        if not rows:
            try:
                self._pause()
                summary = ak.stock_hsgt_fund_flow_summary_em()
                today = date.today()
                if start <= today <= end and summary is not None and not summary.empty:
                    c_date = col_by_keywords(summary.columns, ("交易日", "日期")) or summary.columns[0]
                    c_name = col_by_keywords(summary.columns, ("板块", "名称"))
                    c_net = col_by_keywords(summary.columns, ("成交净买", "净买"))
                    for _, r in summary.iterrows():
                        name = as_str(r[c_name]) if c_name is not None else ""
                        ft = {
                            "沪股通": "NORTHBOUND_SH",
                            "深股通": "NORTHBOUND_SZ",
                        }.get(name)
                        if not ft:
                            continue
                        day = _parse_day(as_str(r[c_date])) or today
                        net = _parse_amount_cell(r[c_net]) if c_net is not None else None
                        rows.append(
                            {
                                "scope": "MARKET",
                                "trade_date": day.isoformat(),
                                "flow_type": ft,
                                "net_amount": net,
                                "buy_amount": None,
                                "sell_amount": None,
                                "extra_json": json.dumps(
                                    {"channel": name, "from": "summary"}, ensure_ascii=False
                                ),
                                "source": self.source,
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("northbound summary 失败: %s", exc)

        if not rows:
            raise RuntimeError(
                "northbound 未拉到有效净买数据（东财北向历史字段可能停更，请扩大历史区间或稍后重试）"
            )
        return rows

    def _stock_flow(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        symbols = [_plain(s) for s in request.symbols if s.strip()]
        if not symbols:
            raise ValueError("stock_flow 必须提供 --symbol")
        rows: list[dict] = []
        for symbol in symbols:
            got = self._stock_flow_individual(ak, symbol, start, end)
            if got:
                rows.extend(got)
                continue
            # 回退：北向个股增持资金（可得历史）
            got = self._stock_flow_hsgt(ak, symbol, start, end)
            rows.extend(got)
        if not rows:
            raise RuntimeError("stock_flow 未拉到数据")
        return rows

    def _stock_flow_individual(
        self, ak: Any, symbol: str, start: date, end: date
    ) -> list[dict]:
        try:
            df = self._call_with_retry(
                ak.stock_individual_fund_flow,
                stock=symbol,
                market=_market_of(symbol),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("individual_fund_flow %s 失败: %s", symbol, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_date = col_by_keywords(df.columns, ("日期", "date")) or df.columns[0]
        c_net = col_by_keywords(df.columns, ("主力净流入", "净流入"))
        c_buy = col_by_keywords(df.columns, ("主力流入", "超大单流入"))
        c_sell = col_by_keywords(df.columns, ("主力流出", "超大单流出"))
        out: list[dict] = []
        for _, r in df.iterrows():
            day = _parse_day(as_str(r[c_date]))
            if not self._in_range(day, start, end):
                continue
            out.append(
                {
                    "scope": symbol,
                    "trade_date": day.isoformat(),
                    "flow_type": "STOCK_FLOW",
                    "net_amount": _parse_amount_cell(r[c_net]) if c_net is not None else None,
                    "buy_amount": _parse_amount_cell(r[c_buy]) if c_buy is not None else None,
                    "sell_amount": _parse_amount_cell(r[c_sell]) if c_sell is not None else None,
                    "extra_json": None,
                    "source": self.source,
                }
            )
        return out

    def _stock_flow_hsgt(
        self, ak: Any, symbol: str, start: date, end: date
    ) -> list[dict]:
        try:
            df = self._call_with_retry(ak.stock_hsgt_individual_em, symbol=symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("hsgt_individual %s 失败: %s", symbol, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_date = col_by_keywords(df.columns, ("持股日期", "日期")) or df.columns[0]
        c_net = col_by_keywords(df.columns, ("增持资金", "净买"))
        c_shares = col_by_keywords(df.columns, ("增持股数",))
        parsed: list[dict] = []
        for _, r in df.iterrows():
            day = _parse_day(as_str(r[c_date]))
            if day is None or day > end:
                continue
            net = _finite(as_float(r[c_net])) if c_net is not None else None
            if net is None:
                continue
            extra = {}
            if c_shares is not None:
                extra["delta_shares"] = _finite(as_float(r[c_shares]))
            parsed.append(
                {
                    "scope": symbol,
                    "trade_date": day.isoformat(),
                    "flow_type": "STOCK_NORTHBOUND",
                    "net_amount": net,
                    "buy_amount": None,
                    "sell_amount": None,
                    "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None,
                    "source": self.source,
                    "_day": day,
                }
            )
        in_range = [r for r in parsed if start <= r["_day"] <= end]
        if not in_range and parsed:
            lookback = max(5, (end - start).days + 5)
            in_range = sorted(parsed, key=lambda x: x["_day"])[-lookback:]
            logger.warning(
                "stock_flow hsgt %s 区间无数据，回退最近 %s 日", symbol, len(in_range)
            )
        for r in in_range:
            r.pop("_day", None)
        return in_range

    def _margin(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        rows: list[dict] = []
        symbols = [_plain(s) for s in request.symbols if s.strip()]
        sse_want = {s for s in symbols if s.startswith(("6", "5"))}
        sz_want = {s for s in symbols if s.startswith(("0", "3"))}

        # 上交所市场汇总（元）
        try:
            df = self._call_with_retry(
                ak.stock_margin_sse,
                start_date=_ymd(start),
                end_date=_ymd(end),
            )
            if df is not None and not getattr(df, "empty", True):
                c_date = col_by_keywords(df.columns, ("信用交易日期", "日期")) or df.columns[0]
                c_rzye = col_by_keywords(df.columns, ("融资余额",))
                c_rqye = col_by_keywords(df.columns, ("融券余量金额", "融券余额"))
                c_rzmre = col_by_keywords(df.columns, ("融资买入额",))
                c_rqyl = col_by_keywords(df.columns, ("融券余量",))
                c_rzrqye = col_by_keywords(df.columns, ("融资融券余额",))
                for _, r in df.iterrows():
                    day = _parse_day(as_str(r[c_date]))
                    if not self._in_range(day, start, end):
                        continue
                    rows.append(
                        {
                            "symbol": "MARKET_SSE",
                            "trade_date": day.isoformat(),
                            "rzye": _finite(as_float(r[c_rzye])) if c_rzye else None,
                            "rqye": _finite(as_float(r[c_rqye])) if c_rqye else None,
                            "rzmre": _finite(as_float(r[c_rzmre])) if c_rzmre else None,
                            "rqyl": _finite(as_float(r[c_rqyl])) if c_rqyl else None,
                            "rzche": None,
                            "rqchl": None,
                            "rzrqye": _finite(as_float(r[c_rzrqye])) if c_rzrqye else None,
                            "source": self.source,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("margin_sse 失败: %s", exc)

        # 深交所市场汇总（接口单位为亿元/亿股，统一换算为元/股）
        d = start
        while d <= end:
            if d.weekday() < 5:
                try:
                    df_sz = self._call_with_retry(ak.stock_margin_szse, date=_ymd(d))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("margin_szse %s 失败: %s", d, exc)
                    df_sz = None
                if df_sz is not None and not getattr(df_sz, "empty", True):
                    r = df_sz.iloc[0]
                    c_rzye = col_by_keywords(df_sz.columns, ("融资余额",))
                    c_rqye = col_by_keywords(df_sz.columns, ("融券余额", "融券余量金额"))
                    c_rzmre = col_by_keywords(df_sz.columns, ("融资买入额",))
                    c_rqyl = col_by_keywords(df_sz.columns, ("融券余量",))
                    c_rzrqye = col_by_keywords(df_sz.columns, ("融资融券余额",))
                    def _yi(col: Any) -> float | None:
                        if col is None:
                            return None
                        v = as_float(r[col])
                        return _finite(v * 1e8) if v is not None else None

                    rows.append(
                        {
                            "symbol": "MARKET_SZSE",
                            "trade_date": d.isoformat(),
                            "rzye": _yi(c_rzye),
                            "rqye": _yi(c_rqye),
                            "rzmre": _yi(c_rzmre),
                            "rqyl": _yi(c_rqyl),
                            "rzche": None,
                            "rqchl": None,
                            "rzrqye": _yi(c_rzrqye),
                            "source": self.source,
                        }
                    )
            d += timedelta(days=1)

        # 个股明细：沪→SSE，深→SZSE
        d = start
        while d <= end:
            if d.weekday() < 5:
                if sse_want:
                    rows.extend(
                        self._margin_detail_day(
                            ak,
                            day=d,
                            want=sse_want,
                            fetcher=ak.stock_margin_detail_sse,
                            code_keys=("标的证券代码", "代码"),
                            date_keys=("信用交易日期", "日期"),
                        )
                    )
                if sz_want:
                    rows.extend(
                        self._margin_detail_day(
                            ak,
                            day=d,
                            want=sz_want,
                            fetcher=ak.stock_margin_detail_szse,
                            code_keys=("证券代码", "代码"),
                            date_keys=("信用交易日期", "日期"),
                        )
                    )
            d += timedelta(days=1)

        if not rows:
            raise RuntimeError("margin 未拉到数据")
        return rows

    def _margin_detail_day(
        self,
        ak: Any,
        *,
        day: date,
        want: set[str],
        fetcher: Any,
        code_keys: tuple[str, ...],
        date_keys: tuple[str, ...],
    ) -> list[dict]:
        try:
            detail = self._call_with_retry(fetcher, date=_ymd(day))
        except Exception as exc:  # noqa: BLE001
            logger.warning("margin_detail %s 失败: %s", day, exc)
            return []
        if detail is None or getattr(detail, "empty", True):
            return []
        c_code = col_by_keywords(detail.columns, code_keys)
        c_date = col_by_keywords(detail.columns, date_keys)
        c_rzye = col_by_keywords(detail.columns, ("融资余额",))
        c_rqye = col_by_keywords(detail.columns, ("融券余量金额", "融券余额"))
        c_rzmre = col_by_keywords(detail.columns, ("融资买入额",))
        c_rqyl = col_by_keywords(detail.columns, ("融券余量",))
        c_rzrqye = col_by_keywords(detail.columns, ("融资融券余额",))
        out: list[dict] = []
        for _, r in detail.iterrows():
            code = as_str(r[c_code]) if c_code is not None else ""
            if code not in want:
                continue
            trade_day = _parse_day(as_str(r[c_date])) if c_date is not None else day
            out.append(
                {
                    "symbol": code,
                    "trade_date": (trade_day or day).isoformat(),
                    "rzye": _finite(as_float(r[c_rzye])) if c_rzye else None,
                    "rqye": _finite(as_float(r[c_rqye])) if c_rqye else None,
                    "rzmre": _finite(as_float(r[c_rzmre])) if c_rzmre else None,
                    "rqyl": _finite(as_float(r[c_rqyl])) if c_rqyl else None,
                    "rzche": None,
                    "rqchl": None,
                    "rzrqye": _finite(as_float(r[c_rzrqye])) if c_rzrqye else None,
                    "source": self.source,
                }
            )
        return out

    def _dragon(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        want = {_plain(s) for s in request.symbols} if request.symbols else None
        try:
            df = self._call_with_retry(
                ak.stock_lhb_detail_em,
                start_date=_ymd(start),
                end_date=_ymd(end),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"dragon_tiger 拉取失败: {exc}") from exc
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("代码",)) or (
            df.columns[1] if df.shape[1] > 1 else df.columns[0]
        )
        c_date = col_by_keywords(df.columns, ("上榜日", "日期"))
        c_reason = col_by_keywords(df.columns, ("解读", "上榜原因", "原因"))
        c_close = col_by_keywords(df.columns, ("收盘价",))
        c_pct = col_by_keywords(df.columns, ("涨跌幅",))
        c_net = col_by_keywords(df.columns, ("龙虎榜净买额", "净买"))
        c_buy = col_by_keywords(df.columns, ("龙虎榜买入额", "买入额"))
        c_sell = col_by_keywords(df.columns, ("龙虎榜卖出额", "卖出额"))
        rows: list[dict] = []
        for _, r in df.iterrows():
            symbol = as_str(r[c_code])
            if not symbol or (want is not None and symbol not in want):
                continue
            day = _parse_day(as_str(r[c_date])) if c_date is not None else None
            if day is None:
                continue
            reason = as_str(r[c_reason]) if c_reason is not None else ""
            event_id = f"{symbol}|{day.isoformat()}|{reason[:80]}"
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": day.isoformat(),
                    "reason": reason or None,
                    "close": _finite(as_float(r[c_close])) if c_close else None,
                    "pct_chg": _finite(as_float(r[c_pct])) if c_pct else None,
                    "net_amount": _finite(as_float(r[c_net])) if c_net else None,
                    "buy_amount": _finite(as_float(r[c_buy])) if c_buy else None,
                    "sell_amount": _finite(as_float(r[c_sell])) if c_sell else None,
                    "source_event_id": event_id[:240],
                    "source": self.source,
                }
            )
        return rows

    def _dragon_seat(self, ak: Any, request: FetchRequest) -> list[dict]:
        """龙虎榜每日活跃营业部（席位级净买）。"""
        start, end = self._require_range(request)
        try:
            df = self._call_with_retry(
                ak.stock_lhb_hyyyb_em,
                start_date=_ymd(start),
                end_date=_ymd(end),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"dragon_tiger_seat 拉取失败: {exc}") from exc
        if df is None or getattr(df, "empty", True):
            return []
        c_seat = col_by_keywords(df.columns, ("营业部名称", "营业部"))
        c_code = col_by_keywords(df.columns, ("营业部代码",))
        c_date = col_by_keywords(df.columns, ("上榜日", "日期"))
        c_buy_n = col_by_keywords(df.columns, ("买入个股数",))
        c_sell_n = col_by_keywords(df.columns, ("卖出个股数",))
        c_buy = col_by_keywords(df.columns, ("买入总金额",))
        c_sell = col_by_keywords(df.columns, ("卖出总金额",))
        c_net = col_by_keywords(df.columns, ("总买卖净额", "净额"))
        c_stocks = col_by_keywords(df.columns, ("买入股票",))
        rows: list[dict] = []
        for i, r in df.iterrows():
            seat = as_str(r[c_seat]) if c_seat is not None else ""
            if not seat:
                continue
            day = _parse_day(as_str(r[c_date])) if c_date is not None else None
            if day is None:
                continue
            seat_code = as_str(r[c_code]) if c_code is not None else ""
            event_id = f"{day.isoformat()}|{seat_code or seat}|{i}"
            buy_n = as_float(r[c_buy_n]) if c_buy_n is not None else None
            sell_n = as_float(r[c_sell_n]) if c_sell_n is not None else None
            rows.append(
                {
                    "trade_date": day.isoformat(),
                    "seat_name": seat,
                    "seat_code": seat_code or None,
                    "buy_count": int(buy_n) if buy_n is not None else None,
                    "sell_count": int(sell_n) if sell_n is not None else None,
                    "buy_amount": _finite(as_float(r[c_buy])) if c_buy else None,
                    "sell_amount": _finite(as_float(r[c_sell])) if c_sell else None,
                    "net_amount": _finite(as_float(r[c_net])) if c_net else None,
                    "related_stocks": (
                        as_str(r[c_stocks]) if c_stocks is not None else None
                    ),
                    "source_event_id": event_id[:240],
                    "source": self.source,
                }
            )
        return rows

    def _block(self, ak: Any, request: FetchRequest) -> list[dict]:
        start, end = self._require_range(request)
        want = {_plain(s) for s in request.symbols} if request.symbols else None
        try:
            df = self._call_with_retry(
                ak.stock_dzjy_mrmx,
                symbol="A股",
                start_date=_ymd(start),
                end_date=_ymd(end),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"block_trade 拉取失败: {exc}") from exc
        if df is None or getattr(df, "empty", True):
            return []
        c_date = col_by_keywords(df.columns, ("交易日期", "日期"))
        c_code = col_by_keywords(df.columns, ("证券代码", "代码"))
        c_price = col_by_keywords(df.columns, ("成交价",))
        c_vol = col_by_keywords(df.columns, ("成交量",))
        c_amt = col_by_keywords(df.columns, ("成交额",))
        c_prem = col_by_keywords(df.columns, ("溢价率",))
        c_buyer = col_by_keywords(df.columns, ("买方营业部", "买方"))
        c_seller = col_by_keywords(df.columns, ("卖方营业部", "卖方"))
        rows: list[dict] = []
        for i, r in df.iterrows():
            symbol = as_str(r[c_code]) if c_code is not None else ""
            if not symbol or (want is not None and symbol not in want):
                continue
            day = _parse_day(as_str(r[c_date])) if c_date is not None else None
            if day is None:
                continue
            price = _finite(as_float(r[c_price])) if c_price else None
            volume = _finite(as_float(r[c_vol])) if c_vol else None
            event_id = f"{symbol}|{day.isoformat()}|{price}|{volume}|{i}"
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": day.isoformat(),
                    "price": price,
                    "volume": volume,
                    "amount": _finite(as_float(r[c_amt])) if c_amt else None,
                    "premium_rate": _finite(as_float(r[c_prem])) if c_prem else None,
                    "buyer": as_str(r[c_buyer]) if c_buyer is not None else None,
                    "seller": as_str(r[c_seller]) if c_seller is not None else None,
                    "source_event_id": event_id[:240],
                    "source": self.source,
                }
            )
        return rows
