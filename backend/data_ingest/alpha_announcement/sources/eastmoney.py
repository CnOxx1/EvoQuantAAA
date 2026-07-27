from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from data_ingest.alpha_announcement.category import (
    matches_requested_categories,
    normalize_category,
)
from data_ingest.alpha_announcement.models import AnnouncementRecord, FetchRequest
from data_ingest.alpha_announcement.sources.base import AnnouncementSource, FetchResult
from shared.timeutil import normalize_publish_time

logger = logging.getLogger(__name__)


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未安装 akshare，请执行: pip install -r requirements.txt"
        ) from exc
    return ak


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _col(df: Any, *keys: str) -> Any | None:
    for c in df.columns:
        cs = str(c)
        if any(k in cs for k in keys):
            return c
    return None


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _parse_day(text: str | None, default: date) -> date:
    if not text:
        return default
    t = text.strip().replace("/", "-")
    if len(t) >= 10 and t[4] == "-":
        return date.fromisoformat(t[:10])
    if len(t) == 8 and t.isdigit():
        return date(int(t[:4]), int(t[4:6]), int(t[6:8]))
    return default


class EastmoneyAnnouncementSource(AnnouncementSource):
    """
    东方财富公告（经 akshare）。

    - 全市场按日：stock_notice_report（增量 / 分类）
    - 个股区间：stock_individual_notice_report（订阅 / 回填）
    """

    source = "eastmoney"
    channel = "eastmoney"

    def __init__(self, *, lookback_days: int = 3) -> None:
        self.lookback_days = lookback_days

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        ak = _require_akshare()
        if request.symbols:
            records = self._fetch_by_symbols(ak, request, since=since)
        else:
            records = self._fetch_market_days(ak, request, since=since)

        if request.categories:
            records = [
                r
                for r in records
                if matches_requested_categories(
                    category_norm=r.category_norm,
                    category_raw=r.category_raw,
                    requested=request.categories,
                )
            ]

        max_pt = None
        for r in records:
            if max_pt is None or r.publish_time > max_pt:
                max_pt = r.publish_time
        return FetchResult(records=records, max_publish_time=max_pt)

    def _date_range(self, request: FetchRequest, *, since: str | None) -> list[date]:
        today = date.today()
        end = _parse_day(request.end, today)
        if request.start:
            start = _parse_day(request.start, end - timedelta(days=self.lookback_days))
        elif since:
            start = _parse_day(since[:10], end - timedelta(days=self.lookback_days))
        else:
            start = end - timedelta(days=self.lookback_days)
        if start > end:
            start, end = end, start
        # 防止一次拉过长
        if (end - start).days > 31:
            start = end - timedelta(days=31)
        days: list[date] = []
        d = start
        while d <= end:
            days.append(d)
            d += timedelta(days=1)
        return days

    def _fetch_market_days(
        self, ak: Any, request: FetchRequest, *, since: str | None
    ) -> list[AnnouncementRecord]:
        records: list[AnnouncementRecord] = []
        since_n = normalize_publish_time(since) if since else None
        for day in self._date_range(request, since=since):
            ymd = _ymd(day)
            logger.info("eastmoney market notices date=%s", ymd)
            try:
                df = ak.stock_notice_report(symbol="全部", date=ymd)
            except Exception as exc:  # noqa: BLE001
                logger.warning("eastmoney notice %s 失败: %s", ymd, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            for rec in self._map_df(df):
                if since_n and rec.publish_time <= since_n:
                    continue
                records.append(rec)
        return records

    def _fetch_by_symbols(
        self, ak: Any, request: FetchRequest, *, since: str | None
    ) -> list[AnnouncementRecord]:
        today = date.today()
        end = _parse_day(request.end, today)
        if request.start:
            begin = _parse_day(request.start, end - timedelta(days=30))
        elif since:
            begin = _parse_day(since[:10], end - timedelta(days=self.lookback_days))
        else:
            begin = end - timedelta(days=self.lookback_days)
        begin_s, end_s = _ymd(begin), _ymd(end)
        since_n = normalize_publish_time(since) if since else None
        records: list[AnnouncementRecord] = []
        for symbol in request.symbols or []:
            code = symbol.split(".")[0]
            logger.info(
                "eastmoney individual notices symbol=%s %s~%s", code, begin_s, end_s
            )
            try:
                df = ak.stock_individual_notice_report(
                    security=code,
                    symbol="全部",
                    begin_date=begin_s,
                    end_date=end_s,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("eastmoney individual %s 失败: %s", code, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            for rec in self._map_df(df, default_symbol=code):
                if since_n and rec.publish_time <= since_n:
                    continue
                records.append(rec)
        return records

    def _map_df(
        self, df: Any, *, default_symbol: str | None = None
    ) -> list[AnnouncementRecord]:
        c_code = _col(df, "代码")
        c_name = _col(df, "名称", "简称")
        c_title = _col(df, "标题", "公告标题")
        c_type = _col(df, "类型", "公告类型")
        c_date = _col(df, "日期", "公告日期", "发布时间")
        c_url = _col(df, "地址", "链接", "url", "URL")

        out: list[AnnouncementRecord] = []
        for _, r in df.iterrows():
            title = _as_str(r[c_title]) if c_title is not None else ""
            if not title:
                continue
            symbol = (
                _as_str(r[c_code]) if c_code is not None else (default_symbol or "")
            ) or default_symbol
            publish_raw = _as_str(r[c_date]) if c_date is not None else ""
            if not publish_raw:
                continue
            # 东财常为日期；归一到点时
            if len(publish_raw) == 10:
                publish_raw = f"{publish_raw} 00:00:00"
            publish_time = normalize_publish_time(publish_raw)
            category_raw = _as_str(r[c_type]) if c_type is not None else "unknown"
            url = _as_str(r[c_url]) if c_url is not None else None
            # 稳定幂等键：代码+标题+时间
            source_ann_id = f"{symbol or 'NA'}|{publish_time}|{title}"
            out.append(
                AnnouncementRecord(
                    source_ann_id=source_ann_id[:240],
                    symbol=symbol,
                    title=title,
                    publish_time=publish_time,
                    category_raw=category_raw or "unknown",
                    category_norm=normalize_category(category_raw, title),
                    url=url or None,
                    channel=self.channel,
                    source=self.source,
                )
            )
        return out
