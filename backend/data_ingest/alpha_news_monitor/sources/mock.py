from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from data_ingest.alpha_announcement.timeutil import normalize_publish_time
from data_ingest.alpha_news_monitor.models import FetchRequest, NewsRecord
from data_ingest.alpha_news_monitor.sources.base import FetchResult, NewsSource


class MockNewsSource(NewsSource):
    source = "mock"
    channel = "mock"

    _SAMPLES = (
        ("600000", "浦发银行相关市场评论", "媒体A", "2026-07-20T02:00:00+00:00", "news"),
        ("000001", "平安银行获机构调研", "媒体B", "2026-07-21T03:00:00+00:00", "news"),
        (None, "宏观：央行公开市场操作", "财联社", "2026-07-22T04:00:00+00:00", "wire"),
    )

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        if request.kind == "news_official":
            self.channel = "official"
            return self._official(request, since=since)
        if request.kind == "news_forum":
            self.channel = "forum"
            return self._forum(request, since=since)
        if request.kind == "news_policy":
            self.channel = "policy"
            return self._policy(request, since=since)

        self.channel = "mock"
        symbols = set(request.symbols or [])
        since_n = normalize_publish_time(since) if since else None
        records: list[NewsRecord] = []
        for symbol, title, media, publish, ctype in self._SAMPLES:
            if symbols and (symbol is None or symbol not in symbols):
                continue
            pt = normalize_publish_time(publish)
            if since_n and pt <= since_n:
                continue
            nid = hashlib.sha1(f"{symbol}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    symbol=symbol,
                    title=title,
                    summary=title,
                    publish_time=pt,
                    url=f"https://example.local/news/{nid}",
                    media_source=media,
                    channel=self.channel,
                    source=self.source,
                    content_type=ctype,
                )
            )
        if request.kind in ("news_incremental", "news_watchlist") and not since_n:
            now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            symbol = (request.symbols or [None])[0]
            title = "模拟最新资讯"
            pt = now.isoformat()
            nid = hashlib.sha1(f"{symbol}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    symbol=symbol,
                    title=title,
                    summary=title,
                    publish_time=pt,
                    url=f"https://example.local/news/{nid}",
                    media_source="mock",
                    channel=self.channel,
                    source=self.source,
                    content_type="news",
                )
            )
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)

    def _official(self, request: FetchRequest, *, since: str | None) -> FetchResult:
        since_n = normalize_publish_time(since) if since else None
        samples = [
            ("cls", "财联社：模拟电报一条", "wire"),
            ("sina", "新浪：模拟财经快讯", "wire"),
            ("futu", "富途：模拟快讯", "wire"),
            ("cjzc", "财经早餐：证监会综合施策维护市场平稳", "wire"),
            ("caixin", "财新：模拟宏观要闻", "wire"),
        ]
        filters = {m.lower() for m in (request.media_filters or [])}
        records: list[NewsRecord] = []
        for media, title, ctype in samples:
            if filters and media not in filters:
                continue
            pt = normalize_publish_time("2026-07-23T08:00:00+00:00")
            if since_n and pt <= since_n:
                continue
            nid = hashlib.sha1(f"{media}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    title=title,
                    summary=title,
                    publish_time=pt,
                    media_source=media,
                    channel="official",
                    source=self.source,
                    content_type=ctype,
                    extra_json=json.dumps(
                        {"policy_tags": ["证监会"], "tone_hint": "bullish_hint"},
                        ensure_ascii=False,
                    )
                    if media == "cjzc"
                    else None,
                )
            )
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)

    def _policy(self, request: FetchRequest, *, since: str | None) -> FetchResult:
        since_n = normalize_publish_time(since) if since else None
        filters = {m.lower() for m in (request.media_filters or [])}
        samples = [
            ("cjzc", "政策早餐：央行降准预期升温", "policy", "bullish_hint", ["央行", "降准"]),
            ("caixin", "财新：监管强调风险防控", "policy", "bearish_hint", ["监管"]),
            ("epu", "中国政策不确定性指数 2026-06", "policy_index", None, []),
        ]
        records: list[NewsRecord] = []
        for media, title, ctype, tone, tags in samples:
            if filters and media not in filters:
                continue
            pt = normalize_publish_time("2026-07-23T08:00:00+00:00")
            if since_n and pt <= since_n:
                continue
            extra = {"policy_tags": tags, "tone_hint": tone}
            if media == "epu":
                extra = {"epu": 120.5, "year": 2026, "month": 6, "region": "China"}
            nid = hashlib.sha1(f"pol|{media}|{title}|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    title=title,
                    summary=title,
                    publish_time=pt,
                    media_source=media,
                    channel="policy",
                    source=self.source,
                    content_type=ctype,
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)

    def _forum(self, request: FetchRequest, *, since: str | None) -> FetchResult:
        since_n = normalize_publish_time(since) if since else None
        symbols = request.symbols or ["600000", "000001"]
        filters = {m.lower() for m in (request.media_filters or [])}
        records: list[NewsRecord] = []
        pt = normalize_publish_time("2026-07-23T15:00:00+00:00")
        if since_n and pt <= since_n:
            return FetchResult(records=[], max_publish_time=None)
        if not filters or "em_comment" in filters:
            for i, symbol in enumerate(symbols[: request.forum_top_n]):
                extra = {"score": 60.0 + i, "focus": 80.0 - i, "rank": i + 1}
                nid = hashlib.sha1(f"em|{symbol}|{pt}".encode()).hexdigest()[:16]
                records.append(
                    NewsRecord(
                        source_news_id=f"mock-{nid}",
                        symbol=symbol,
                        title=f"{symbol} 千股千评",
                        summary=json.dumps(extra, ensure_ascii=False),
                        publish_time=pt,
                        media_source="em_comment",
                        channel="forum",
                        source=self.source,
                        content_type="forum_score",
                        extra_json=json.dumps(extra, ensure_ascii=False),
                    )
                )
        if not filters or "xueqiu" in filters:
            for i, symbol in enumerate(symbols[: min(3, request.forum_top_n)]):
                extra = {"attention": 1000 - i * 10, "rank": i + 1}
                nid = hashlib.sha1(f"xq|{symbol}|{pt}".encode()).hexdigest()[:16]
                records.append(
                    NewsRecord(
                        source_news_id=f"mock-{nid}",
                        symbol=symbol,
                        title=f"{symbol} 雪球讨论热度",
                        summary=json.dumps(extra, ensure_ascii=False),
                        publish_time=pt,
                        media_source="xueqiu",
                        channel="forum",
                        source=self.source,
                        content_type="forum_heat",
                        extra_json=json.dumps(extra, ensure_ascii=False),
                    )
                )
        if not filters or "weibo" in filters:
            extra = {"rate": 0.12, "window": "CNHOUR12"}
            nid = hashlib.sha1(f"wb|茅台|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    title="茅台 微博舆情",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="weibo",
                    channel="forum",
                    source=self.source,
                    content_type="forum_score",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        if filters and "baidu_hot" in filters:
            extra = {"rank": 1, "heat": 1_000_000.0, "asof": pt[:10]}
            nid = hashlib.sha1(f"bdh|mock|{pt}".encode()).hexdigest()[:16]
            records.append(
                NewsRecord(
                    source_news_id=f"mock-{nid}",
                    title="模拟股 百度热搜",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="baidu_hot",
                    channel="forum",
                    source=self.source,
                    content_type="forum_heat",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        if filters and "baidu_vote" in filters:
            for symbol in symbols[: min(2, request.forum_top_n)]:
                extra = {"bull_pct": "60%", "bear_pct": "40%", "asof": pt[:10]}
                nid = hashlib.sha1(f"bdv|{symbol}|{pt}".encode()).hexdigest()[:16]
                records.append(
                    NewsRecord(
                        source_news_id=f"mock-{nid}",
                        symbol=symbol,
                        title=f"{symbol} 百度看涨看跌",
                        summary=json.dumps(extra, ensure_ascii=False),
                        publish_time=pt,
                        media_source="baidu_vote",
                        channel="forum",
                        source=self.source,
                        content_type="forum_score",
                        extra_json=json.dumps(extra, ensure_ascii=False),
                    )
                )
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)
