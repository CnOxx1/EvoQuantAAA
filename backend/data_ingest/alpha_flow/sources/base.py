from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.alpha_flow.models import FetchBundle, FetchRequest


class FlowSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
