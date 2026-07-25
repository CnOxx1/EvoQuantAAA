from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any

from data_ingest.core_ref.models import FetchBundle, FetchRequest
from data_ingest.core_ref.sources._parse import (
    as_float,
    as_str,
    board_from_code,
    col_by_keywords,
    infer_st_type,
)
from data_ingest.core_ref.sources.base import CoreRefSource

logger = logging.getLogger(__name__)


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 akshare，请执行: pip install -r requirements.txt"
        ) from exc
    return ak


class AkshareCoreRefSource(CoreRefSource):
    """
    真实参考数据源（akshare 聚合公开接口）。

    - calendar      → tool_trade_date_hist_sina
    - listing       → 沪/深/北名称代码 + 退市列表
    - industry      → 申万一级成分（SW*）或深/北所属行业
    - share_capital → 深/北列表股本 + 沪市个股股本结构（可限流）
    - index_member  → index_stock_cons_csindex（回退 index_stock_cons）
    - special_treat → 东财 ST 列表（回退名称扫描）
    """

    source = "akshare"

    def __init__(
        self,
        *,
        request_pause: float = 0.12,
        share_capital_sh_limit: int | None = 80,
    ) -> None:
        self.request_pause = request_pause
        # 沪市逐票接口慢；默认限流保证可跑通。设为 0 表示全量。
        self.share_capital_sh_limit = share_capital_sh_limit

    def fetch(self, request: FetchRequest) -> FetchBundle:
        ak = _require_akshare()
        dispatch = {
            "calendar": self._calendar,
            "listing": lambda _ak, _req: self._listing(_ak),
            "industry": self._industry,
            "share_capital": lambda _ak, _req: self._share_capital(_ak),
            "index_member": self._index_member,
            "special_treat": lambda _ak, _req: self._special_treat(_ak),
            "restricted_release": self._restricted_release,
        }
        if request.kind not in dispatch:
            raise ValueError(f"unsupported kind: {request.kind}")
        rows = dispatch[request.kind](ak, request)
        logger.info("akshare fetched kind=%s rows=%s", request.kind, len(rows))
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _pause(self) -> None:
        if self.request_pause > 0:
            time.sleep(self.request_pause)

    def _call(self, fn: Any, *, label: str) -> Any:
        from shared.akshare_call import call_with_retry

        return call_with_retry(
            fn, label=label, attempts=3, pause=self.request_pause, backoff=0.6
        )

    def _calendar(self, ak: Any, request: FetchRequest) -> list[dict]:
        start = date.fromisoformat(request.start or "")
        end = date.fromisoformat(request.end or "")
        if end < start:
            raise ValueError("end 必须 >= start")
        df = ak.tool_trade_date_hist_sina()
        col = "trade_date" if "trade_date" in df.columns else df.columns[0]
        open_dates = {as_str(x) for x in df[col].tolist() if as_str(x)}
        rows: list[dict] = []
        d = start
        while d <= end:
            ds = d.isoformat()
            rows.append(
                {
                    "exchange": request.exchange,
                    "trade_date": ds,
                    "is_open": 1 if ds in open_dates else 0,
                    "is_half_day": 0,
                    "source": self.source,
                }
            )
            d += timedelta(days=1)
        return rows

    def _listing(self, ak: Any) -> list[dict]:
        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add(
            *,
            symbol: str,
            name: str,
            exchange: str,
            board: str,
            list_date: str,
            delist_date: str | None = None,
        ) -> None:
            if not symbol:
                return
            eff = list_date or delist_date or "1970-01-01"
            key = (symbol, eff)
            if key in seen:
                return
            seen.add(key)
            rows.append(
                {
                    "symbol": symbol,
                    "name": name or symbol,
                    "exchange": exchange,
                    "board": board,
                    "list_date": list_date or None,
                    "delist_date": delist_date,
                    "effective_date": eff,
                    "source": self.source,
                }
            )

        for symbol_name, board_hint in (("主板A股", None), ("科创板", "科创板")):
            try:
                self._pause()
                df = ak.stock_info_sh_name_code(symbol=symbol_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("上交所 %s 失败: %s", symbol_name, exc)
                continue
            c_code = col_by_keywords(df.columns, ("证券代码", "代码")) or df.columns[0]
            c_name = col_by_keywords(df.columns, ("证券简称", "简称")) or df.columns[1]
            c_date = col_by_keywords(df.columns, ("上市日期",)) or df.columns[-1]
            for _, r in df.iterrows():
                symbol = as_str(r[c_code])
                add(
                    symbol=symbol,
                    name=as_str(r[c_name]),
                    exchange="SSE",
                    board=board_hint or board_from_code(symbol, "SSE"),
                    list_date=as_str(r[c_date]) or "1970-01-01",
                )

        self._pause()
        sz = ak.stock_info_sz_name_code(symbol="A股列表")
        c_code = col_by_keywords(sz.columns, ("A股代码", "代码")) or sz.columns[1]
        c_name = col_by_keywords(sz.columns, ("A股简称", "简称")) or sz.columns[2]
        c_date = col_by_keywords(sz.columns, ("上市日期",)) or sz.columns[3]
        for _, r in sz.iterrows():
            symbol = as_str(r[c_code])
            add(
                symbol=symbol,
                name=as_str(r[c_name]),
                exchange="SZSE",
                board=board_from_code(symbol, "SZSE"),
                list_date=as_str(r[c_date]) or "1970-01-01",
            )

        try:
            self._pause()
            bj = ak.stock_info_bj_name_code()
            c_code = col_by_keywords(bj.columns, ("证券代码", "代码")) or bj.columns[0]
            c_name = col_by_keywords(bj.columns, ("证券简称", "简称")) or bj.columns[1]
            c_date = col_by_keywords(bj.columns, ("上市日期",)) or bj.columns[4]
            for _, r in bj.iterrows():
                symbol = as_str(r[c_code])
                add(
                    symbol=symbol,
                    name=as_str(r[c_name]),
                    exchange="BSE",
                    board="北交所",
                    list_date=as_str(r[c_date]) or "1970-01-01",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("北交所列表失败: %s", exc)

        self._merge_delist(ak, rows, seen)
        if not rows:
            raise RuntimeError("listing 未拉到任何证券")
        return rows

    def _merge_delist(
        self, ak: Any, rows: list[dict], seen: set[tuple[str, str]]
    ) -> None:
        by_symbol = {r["symbol"]: r for r in rows}

        def upsert_delist(
            symbol: str, name: str, exchange: str, delist_date: str
        ) -> None:
            if not symbol:
                return
            if symbol in by_symbol:
                by_symbol[symbol]["delist_date"] = delist_date or None
                return
            eff = delist_date or "1970-01-01"
            if (symbol, eff) in seen:
                return
            seen.add((symbol, eff))
            row = {
                "symbol": symbol,
                "name": name or symbol,
                "exchange": exchange,
                "board": board_from_code(symbol, exchange),
                "list_date": None,
                "delist_date": delist_date or None,
                "effective_date": eff,
                "source": self.source,
            }
            rows.append(row)
            by_symbol[symbol] = row

        try:
            self._pause()
            sh_d = ak.stock_info_sh_delist()
            c_code = col_by_keywords(sh_d.columns, ("公司代码", "代码")) or (
                sh_d.columns[1] if sh_d.shape[1] > 1 else sh_d.columns[0]
            )
            c_name = col_by_keywords(sh_d.columns, ("公司简称", "简称", "名称")) or sh_d.columns[0]
            c_date = col_by_keywords(sh_d.columns, ("终止", "摘牌")) or sh_d.columns[-1]
            for _, r in sh_d.iterrows():
                upsert_delist(
                    as_str(r[c_code]),
                    as_str(r[c_name]),
                    "SSE",
                    as_str(r[c_date]),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("上交所退市列表失败: %s", exc)

        try:
            self._pause()
            sz_d = ak.stock_info_sz_delist(symbol="终止上市公司")
            c_code = col_by_keywords(sz_d.columns, ("证券代码", "代码")) or (
                sz_d.columns[1] if sz_d.shape[1] > 1 else sz_d.columns[0]
            )
            c_name = col_by_keywords(sz_d.columns, ("证券简称", "简称", "名称")) or sz_d.columns[0]
            c_date = col_by_keywords(sz_d.columns, ("终止",)) or sz_d.columns[-1]
            for _, r in sz_d.iterrows():
                upsert_delist(
                    as_str(r[c_code]),
                    as_str(r[c_name]),
                    "SZSE",
                    as_str(r[c_date]),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("深交所退市列表失败: %s", exc)

    def _industry(self, ak: Any, request: FetchRequest) -> list[dict]:
        standard = (request.industry_standard or "SW2021").upper()
        if standard.startswith("SW"):
            return self._industry_sw(ak, standard)
        return self._industry_exchange(ak, standard)

    def _industry_sw(self, ak: Any, standard: str) -> list[dict]:
        self._pause()
        industries = ak.sw_index_first_info()
        code_col, name_col = industries.columns[0], industries.columns[1]
        rows: list[dict] = []
        seen: set[str] = set()
        for _, ind in industries.iterrows():
            ind_code = as_str(ind[code_col]).replace(".SI", "")
            ind_name = as_str(ind[name_col])
            if not ind_code:
                continue
            try:
                self._pause()
                members = ak.index_component_sw(symbol=ind_code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("申万成分失败 %s: %s", ind_code, exc)
                continue
            for _, m in members.iterrows():
                symbol = as_str(m.iloc[1]) if len(m) > 1 else ""
                eff = as_str(m.iloc[-1]) if len(m) else ""
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                rows.append(
                    {
                        "symbol": symbol,
                        "standard": standard,
                        "industry_code": ind_code,
                        "industry_name": ind_name,
                        "effective_date": eff or "1970-01-01",
                        "source": self.source,
                    }
                )
        if not rows:
            raise RuntimeError("申万行业成分为空")
        return rows

    def _industry_exchange(self, ak: Any, standard: str) -> list[dict]:
        rows: list[dict] = []
        today = date.today().isoformat()
        self._pause()
        sz = ak.stock_info_sz_name_code(symbol="A股列表")
        c_code = col_by_keywords(sz.columns, ("A股代码", "代码")) or sz.columns[1]
        c_ind = col_by_keywords(sz.columns, ("行业",)) or sz.columns[-1]
        for _, r in sz.iterrows():
            symbol = as_str(r[c_code])
            industry_name = as_str(r[c_ind])
            if not symbol or not industry_name:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "standard": standard,
                    "industry_code": industry_name.split()[0][:16],
                    "industry_name": industry_name,
                    "effective_date": today,
                    "source": self.source,
                }
            )
        try:
            self._pause()
            bj = ak.stock_info_bj_name_code()
            c_code = col_by_keywords(bj.columns, ("证券代码", "代码")) or bj.columns[0]
            c_ind = col_by_keywords(bj.columns, ("行业",))
            if c_ind is not None:
                for _, r in bj.iterrows():
                    symbol = as_str(r[c_code])
                    industry_name = as_str(r[c_ind])
                    if not symbol or not industry_name:
                        continue
                    rows.append(
                        {
                            "symbol": symbol,
                            "standard": standard,
                            "industry_code": industry_name[:16],
                            "industry_name": industry_name,
                            "effective_date": today,
                            "source": self.source,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("北交所行业失败: %s", exc)
        if not rows:
            raise RuntimeError("交易所行业分类为空")
        return rows

    def _share_capital(self, ak: Any) -> list[dict]:
        rows: list[dict] = []
        today = date.today().isoformat()
        seen: set[str] = set()

        self._pause()
        sz = ak.stock_info_sz_name_code(symbol="A股列表")
        c_code = col_by_keywords(sz.columns, ("A股代码", "代码")) or sz.columns[1]
        c_total = col_by_keywords(sz.columns, ("总股本",))
        c_float = col_by_keywords(sz.columns, ("流通股本",))
        for _, r in sz.iterrows():
            symbol = as_str(r[c_code])
            total = as_float(r[c_total]) if c_total is not None else None
            float_ = as_float(r[c_float]) if c_float is not None else None
            if not symbol or symbol in seen or total is None:
                continue
            seen.add(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "total_shares": total,
                    "float_shares": float_ if float_ is not None else total,
                    "effective_date": today,
                    "source": self.source,
                }
            )

        try:
            self._pause()
            bj = ak.stock_info_bj_name_code()
            c_code = col_by_keywords(bj.columns, ("证券代码", "代码")) or bj.columns[0]
            c_total = col_by_keywords(bj.columns, ("总股本",))
            c_float = col_by_keywords(bj.columns, ("流通股本",))
            for _, r in bj.iterrows():
                symbol = as_str(r[c_code])
                total = as_float(r[c_total]) if c_total is not None else None
                float_ = as_float(r[c_float]) if c_float is not None else None
                if not symbol or symbol in seen or total is None:
                    continue
                seen.add(symbol)
                rows.append(
                    {
                        "symbol": symbol,
                        "total_shares": total,
                        "float_shares": float_ if float_ is not None else total,
                        "effective_date": today,
                        "source": self.source,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("北交所股本失败: %s", exc)

        sh_codes: list[str] = []
        for board in ("主板A股", "科创板"):
            try:
                self._pause()
                sh = ak.stock_info_sh_name_code(symbol=board)
                c_code = col_by_keywords(sh.columns, ("证券代码", "代码")) or sh.columns[0]
                sh_codes.extend(as_str(x) for x in sh[c_code].tolist())
            except Exception as exc:  # noqa: BLE001
                logger.warning("沪市 %s 代码失败: %s", board, exc)

        sh_codes = [c for c in dict.fromkeys(sh_codes) if c and c not in seen]
        limit = self.share_capital_sh_limit
        if limit is not None and limit > 0:
            sh_codes = sh_codes[:limit]
            logger.info("沪市股本限流拉取 limit=%s", limit)

        for i, symbol in enumerate(sh_codes, 1):
            try:
                self._pause()
                gbjg = ak.stock_zh_a_gbjg_em(symbol=symbol)
                if gbjg is None or gbjg.empty:
                    continue
                latest = gbjg.iloc[0]
                c_total = col_by_keywords(gbjg.columns, ("总股本",))
                c_float = col_by_keywords(
                    gbjg.columns, ("流通A股", "已流通股份", "流通股本")
                )
                c_date = col_by_keywords(gbjg.columns, ("变更日期", "日期"))
                total = as_float(latest[c_total]) if c_total is not None else None
                float_ = as_float(latest[c_float]) if c_float is not None else None
                eff = as_str(latest[c_date]) if c_date is not None else today
                if total is None:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "total_shares": total,
                        "float_shares": float_ if float_ is not None else total,
                        "effective_date": eff or today,
                        "source": self.source,
                    }
                )
                seen.add(symbol)
            except Exception as exc:  # noqa: BLE001
                logger.warning("沪市股本 %s 失败: %s", symbol, exc)
            if i % 50 == 0:
                logger.info("沪市股本进度 %s/%s", i, len(sh_codes))

        if not rows:
            raise RuntimeError("share_capital 未拉到数据")
        return rows

    def _index_member(self, ak: Any, request: FetchRequest) -> list[dict]:
        indexes = request.index_symbols or ["000300"]
        trade_date = (request.end or request.start or date.today().isoformat())[:10]
        rows: list[dict] = []
        for index_symbol in indexes:
            code = index_symbol.split(".")[0]
            members = None
            try:
                self._pause()
                members = ak.index_stock_cons_csindex(symbol=code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("中证成分失败 %s: %s，尝试新浪", code, exc)
            if members is None or getattr(members, "empty", True):
                self._pause()
                members = ak.index_stock_cons(symbol=code)

            as_of = trade_date
            c_date = col_by_keywords(members.columns, ("日期",))
            if c_date is not None and len(members):
                as_of = as_str(members.iloc[0][c_date]) or as_of
            # 勿用裸「代码」：会误匹配「指数代码」导致成分全写成指数本身
            c_symbol = col_by_keywords(
                members.columns,
                ("成分券代码",),
                ("成分代码",),
                ("品种代码",),
                ("股票代码",),
                ("证券代码",),
                ("constituent",),
            )
            if c_symbol is None or "指数" in str(c_symbol):
                # 常见中证表：日期/指数代码/指数名称/成分券代码/...
                for cand in members.columns:
                    cs = str(cand)
                    if "成分" in cs and "代码" in cs:
                        c_symbol = cand
                        break
            if c_symbol is None:
                c_symbol = (
                    members.columns[4] if members.shape[1] >= 5 else members.columns[0]
                )
            c_weight = col_by_keywords(members.columns, ("权重", "weight"))

            parsed: list[tuple[str, float | None]] = []
            for _, rec in members.iterrows():
                symbol = as_str(rec[c_symbol]).split(".")[0]
                if not symbol or symbol == code or not symbol.isdigit():
                    continue
                w = as_float(rec[c_weight]) if c_weight is not None else None
                parsed.append((symbol, w))
            n = len(parsed) or 1
            default_w = round(1.0 / n, 6)
            for symbol, w in parsed:
                weight = default_w
                if w is not None:
                    weight = w / 100.0 if w > 1 else w
                rows.append(
                    {
                        "index_symbol": code,
                        "symbol": symbol,
                        "trade_date": as_of,
                        "weight": weight,
                        "source": self.source,
                    }
                )
        if not rows:
            raise RuntimeError("index_member 为空")
        return rows

    def _special_treat(self, ak: Any) -> list[dict]:
        today = date.today().isoformat()
        rows: list[dict] = []

        try:
            self._pause()
            st_df = ak.stock_zh_a_st_em()
            c_code = col_by_keywords(st_df.columns, ("代码",)) or (
                st_df.columns[1] if st_df.shape[1] > 1 else st_df.columns[0]
            )
            c_name = col_by_keywords(st_df.columns, ("名称", "简称")) or (
                st_df.columns[2] if st_df.shape[1] > 2 else st_df.columns[0]
            )
            for _, r in st_df.iterrows():
                symbol = as_str(r[c_code])
                name = as_str(r[c_name])
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "treat_type": infer_st_type(name) or "ST",
                        "effective_date": today,
                        "end_date": None,
                        "source": self.source,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("东财 ST 列表失败，回退名称扫描: %s", exc)

        if not rows:
            self._pause()
            all_df = ak.stock_info_a_code_name()
            c_code, c_name = all_df.columns[0], all_df.columns[1]
            for _, r in all_df.iterrows():
                name = as_str(r[c_name])
                treat = infer_st_type(name)
                if not treat:
                    continue
                symbol = as_str(r[c_code])
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "treat_type": treat,
                        "effective_date": today,
                        "end_date": None,
                        "source": self.source,
                    }
                )

        if not rows:
            raise RuntimeError("special_treat 未识别到 ST 标的")
        return rows

    def _restricted_release(self, ak: Any, request: FetchRequest) -> list[dict]:
        """限售解禁：区间用 detail_em；有 symbols 时再按票 queue 补齐并过滤。"""
        if not (request.start and request.end):
            raise ValueError("restricted_release 必须提供 --start 与 --end")
        start, end = request.start[:10], request.end[:10]
        start_ymd, end_ymd = start.replace("-", ""), end.replace("-", "")
        symbol_filter = {
            as_str(s).split(".")[0][-6:]
            for s in (request.symbols or [])
            if as_str(s)
        }
        rows: list[dict] = []
        seen: set[str] = set()

        def _append_row(
            *,
            symbol: str,
            name: str | None,
            release_date: str,
            share_type: str | None,
            release_shares: float | None,
            actual_shares: float | None,
            actual_mv: float | None,
            float_ratio: float | None,
            pre_close: float | None,
            pct_b20: float | None,
            pct_a20: float | None,
        ) -> None:
            if not symbol or not release_date:
                return
            if symbol_filter and symbol not in symbol_filter:
                return
            if release_date < start or release_date > end:
                return
            event_id = f"{symbol}|{release_date}|{share_type or ''}|{release_shares or ''}"
            if event_id in seen:
                return
            seen.add(event_id)
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "release_date": release_date,
                    "share_type": share_type,
                    "release_shares": release_shares,
                    "actual_shares": actual_shares,
                    "actual_mv": actual_mv,
                    "float_ratio": float_ratio,
                    "pre_close": pre_close,
                    "pct_chg_b20": pct_b20,
                    "pct_chg_a20": pct_a20,
                    "source_event_id": event_id[:240],
                    "source": self.source,
                }
            )

        try:
            df = self._call(
                lambda: ak.stock_restricted_release_detail_em(
                    start_date=start_ymd, end_date=end_ymd
                ),
                label="restricted_release_detail",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("restricted_release detail 失败: %s", exc)
            df = None
        if df is not None and not getattr(df, "empty", True):
            c_code = col_by_keywords(df.columns, ("股票代码", "代码"))
            c_name = col_by_keywords(df.columns, ("股票简称", "简称", "名称"))
            c_date = col_by_keywords(df.columns, ("解禁时间", "解禁日期"))
            c_type = col_by_keywords(df.columns, ("限售股类型", "类型"))
            c_shares = col_by_keywords(df.columns, ("解禁数量",))
            c_actual = col_by_keywords(df.columns, ("实际解禁数量",))
            c_mv = col_by_keywords(df.columns, ("实际解禁市值", "实际解禁数量市值"))
            c_ratio = col_by_keywords(df.columns, ("占解禁前流通市值比例", "占流通市值比例"))
            c_close = col_by_keywords(df.columns, ("解禁前一交易日收盘价",))
            c_b20 = col_by_keywords(df.columns, ("解禁前20日涨跌幅",))
            c_a20 = col_by_keywords(df.columns, ("解禁后20日涨跌幅",))
            for _, r in df.iterrows():
                symbol = as_str(r[c_code]) if c_code is not None else ""
                rd = as_str(r[c_date])[:10] if c_date is not None else ""
                _append_row(
                    symbol=symbol,
                    name=as_str(r[c_name]) if c_name is not None else None,
                    release_date=rd,
                    share_type=as_str(r[c_type]) if c_type is not None else None,
                    release_shares=as_float(r[c_shares]) if c_shares is not None else None,
                    actual_shares=as_float(r[c_actual]) if c_actual is not None else None,
                    actual_mv=as_float(r[c_mv]) if c_mv is not None else None,
                    float_ratio=as_float(r[c_ratio]) if c_ratio is not None else None,
                    pre_close=as_float(r[c_close]) if c_close is not None else None,
                    pct_b20=as_float(r[c_b20]) if c_b20 is not None else None,
                    pct_a20=as_float(r[c_a20]) if c_a20 is not None else None,
                )

        # 有显式 symbols 时按票 queue 补漏（detail 分页偶发不全）
        for symbol in sorted(symbol_filter):
            try:
                qdf = self._call(
                    lambda s=symbol: ak.stock_restricted_release_queue_em(symbol=s),
                    label=f"restricted_release_queue:{symbol}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("restricted_release queue %s 失败: %s", symbol, exc)
                continue
            if qdf is None or getattr(qdf, "empty", True):
                continue
            c_date = col_by_keywords(qdf.columns, ("解禁时间", "解禁日期"))
            c_type = col_by_keywords(qdf.columns, ("限售股类型", "类型"))
            c_shares = col_by_keywords(qdf.columns, ("解禁数量",))
            c_actual = col_by_keywords(qdf.columns, ("实际解禁数量",))
            c_mv = col_by_keywords(qdf.columns, ("实际解禁数量市值", "实际解禁市值"))
            c_ratio = col_by_keywords(qdf.columns, ("占流通市值比例",))
            c_close = col_by_keywords(qdf.columns, ("解禁前一交易日收盘价",))
            c_b20 = col_by_keywords(qdf.columns, ("解禁前20日涨跌幅",))
            c_a20 = col_by_keywords(qdf.columns, ("解禁后20日涨跌幅",))
            for _, r in qdf.iterrows():
                rd = as_str(r[c_date])[:10] if c_date is not None else ""
                _append_row(
                    symbol=symbol,
                    name=None,
                    release_date=rd,
                    share_type=as_str(r[c_type]) if c_type is not None else None,
                    release_shares=as_float(r[c_shares]) if c_shares is not None else None,
                    actual_shares=as_float(r[c_actual]) if c_actual is not None else None,
                    actual_mv=as_float(r[c_mv]) if c_mv is not None else None,
                    float_ratio=as_float(r[c_ratio]) if c_ratio is not None else None,
                    pre_close=as_float(r[c_close]) if c_close is not None else None,
                    pct_b20=as_float(r[c_b20]) if c_b20 is not None else None,
                    pct_a20=as_float(r[c_a20]) if c_a20 is not None else None,
                )
        return rows

