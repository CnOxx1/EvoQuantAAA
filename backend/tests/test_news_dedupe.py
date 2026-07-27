from __future__ import annotations

import json

from data_ingest.alpha_news_monitor.dedupe import (
    dedupe_news_records,
    map_symbols_by_name,
    normalize_title_key,
    title_hash,
)
from data_ingest.alpha_news_monitor.models import NewsRecord
from data_ingest.alpha_news_monitor.repository import lookback_watermark


def _rec(title, pub, source="a", nid="1", symbol=None):
    return NewsRecord(
        source_news_id=nid,
        title=title,
        publish_time=pub,
        channel="official",
        source=source,
        symbol=symbol,
    )


def test_normalize_and_hash():
    assert normalize_title_key("你好，世界!!!") == normalize_title_key("你好 世界")
    assert title_hash("abc") == title_hash("a b c")


def test_dedupe_keeps_earliest_and_marks_dup_sources():
    rows = [
        _rec("同一标题", "2026-07-01T10:00:00+00:00", source="sina", nid="s1"),
        _rec("同一标题", "2026-07-01T11:00:00+00:00", source="cls", nid="c1"),
    ]
    out = dedupe_news_records(rows)
    assert len(out) == 1
    assert out[0].source == "sina"
    extra = json.loads(out[0].extra_json or "{}")
    assert "cls" in extra.get("dup_sources", [])


def test_dedupe_against_recent():
    h = title_hash("已见过")
    recent = {h: {"publish_time": "2026-07-01T09:00:00+00:00", "source": "old"}}
    out = dedupe_news_records(
        [_rec("已见过", "2026-07-01T12:00:00+00:00", source="new", nid="n1")],
        recent_keys=recent,
    )
    assert out == []


def test_symbol_map():
    out = map_symbols_by_name(
        [_rec("浦发银行发布公告", "t", nid="1")],
        name_to_symbol={"浦发银行": "600000"},
    )
    assert out[0].symbol == "600000"


def test_lookback_watermark():
    wm = "2026-07-25T12:00:00+00:00"
    since = lookback_watermark(wm, hours=24)
    assert since is not None
    assert since.startswith("2026-07-24T12:00:00")
