from __future__ import annotations

"""新闻标题规范化去重（纯函数，不连库）。"""

import hashlib
import json
import re
from typing import Any

from data_ingest.alpha_news_monitor.models import NewsRecord

_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize_title_key(title: str, *, n: int = 40) -> str:
    s = _PUNCT_RE.sub("", (title or "").strip().lower())
    return s[:n]


def title_hash(title: str) -> str:
    key = normalize_title_key(title)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] if key else ""


def _merge_extra(extra_json: str | None, *, dup_sources: list[str]) -> str:
    try:
        data = json.loads(extra_json) if extra_json else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    existing = data.get("dup_sources") or []
    if not isinstance(existing, list):
        existing = []
    merged = list(dict.fromkeys([*existing, *dup_sources]))
    if merged:
        data["dup_sources"] = merged
    return json.dumps(data, ensure_ascii=False)


def dedupe_news_records(
    records: list[NewsRecord],
    *,
    recent_keys: dict[str, dict[str, Any]] | None = None,
) -> list[NewsRecord]:
    """
    同批 + 近窗已入库：normalize(title)[:40] 相同视为重复。
    保留最早 publish_time；重复源写入 extra_json.dup_sources。
    recent_keys: hash -> {publish_time, source, source_news_id}
    """
    recent = recent_keys or {}
    best: dict[str, NewsRecord] = {}
    dups: dict[str, list[str]] = {}

    ordered = sorted(records, key=lambda r: (r.publish_time or "", r.source_news_id))
    for r in ordered:
        h = title_hash(r.title)
        if not h:
            best[f"empty:{r.source_news_id}:{r.source}"] = r
            continue
        if h in recent:
            # 已入库更早或同文：丢弃本条，但记 dup
            dups.setdefault(h, []).append(str(r.source))
            continue
        if h not in best:
            best[h] = r
            continue
        cur = best[h]
        # 已有更早：当前为重复源
        dups.setdefault(h, []).append(str(r.source))
        _ = cur  # keep earliest already in best

    out: list[NewsRecord] = []
    for key, r in best.items():
        if key.startswith("empty:"):
            out.append(r)
            continue
        h = key
        extras = dups.get(h) or []
        if extras:
            out.append(
                NewsRecord(
                    source_news_id=r.source_news_id,
                    title=r.title,
                    publish_time=r.publish_time,
                    channel=r.channel,
                    source=r.source,
                    symbol=r.symbol,
                    summary=r.summary,
                    url=r.url,
                    media_source=r.media_source,
                    content_type=r.content_type,
                    extra_json=_merge_extra(r.extra_json, dup_sources=extras),
                )
            )
        else:
            out.append(r)
    return out


def map_symbols_by_name(
    records: list[NewsRecord],
    *,
    name_to_symbol: dict[str, str],
) -> list[NewsRecord]:
    """标题包含股票简称时回填 symbol（已有 symbol 不覆盖）。"""
    if not name_to_symbol:
        return records
    # 长名优先，避免短串误伤
    names = sorted(name_to_symbol.keys(), key=len, reverse=True)
    out: list[NewsRecord] = []
    for r in records:
        if r.symbol:
            out.append(r)
            continue
        title = r.title or ""
        hit = None
        for name in names:
            if name and name in title:
                hit = name_to_symbol[name]
                break
        if hit:
            out.append(
                NewsRecord(
                    source_news_id=r.source_news_id,
                    title=r.title,
                    publish_time=r.publish_time,
                    channel=r.channel,
                    source=r.source,
                    symbol=hit,
                    summary=r.summary,
                    url=r.url,
                    media_source=r.media_source,
                    content_type=r.content_type,
                    extra_json=r.extra_json,
                )
            )
        else:
            out.append(r)
    return out
