from data_ingest.alpha_announcement.sources.base import AnnouncementSource
from data_ingest.alpha_announcement.sources.cninfo import CninfoAnnouncementSource
from data_ingest.alpha_announcement.sources.eastmoney import EastmoneyAnnouncementSource
from data_ingest.alpha_announcement.sources.mock import MockAnnouncementSource


def get_source(name: str) -> AnnouncementSource:
    key = (name or "eastmoney").lower()
    if key == "mock":
        return MockAnnouncementSource()
    if key == "cninfo":
        return CninfoAnnouncementSource()
    if key in {"eastmoney", "akshare"}:
        return EastmoneyAnnouncementSource()
    raise ValueError(f"未知公告源: {name}")


__all__ = [
    "AnnouncementSource",
    "CninfoAnnouncementSource",
    "EastmoneyAnnouncementSource",
    "MockAnnouncementSource",
    "get_source",
]
