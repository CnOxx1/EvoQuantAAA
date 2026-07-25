from __future__ import annotations

from abc import ABC, abstractmethod

from data_ingest.alpha_contract.models import FetchBundle, FetchRequest


class ContractSource(ABC):
    source: str

    @abstractmethod
    def fetch(self, request: FetchRequest) -> FetchBundle:
        raise NotImplementedError
