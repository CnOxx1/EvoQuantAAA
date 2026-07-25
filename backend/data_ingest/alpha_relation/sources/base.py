from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.alpha_relation.models import FetchBundle, FetchRequest


class RelationSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
