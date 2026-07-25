from __future__ import annotations

from collections import defaultdict
from typing import Any

from data_quality.models import RuleOutcome


def run_alpha_rules(
    *,
    valuation_rows: list[dict[str, Any]],
    money_flow_rows: list[dict[str, Any]],
    news_rows: list[dict[str, Any]],
) -> list[RuleOutcome]:
    return [
        _valuation_null_rate(valuation_rows),
        _valuation_dup_keys(valuation_rows),
        _flow_null_rate(money_flow_rows),
        _flow_dup_keys(money_flow_rows),
        _news_publish_vs_ingest(news_rows),
        _news_dup_title_day(news_rows),
    ]


def _valuation_null_rate(rows: list[dict[str, Any]]) -> RuleOutcome:
    if not rows:
        return RuleOutcome(
            rule_code="valuation_nonempty",
            severity="warn",
            status="pass",
            message="无估值行，跳过",
            detail={"skipped": True},
        )
    nulls = sum(1 for r in rows if r.get("pe_ttm") is None)
    rate = nulls / len(rows)
    ok = rate <= 0.5
    return RuleOutcome(
        rule_code="valuation_pe_null_rate",
        severity="warn",
        status="pass" if ok else "fail",
        message=f"pe_ttm 空值率 {rate:.2%}",
        detail={"rows": len(rows), "nulls": nulls, "rate": rate},
    )


def _valuation_dup_keys(rows: list[dict[str, Any]]) -> RuleOutcome:
    seen: set[tuple[str, str]] = set()
    dups = 0
    for r in rows:
        key = (str(r["symbol"]), str(r["trade_date"])[:10])
        if key in seen:
            dups += 1
        seen.add(key)
    ok = dups == 0
    return RuleOutcome(
        rule_code="valuation_dup_symbol_date",
        severity="warn",
        status="pass" if ok else "fail",
        message="估值键无重复" if ok else f"重复键 {dups}",
        detail={"dups": dups},
    )


def _flow_null_rate(rows: list[dict[str, Any]]) -> RuleOutcome:
    if not rows:
        return RuleOutcome(
            rule_code="flow_nonempty",
            severity="warn",
            status="pass",
            message="无资金流行，跳过",
            detail={"skipped": True},
        )
    nulls = sum(1 for r in rows if r.get("net_amount") is None)
    rate = nulls / len(rows)
    ok = rate <= 0.3
    return RuleOutcome(
        rule_code="flow_net_null_rate",
        severity="warn",
        status="pass" if ok else "fail",
        message=f"net_amount 空值率 {rate:.2%}",
        detail={"rows": len(rows), "nulls": nulls, "rate": rate},
    )


def _flow_dup_keys(rows: list[dict[str, Any]]) -> RuleOutcome:
    seen: set[tuple[str, str, str, str]] = set()
    dups = 0
    for r in rows:
        key = (
            str(r.get("scope")),
            str(r["trade_date"])[:10],
            str(r.get("flow_type")),
            str(r.get("source")),
        )
        if key in seen:
            dups += 1
        seen.add(key)
    ok = dups == 0
    return RuleOutcome(
        rule_code="flow_dup_keys",
        severity="warn",
        status="pass" if ok else "fail",
        message="资金流键无重复" if ok else f"重复键 {dups}",
        detail={"dups": dups},
    )


def _news_publish_vs_ingest(rows: list[dict[str, Any]]) -> RuleOutcome:
    bad = []
    for r in rows:
        pub = str(r.get("publish_time") or "")
        ing = str(r.get("ingested_at") or "")
        if pub and ing and pub > ing:
            bad.append({"id": r.get("source_news_id") or r.get("id"), "publish_time": pub})
    ok = not bad
    return RuleOutcome(
        rule_code="news_publish_before_ingest",
        severity="warn",
        status="pass" if ok else "fail",
        message="新闻点时不晚于入库" if ok else f"publish>ingested {len(bad)} 条",
        detail={"bad_count": len(bad), "sample": bad[:10]},
    )


def _news_dup_title_day(rows: list[dict[str, Any]]) -> RuleOutcome:
    """同日同标题重复（粗检）。"""
    buckets: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        title = str(r.get("title") or "").strip()[:40]
        day = str(r.get("publish_time") or "")[:10]
        if not title or not day:
            continue
        buckets[(day, title)] += 1
    dups = sum(1 for n in buckets.values() if n > 1)
    ok = dups == 0
    return RuleOutcome(
        rule_code="news_dup_title_day",
        severity="warn",
        status="pass" if ok else "fail",
        message="新闻标题日无重复" if ok else f"重复标题日组 {dups}",
        detail={"dup_groups": dups},
    )
