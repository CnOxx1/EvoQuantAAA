from __future__ import annotations

from data_ingest.alpha_contract.models import FetchBundle, FetchRequest
from data_ingest.alpha_contract.sources.base import ContractSource


class MockContractSource(ContractSource):
    source = "mock"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        want = {s.strip() for s in (request.symbols or []) if s.strip()}
        samples = [
            {
                "symbol": "600284",
                "name": "浦东建设",
                "announce_date": "2026-07-24",
                "sign_date": None,
                "contract_type": "项目中标",
                "contract_name": "模拟道路工程中标合同",
                "amount": 10_501_400.0,
                "revenue_prev_year": None,
                "amount_rev_ratio": None,
                "revenue_latest": 1.8e9,
                "party_self": "上海浦东建设公司",
                "party_self_relation": "本公司子公司",
                "party_other": "某业主单位",
                "party_other_relation": None,
                "is_win_bid": 1,
                "source_event_id": "mock-win-600284-20260724",
                "source": self.source,
            },
            {
                "symbol": "002428",
                "name": "云南锗业",
                "announce_date": "2026-07-24",
                "sign_date": None,
                "contract_type": "销售合同",
                "contract_name": "模拟销售协议",
                "amount": None,
                "revenue_prev_year": None,
                "amount_rev_ratio": None,
                "revenue_latest": None,
                "party_self": "云南锗业股份有限公司",
                "party_self_relation": "本公司",
                "party_other": "客户",
                "party_other_relation": "无关联关系",
                "is_win_bid": 0,
                "source_event_id": "mock-sale-002428-20260724",
                "source": self.source,
            },
        ]
        rows = []
        for r in samples:
            if want and r["symbol"] not in want:
                continue
            day = r["announce_date"]
            if request.start and day < request.start[:10]:
                continue
            if request.end and day > request.end[:10]:
                continue
            if request.kind == "win_bid" and not r["is_win_bid"]:
                continue
            rows.append(dict(r))
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)
