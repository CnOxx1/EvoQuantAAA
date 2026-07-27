from __future__ import annotations

import hashlib
import itertools
import json
import logging
import re
from datetime import date
from typing import Any

from data_ingest.alpha_relation.models import HOLDER_TYPES, FetchBundle, FetchRequest
from data_ingest.alpha_relation.sources.base import RelationSource
from data_ingest.ingest_common.parse import as_float, as_str, col_by_keywords
from shared.akshare_call import call_with_retry

logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"\b(\d{6})\b")


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 akshare") from exc
    return ak


def _plain(symbol: str) -> str:
    s = as_str(symbol).upper()
    for p in ("SH", "SZ", "BJ"):
        if s.startswith(p) and len(s) > len(p):
            s = s[len(p) :]
    for suf in (".SH", ".SZ", ".BJ"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s.split(".")[0]


def _em_code(symbol: str) -> str:
    """东财人气接口需要带市场前缀。"""
    code = _plain(symbol)
    if not code:
        return ""
    if code.startswith(("5", "6", "9")):
        return f"SH{code}"
    if code.startswith(("4", "8")):
        return f"BJ{code}"
    return f"SZ{code}"


def _asof(request: FetchRequest) -> str:
    return (request.end or date.today().isoformat())[:10]


def _event_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:32]


def _ordered_pair(a: str, b: str) -> tuple[str, str] | None:
    a, b = _plain(a), _plain(b)
    if not a or not b or a == b:
        return None
    return (a, b) if a < b else (b, a)


def _parse_stock_detail(text: str) -> list[tuple[str, str]]:
    """解析 `601668|中国建筑|2025-09-30,002271|...` → [(code, name), ...]。"""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chunk in as_str(text).split(","):
        parts = [p.strip() for p in chunk.split("|") if p.strip()]
        if not parts:
            continue
        code = _plain(parts[0])
        if not code or code in seen:
            continue
        name = parts[1] if len(parts) > 1 else ""
        seen.add(code)
        out.append((code, name))
    return out


class AkshareRelationSource(RelationSource):
    """
    - hot_relate：东财人气相关股（直接边）
    - holder_team：股东协同持股明细展开为共持边
    - board_co：同概念/同行业板块成分共板边
    """

    source = "akshare"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        ak = _require_akshare()
        if request.kind == "hot_relate":
            rows = self._hot_relate(ak, request)
        elif request.kind == "holder_team":
            rows = self._holder_team(ak, request)
        elif request.kind == "board_co":
            rows = self._board_co(ak, request)
        else:
            raise ValueError(f"未知 kind: {request.kind}")
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _hot_relate(self, ak: Any, request: FetchRequest) -> list[dict[str, Any]]:
        symbols = [_plain(s) for s in (request.symbols or []) if s.strip()]
        if not symbols:
            raise ValueError("hot_relate 需要 --symbol 或 --universe")
        asof = _asof(request)
        out: list[dict[str, Any]] = []
        for code in symbols:
            em = _em_code(code)
            try:
                df = call_with_retry(
                    lambda e=em: ak.stock_hot_rank_relate_em(symbol=e),
                    label=f"stock_hot_rank_relate_em:{em}",
                    attempts=3,
                    pause=0.2,
                    backoff=0.6,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("hot_relate %s 失败: %s", em, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_src = col_by_keywords(df.columns, ("股票代码",))
            c_dst = col_by_keywords(df.columns, ("相关股票代码", "相关"))
            c_chg = col_by_keywords(df.columns, ("涨跌幅",))
            c_time = col_by_keywords(df.columns, ("时间",))
            for _, r in df.iterrows():
                src = _plain(as_str(r[c_src]) if c_src is not None else code)
                dst = _plain(as_str(r[c_dst]) if c_dst is not None else "")
                pair = _ordered_pair(src, dst)
                if not pair:
                    continue
                a, b = pair
                chg = as_float(r[c_chg]) if c_chg is not None else None
                pt = as_str(r[c_time])[:10] if c_time is not None else asof
                day = pt[:10] if pt else asof
                eid = _event_id("HOT_RELATE", a, b, day)
                out.append(
                    {
                        "src_symbol": a,
                        "dst_symbol": b,
                        "relation_type": "HOT_RELATE",
                        "as_of_date": day,
                        "weight": abs(chg) if chg is not None else 1.0,
                        "board_name": None,
                        "holder_name": None,
                        "holder_type": None,
                        "coop_holder_name": None,
                        "extra_json": json.dumps(
                            {"src_raw": src, "dst_raw": dst, "pct_chg": chg},
                            ensure_ascii=False,
                        ),
                        "source_event_id": eid,
                        "source": self.source,
                    }
                )
        return out

    def _holder_team(self, ak: Any, request: FetchRequest) -> list[dict[str, Any]]:
        holder_type = (request.holder_type or "社保").strip()
        if holder_type not in HOLDER_TYPES:
            raise ValueError(f"非法 holder_type: {holder_type}; 允许: {HOLDER_TYPES}")
        if holder_type == "全部":
            logger.warning("holder_team=全部 分页极多，开发机不建议；将继续但可能很慢")
        want = {_plain(s) for s in (request.symbols or []) if s.strip()}
        asof = _asof(request)
        max_n = max(2, min(int(request.max_pair_stocks or 12), 20))
        try:
            df = call_with_retry(
                lambda: ak.stock_gdfx_free_holding_teamwork_em(symbol=holder_type),
                label=f"stock_gdfx_free_holding_teamwork_em:{holder_type}",
                attempts=2,
                pause=0.5,
                backoff=1.0,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("holder_team 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []

        c_holder = col_by_keywords(df.columns, ("股东名称",))
        c_htype = col_by_keywords(df.columns, ("股东类型",))
        c_coop = col_by_keywords(df.columns, ("协同股东名称",))
        c_ctype = col_by_keywords(df.columns, ("协同股东类型",))
        c_num = col_by_keywords(df.columns, ("协同次数",))
        c_detail = col_by_keywords(df.columns, ("个股详情",))

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _, r in df.iterrows():
            detail = as_str(r[c_detail]) if c_detail is not None else ""
            stocks = _parse_stock_detail(detail)[:max_n]
            if len(stocks) < 2:
                continue
            codes = [c for c, _ in stocks]
            if want:
                codes = [c for c in codes if c in want]
            if len(codes) < 2:
                continue
            weight = as_float(r[c_num]) if c_num is not None else 1.0
            holder = as_str(r[c_holder]) if c_holder is not None else ""
            coop = as_str(r[c_coop]) if c_coop is not None else ""
            htype = as_str(r[c_htype]) if c_htype is not None else holder_type
            ctype = as_str(r[c_ctype]) if c_ctype is not None else ""
            for a, b in itertools.combinations(sorted(set(codes)), 2):
                eid = _event_id("HOLDER_TEAM", a, b, holder, coop, asof)
                if eid in seen:
                    continue
                seen.add(eid)
                out.append(
                    {
                        "src_symbol": a,
                        "dst_symbol": b,
                        "relation_type": "HOLDER_TEAM",
                        "as_of_date": asof,
                        "weight": weight,
                        "board_name": None,
                        "holder_name": holder or None,
                        "holder_type": htype or holder_type,
                        "coop_holder_name": coop or None,
                        "extra_json": json.dumps(
                            {
                                "coop_holder_type": ctype or None,
                                "holder_filter": holder_type,
                            },
                            ensure_ascii=False,
                        ),
                        "source_event_id": eid,
                        "source": self.source,
                    }
                )
        return out

    def _board_co(self, ak: Any, request: FetchRequest) -> list[dict[str, Any]]:
        names = [n.strip() for n in (request.board_names or []) if n.strip()]
        if not names:
            raise ValueError("board_co 需要 --board-name（可重复）")
        want = {_plain(s) for s in (request.symbols or []) if s.strip()}
        asof = _asof(request)
        board_type = (request.board_type or "CONCEPT").upper()
        if board_type == "INDUSTRY":
            fn = getattr(ak, "stock_board_industry_cons_em", None)
            rel = "INDUSTRY_CO"
        else:
            fn = getattr(ak, "stock_board_concept_cons_em", None)
            rel = "CONCEPT_CO"
        if fn is None:
            raise RuntimeError(f"akshare 无板块成分接口 board_type={board_type}")

        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for board in names:
            try:
                df = call_with_retry(
                    lambda b=board: fn(symbol=b),
                    label=f"board_cons:{board_type}:{board}",
                    attempts=3,
                    pause=0.4,
                    backoff=0.8,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("board_co %s/%s 失败: %s", board_type, board, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_code = col_by_keywords(df.columns, ("代码", "股票代码"))
            codes: list[str] = []
            for _, r in df.iterrows():
                code = _plain(as_str(r[c_code]) if c_code is not None else "")
                if not code:
                    continue
                if want and code not in want:
                    continue
                codes.append(code)
            codes = sorted(set(codes))
            if len(codes) < 2:
                continue
            # 开发机保护：单板块最多取前 40 只做完全图
            codes = codes[:40]
            for a, b in itertools.combinations(codes, 2):
                eid = _event_id(rel, a, b, board, asof)
                if eid in seen:
                    continue
                seen.add(eid)
                out.append(
                    {
                        "src_symbol": a,
                        "dst_symbol": b,
                        "relation_type": rel,
                        "as_of_date": asof,
                        "weight": 1.0,
                        "board_name": board,
                        "holder_name": None,
                        "holder_type": None,
                        "coop_holder_name": None,
                        "extra_json": json.dumps(
                            {"board_type": board_type}, ensure_ascii=False
                        ),
                        "source_event_id": eid,
                        "source": self.source,
                    }
                )
        return out
