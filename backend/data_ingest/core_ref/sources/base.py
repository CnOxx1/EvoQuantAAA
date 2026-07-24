from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.core_ref.models import FetchBundle, FetchRequest


class CoreRefSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
