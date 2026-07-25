from __future__ import annotations

"""基本面 PIT：按公告日（announce_date）构造可见区间快照。"""

import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any


_ITEM_MAP = {
    "OPERATE_INCOME": "revenue",
    "营业收入": "revenue",
    "NETPROFIT": "net_profit",
    "净利润": "net_profit",
    "TOTAL_ASSETS": "total_assets",
    "资产总计": "total_assets",
    "TOTAL_LIABILITIES": "total_liabilities",
    "负债合计": "total_liabilities",
}

_IND_MAP = {
    "roe": "roe",
    "ROE": "roe",
    "eps": "eps",
    "EPS": "eps",
}


def _day_before(d: str) -> str:
    return (date.fromisoformat(d[:10]) - timedelta(days=1)).isoformat()


def build_fund_pit_intervals(
    *,
    statement_rows: list[dict[str, Any]],
    indicator_rows: list[dict[str, Any]],
    process_batch_id: str,
    processed_at: str,
) -> list[dict[str, Any]]:
    """
    对每个标的按 announce_date 排序事件；
    valid_from=announce_date，valid_to=下一次公告前一日（末条 open）。
    同日多报告期取 report_period 最大者；更正（更晚公告）覆盖此前可见集。
    """
    # (symbol, announce_date, report_period) -> metrics
    events: dict[tuple[str, str, str], dict[str, Any]] = {}

    for r in statement_rows:
        ann = (r.get("announce_date") or "")[:10]
        if not ann:
            continue
        sym = str(r["symbol"])
        period = str(r["report_period"])[:10]
        key = (sym, ann, period)
        slot = events.setdefault(
            key,
            {
                "symbol": sym,
                "publish_date": ann,
                "report_period": period,
                "metrics": {},
                "source": str(r.get("source") or ""),
            },
        )
        code = str(r.get("item_code") or "")
        field = _ITEM_MAP.get(code)
        if field and r.get("item_value") is not None:
            slot["metrics"][field] = float(r["item_value"])
        slot["metrics"][f"stmt:{r.get('statement_type')}:{code}"] = r.get("item_value")

    for r in indicator_rows:
        ann = (r.get("announce_date") or "")[:10]
        if not ann:
            continue
        sym = str(r["symbol"])
        period = str(r["report_period"])[:10]
        key = (sym, ann, period)
        slot = events.setdefault(
            key,
            {
                "symbol": sym,
                "publish_date": ann,
                "report_period": period,
                "metrics": {},
                "source": str(r.get("source") or ""),
            },
        )
        code = str(r.get("indicator_code") or "")
        field = _IND_MAP.get(code)
        if field and r.get("indicator_value") is not None:
            slot["metrics"][field] = float(r["indicator_value"])
        slot["metrics"][f"ind:{code}"] = r.get("indicator_value")

    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in events.values():
        by_sym[ev["symbol"]].append(ev)

    out: list[dict[str, Any]] = []
    for sym, evs in by_sym.items():
        # 同 announce_date 保留 report_period 最大
        by_ann: dict[str, dict[str, Any]] = {}
        for ev in sorted(evs, key=lambda e: (e["publish_date"], e["report_period"])):
            by_ann[ev["publish_date"]] = ev
        ordered = [by_ann[d] for d in sorted(by_ann.keys())]
        for i, ev in enumerate(ordered):
            valid_from = ev["publish_date"]
            valid_to = None
            if i + 1 < len(ordered):
                valid_to = _day_before(ordered[i + 1]["publish_date"])
                if valid_to < valid_from:
                    valid_to = valid_from
            m = ev["metrics"]
            out.append(
                {
                    "process_batch_id": process_batch_id,
                    "symbol": sym,
                    "report_period": ev["report_period"],
                    "publish_date": ev["publish_date"],
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "revenue": m.get("revenue"),
                    "net_profit": m.get("net_profit"),
                    "total_assets": m.get("total_assets"),
                    "total_liabilities": m.get("total_liabilities"),
                    "roe": m.get("roe"),
                    "eps": m.get("eps"),
                    "metrics_json": json.dumps(m, ensure_ascii=False),
                    "source": ev.get("source") or "mixed",
                    "processed_at": processed_at,
                }
            )
    out.sort(key=lambda r: (r["symbol"], r["valid_from"]))
    return out


def lookup_fund_asof(
    intervals: list[dict[str, Any]], *, symbol: str, as_of: str
) -> dict[str, Any] | None:
    """研究侧辅助：区间 join（valid_from <= as_of <= valid_to 或 valid_to 空）。"""
    d = as_of[:10]
    best = None
    for r in intervals:
        if r["symbol"] != symbol:
            continue
        vf = str(r["valid_from"])[:10]
        vt = r.get("valid_to")
        if vf > d:
            continue
        if vt is not None and str(vt)[:10] < d:
            continue
        if best is None or vf > str(best["valid_from"])[:10]:
            best = r
    return best
