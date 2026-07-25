from __future__ import annotations

import logging
from typing import Any

import requests

from data_ingest.alpha_announcement.category import (
    cninfo_searchkey,
    matches_requested_categories,
    normalize_category,
)
from data_ingest.alpha_announcement.models import AnnouncementRecord, FetchRequest
from data_ingest.alpha_announcement.sources.base import AnnouncementSource, FetchResult
from data_ingest.alpha_announcement.timeutil import default_se_date, normalize_publish_time

logger = logging.getLogger(__name__)

CNINFO_QUERY = "http://www.cninfo.com.cn/new/hisAnnouncement/query"


def _to_cninfo_code(symbol: str) -> tuple[str, str]:
    code = symbol.split(".")[0]
    if code.startswith(("6", "9")):
        return code, "sse"
    return code, "szse"


class CninfoAnnouncementSource(AnnouncementSource):
    """巨潮资讯公告查询（公开 HTTP）。"""

    source = "cninfo"
    channel = "cninfo"

    def __init__(self, timeout: float = 15.0, lookback_days: int = 7) -> None:
        self.timeout = timeout
        self.lookback_days = lookback_days
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 ashare-quant-alpha_announcement",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "http://www.cninfo.com.cn",
                "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
            }
        )

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        records: list[AnnouncementRecord] = []
        max_pt: str | None = None
        since_n = normalize_publish_time(since) if since else None

        symbol_list = request.symbols or [None]
        for symbol in symbol_list:
            page = 1
            while page <= request.max_pages:
                payload = self._build_payload(request, symbol=symbol, page=page)
                logger.info(
                    "cninfo query symbol=%s page=%s seDate=%s",
                    symbol,
                    page,
                    payload.get("seDate"),
                )
                resp = self.session.post(CNINFO_QUERY, data=payload, timeout=self.timeout)
                resp.raise_for_status()
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise RuntimeError(
                        f"cninfo 返回非 JSON，status={resp.status_code}, body={resp.text[:200]}"
                    ) from exc
                if not isinstance(data, dict):
                    raise RuntimeError(f"cninfo 返回异常结构: {type(data)}")
                anns = data.get("announcements") or []
                if not anns:
                    logger.warning(
                        "cninfo 无公告 symbol=%s page=%s total=%s",
                        symbol,
                        page,
                        data.get("totalAnnouncement"),
                    )
                    break

                for item in anns:
                    rec = self._map_item(item)
                    if since_n and rec.publish_time <= since_n:
                        continue
                    if request.categories and not matches_requested_categories(
                        category_norm=rec.category_norm,
                        category_raw=rec.category_raw,
                        requested=request.categories,
                    ):
                        continue
                    records.append(rec)
                    if max_pt is None or rec.publish_time > max_pt:
                        max_pt = rec.publish_time

                total_pages = int(data.get("totalpages") or 1)
                if page >= total_pages:
                    break
                page += 1

        return FetchResult(records=records, max_publish_time=max_pt)

    def _build_payload(
        self, request: FetchRequest, *, symbol: str | None, page: int
    ) -> dict[str, Any]:
        stock = ""
        column = "szse"
        if symbol:
            code, column = _to_cninfo_code(symbol)
            stock = code
        se_date = default_se_date(
            request.start, request.end, lookback_days=self.lookback_days
        )
        return {
            "pageNum": page,
            "pageSize": request.page_size,
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": stock,
            "searchkey": cninfo_searchkey(request.categories),
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }

    def _map_item(self, item: dict[str, Any]) -> AnnouncementRecord:
        raw_id = item.get("announcementId") or item.get("adjId") or item.get("id")
        if raw_id is None or str(raw_id).strip() in ("", "None"):
            raise ValueError(f"cninfo 公告缺少 announcementId: {item!r}")
        title = str(item.get("announcementTitle") or "").strip() or "untitled"
        publish_time = normalize_publish_time(item.get("announcementTime"))
        category_raw = str(
            item.get("announcementTypeName") or item.get("category") or "unknown"
        )
        sec_code = item.get("secCode")
        symbol = str(sec_code) if sec_code else None
        adjunct = item.get("adjunctUrl")
        url = f"http://static.cninfo.com.cn/{adjunct}" if adjunct else None
        return AnnouncementRecord(
            source_ann_id=str(raw_id),
            symbol=symbol,
            title=title,
            publish_time=publish_time,
            category_raw=category_raw,
            category_norm=normalize_category(category_raw, title),
            url=url,
            channel=self.channel,
            source=self.source,
        )
