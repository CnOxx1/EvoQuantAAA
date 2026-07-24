from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.alpha_fundamental.models import FetchBundle, FetchRequest


class FundamentalSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
