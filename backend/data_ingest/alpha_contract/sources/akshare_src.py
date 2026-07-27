from __future__ import annotations

import hashlib
import logging
from typing import Any

from data_ingest.alpha_contract.models import FetchBundle, FetchRequest
from data_ingest.alpha_contract.sources.base import ContractSource
from data_ingest.ingest_common.parse import as_float, as_str, col_by_keywords
from shared.akshare_call import call_with_retry

logger = logging.getLogger(__name__)

_WIN_BID_TYPE_KEYS = ("中标", "中选", "成交")
_WIN_BID_NAME_KEYS = ("中标", "中选", "成交公告", "中标通知")


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 akshare") from exc
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


def _ymd(text: str | None) -> str:
    t = as_str(text)
    if not t:
        return ""
    if len(t) >= 10 and t[4] == "-":
        return t[:10]
    digits = "".join(ch for ch in t if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return t[:10]


def _is_win_bid(contract_type: str, contract_name: str) -> bool:
    ctype = contract_type or ""
    cname = contract_name or ""
    if any(k in ctype for k in _WIN_BID_TYPE_KEYS):
        return True
    return any(k in cname for k in _WIN_BID_NAME_KEYS)


def _event_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


class AkshareContractSource(ContractSource):
    """东财重大合同明细 `stock_zdhtmx_em`（含项目中标）。"""

    source = "akshare"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        if not (request.start and request.end):
            raise ValueError("major_contract/win_bid 需要 --start 与 --end")
        ak = _require_akshare()
        start = request.start[:10].replace("-", "")
        end = request.end[:10].replace("-", "")
        try:
            df = call_with_retry(
                lambda: ak.stock_zdhtmx_em(start_date=start, end_date=end),
                label="stock_zdhtmx_em",
                attempts=3,
                pause=0.3,
                backoff=0.8,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_zdhtmx_em 失败: %s", exc)
            return FetchBundle(kind=request.kind, rows=[], source=self.source)

        if df is None or getattr(df, "empty", True):
            return FetchBundle(kind=request.kind, rows=[], source=self.source)

        c_code = col_by_keywords(df.columns, ("股票代码", "代码"))
        c_name = col_by_keywords(df.columns, ("股票简称", "简称", "名称"))
        c_self = col_by_keywords(df.columns, ("签署主体",))
        c_self_rel = col_by_keywords(df.columns, ("签署主体-与上市公司关系", "与上市公司关系"))
        c_other = col_by_keywords(df.columns, ("其他签署方",))
        c_other_rel = col_by_keywords(df.columns, ("其他签署方-与上市公司关系",))
        c_type = col_by_keywords(df.columns, ("合同类型",))
        c_cname = col_by_keywords(df.columns, ("合同名称",))
        c_amt = col_by_keywords(df.columns, ("合同金额",))
        c_rev = col_by_keywords(df.columns, ("上年度营业收入",))
        c_ratio = col_by_keywords(df.columns, ("占上年度营业收入比例",))
        c_rev_latest = col_by_keywords(df.columns, ("最新财务报表的营业收入",))
        c_sign = col_by_keywords(df.columns, ("签署日期",))
        c_ann = col_by_keywords(df.columns, ("公告日期",))

        want = {_plain(s) for s in (request.symbols or []) if s.strip()}
        rows: list[dict[str, Any]] = []
        for _, r in df.iterrows():
            code = _plain(as_str(r[c_code])) if c_code is not None else ""
            if not code:
                continue
            if want and code not in want:
                continue
            ann = _ymd(as_str(r[c_ann]) if c_ann is not None else "")
            if not ann:
                continue
            if request.start and ann < request.start[:10]:
                continue
            if request.end and ann > request.end[:10]:
                continue
            ctype = as_str(r[c_type]) if c_type is not None else ""
            cname = as_str(r[c_cname]) if c_cname is not None else ""
            win = 1 if _is_win_bid(ctype, cname) else 0
            if request.kind == "win_bid" and not win:
                continue
            party_self = as_str(r[c_self]) if c_self is not None else ""
            party_other = as_str(r[c_other]) if c_other is not None else ""
            eid = _event_id(code, ann, ctype, cname, party_self, party_other)
            rows.append(
                {
                    "symbol": code,
                    "name": as_str(r[c_name]) if c_name is not None else None,
                    "announce_date": ann,
                    "sign_date": _ymd(as_str(r[c_sign]) if c_sign is not None else "")
                    or None,
                    "contract_type": ctype or None,
                    "contract_name": cname or None,
                    "amount": as_float(r[c_amt]) if c_amt is not None else None,
                    "revenue_prev_year": as_float(r[c_rev]) if c_rev is not None else None,
                    "amount_rev_ratio": as_float(r[c_ratio])
                    if c_ratio is not None
                    else None,
                    "revenue_latest": as_float(r[c_rev_latest])
                    if c_rev_latest is not None
                    else None,
                    "party_self": party_self or None,
                    "party_self_relation": as_str(r[c_self_rel])
                    if c_self_rel is not None
                    else None,
                    "party_other": party_other or None,
                    "party_other_relation": as_str(r[c_other_rel])
                    if c_other_rel is not None
                    else None,
                    "is_win_bid": win,
                    "source_event_id": eid,
                    "source": self.source,
                }
            )
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)
