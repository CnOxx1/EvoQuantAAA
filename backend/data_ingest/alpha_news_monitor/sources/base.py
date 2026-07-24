from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from data_ingest.alpha_news_monitor.models import FetchRequest, NewsRecord


@dataclass
class FetchResult:
    records: list[NewsRecord]
    max_publish_time: str | None


class NewsSource(ABC):
    source: str
    channel: str

    @abstractmethod
    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        raise NotImplementedError
