from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from data_ingest.alpha_announcement.models import AnnouncementRecord, FetchRequest


@dataclass
class FetchResult:
    records: list[AnnouncementRecord]
    max_publish_time: str | None = None


class AnnouncementSource(ABC):
    source: str
    channel: str

    @abstractmethod
    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        raise NotImplementedError
