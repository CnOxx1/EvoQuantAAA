from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.core_market.models import FetchBundle, FetchRequest


class CoreMarketSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
