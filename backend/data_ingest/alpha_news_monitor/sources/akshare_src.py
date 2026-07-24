from __future__ import annotations

import hashlib
import logging
from datetime import date, timedelta
from typing import Any

from data_ingest.alpha_announcement.timeutil import normalize_publish_time
from data_ingest.alpha_news_monitor.models import FetchRequest, NewsRecord
from data_ingest.alpha_news_monitor.sources.base import FetchResult, NewsSource
from data_ingest.core_ref.sources._parse import as_str, col_by_keywords

logger = logging.getLogger(__name__)


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 akshare") from exc
    return ak


def _plain(symbol: str) -> str:
    return symbol.split(".")[0].strip()


def _news_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


class AkshareNewsSource(NewsSource):
    """
    - 增量/回填：stock_info_global_em（东财快讯）
    - 订阅：stock_news_em（个股资讯）
    - 回填补充：news_cctv（可选宏观）
    """

    source = "akshare"
    channel = "eastmoney"

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        ak = _require_akshare()
        if request.kind == "news_watchlist" or request.symbols:
            records = self._by_symbols(ak, request, since=since)
        else:
            records = self._global_em(ak, request, since=since)
            if request.kind == "news_backfill" and request.start and request.end:
                records.extend(self._cctv_backfill(ak, request, since=since))

        since_n = normalize_publish_time(since) if since else None
        if since_n:
            records = [r for r in records if r.publish_time > since_n]
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)

    def _global_em(
        self, ak: Any, request: FetchRequest, *, since: str | None
    ) -> list[NewsRecord]:
        try:
            df = ak.stock_info_global_em()
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_em 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_title = col_by_keywords(df.columns, ("标题", "title")) or df.columns[0]
        c_sum = col_by_keywords(df.columns, ("摘要", "内容"))
        c_time = col_by_keywords(df.columns, ("发布时间", "时间"))
        c_url = col_by_keywords(df.columns, ("链接", "url", "地址"))
        out: list[NewsRecord] = []
        for _, r in df.iterrows():
            title = as_str(r[c_title])
            if not title:
                continue
            try:
                pt = normalize_publish_time(r[c_time] if c_time is not None else None)
            except Exception:
                continue
            if request.start and pt[:10] < request.start[:10]:
                continue
            if request.end and pt[:10] > request.end[:10]:
                continue
            url = as_str(r[c_url]) if c_url is not None else ""
            summary = as_str(r[c_sum]) if c_sum is not None else None
            nid = _news_id("em_global", title, pt, url)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=None,
                    title=title,
                    summary=summary,
                    publish_time=pt,
                    url=url or None,
                    media_source="eastmoney_global",
                    channel=self.channel,
                    source=self.source,
                )
            )
        return out

    def _by_symbols(
        self, ak: Any, request: FetchRequest, *, since: str | None
    ) -> list[NewsRecord]:
        symbols = [_plain(s) for s in request.symbols if s.strip()]
        if not symbols:
            raise ValueError("news_watchlist 必须提供 --symbol")
        out: list[NewsRecord] = []
        for symbol in symbols:
            try:
                df = ak.stock_news_em(symbol=symbol)
            except Exception as exc:  # noqa: BLE001
                logger.warning("stock_news_em %s 失败: %s", symbol, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_title = col_by_keywords(df.columns, ("新闻标题", "标题"))
            c_sum = col_by_keywords(df.columns, ("新闻内容", "内容", "摘要"))
            c_time = col_by_keywords(df.columns, ("发布时间", "时间"))
            c_media = col_by_keywords(df.columns, ("文章来源", "来源"))
            c_url = col_by_keywords(df.columns, ("新闻链接", "链接", "地址"))
            for _, r in df.iterrows():
                title = as_str(r[c_title]) if c_title is not None else ""
                if not title:
                    continue
                try:
                    pt = normalize_publish_time(r[c_time] if c_time is not None else None)
                except Exception:
                    continue
                if request.start and pt[:10] < request.start[:10]:
                    continue
                if request.end and pt[:10] > request.end[:10]:
                    continue
                url = as_str(r[c_url]) if c_url is not None else ""
                nid = _news_id("em_stock", symbol, title, pt, url)
                out.append(
                    NewsRecord(
                        source_news_id=nid,
                        symbol=symbol,
                        title=title,
                        summary=as_str(r[c_sum]) if c_sum is not None else None,
                        publish_time=pt,
                        url=url or None,
                        media_source=as_str(r[c_media]) if c_media is not None else None,
                        channel=self.channel,
                        source=self.source,
                    )
                )
        return out

    def _cctv_backfill(
        self, ak: Any, request: FetchRequest, *, since: str | None
    ) -> list[NewsRecord]:
        start = date.fromisoformat(request.start[:10])
        end = date.fromisoformat(request.end[:10])
        out: list[NewsRecord] = []
        d = start
        while d <= end:
            ymd = d.strftime("%Y%m%d")
            try:
                df = ak.news_cctv(date=ymd)
            except Exception as exc:  # noqa: BLE001
                logger.warning("news_cctv %s 失败: %s", ymd, exc)
                d += timedelta(days=1)
                continue
            if df is not None and not getattr(df, "empty", True):
                c_title = col_by_keywords(df.columns, ("title", "标题")) or df.columns[1]
                c_content = col_by_keywords(df.columns, ("content", "内容"))
                for _, r in df.iterrows():
                    title = as_str(r[c_title])
                    if not title:
                        continue
                    pt = normalize_publish_time(f"{d.isoformat()} 19:00:00")
                    nid = _news_id("cctv", ymd, title)
                    out.append(
                        NewsRecord(
                            source_news_id=nid,
                            symbol=None,
                            title=title,
                            summary=as_str(r[c_content])[:500] if c_content else None,
                            publish_time=pt,
                            url=None,
                            media_source="cctv",
                            channel="cctv",
                            source=self.source,
                        )
                    )
            d += timedelta(days=1)
        return out
