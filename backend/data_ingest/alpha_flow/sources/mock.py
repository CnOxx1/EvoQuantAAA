from __future__ import annotations

import json
from datetime import date, timedelta

from data_ingest.alpha_flow.models import FetchBundle, FetchRequest
from data_ingest.alpha_flow.sources.base import FlowSource


class MockFlowSource(FlowSource):
    source = "mock"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        dispatch = {
            "northbound": self._northbound,
            "stock_flow": self._stock_flow,
            "margin": self._margin,
            "dragon_tiger": self._dragon,
            "block_trade": self._block,
        }
        if request.kind not in dispatch:
            raise ValueError(f"unsupported kind: {request.kind}")
        return FetchBundle(
            kind=request.kind, rows=dispatch[request.kind](request), source=self.source
        )

    def _dates(self, request: FetchRequest) -> list[str]:
        start = date.fromisoformat(request.start or "2026-07-21")
        end = date.fromisoformat(request.end or "2026-07-23")
        out: list[str] = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                out.append(d.isoformat())
            d += timedelta(days=1)
        return out

    def _northbound(self, request: FetchRequest) -> list[dict]:
        rows = []
        for ds in self._dates(request):
            for ft, net in (("NORTHBOUND", 1e8), ("NORTHBOUND_SH", 6e7), ("NORTHBOUND_SZ", 4e7)):
                rows.append(
                    {
                        "scope": "MARKET",
                        "trade_date": ds,
                        "flow_type": ft,
                        "net_amount": net,
                        "buy_amount": net * 2,
                        "sell_amount": net,
                        "extra_json": None,
                        "source": self.source,
                    }
                )
        return rows

    def _stock_flow(self, request: FetchRequest) -> list[dict]:
        symbols = request.symbols or ["600000", "000001"]
        rows = []
        for symbol in symbols:
            for ds in self._dates(request):
                rows.append(
                    {
                        "scope": symbol,
                        "trade_date": ds,
                        "flow_type": "STOCK_FLOW",
                        "net_amount": 1e7,
                        "buy_amount": 3e7,
                        "sell_amount": 2e7,
                        "extra_json": json.dumps({"main_net": 1e7}),
                        "source": self.source,
                    }
                )
        return rows

    def _margin(self, request: FetchRequest) -> list[dict]:
        rows = []
        for ds in self._dates(request):
            rows.append(
                {
                    "symbol": "MARKET_SSE",
                    "trade_date": ds,
                    "rzye": 1.5e12,
                    "rqye": 2.5e9,
                    "rzmre": 1.5e11,
                    "rqyl": 6e7,
                    "rzche": None,
                    "rqchl": None,
                    "rzrqye": 1.52e12,
                    "source": self.source,
                }
            )
        return rows

    def _dragon(self, request: FetchRequest) -> list[dict]:
        ds = self._dates(request)[-1] if self._dates(request) else "2026-07-23"
        return [
            {
                "symbol": "000078",
                "trade_date": ds,
                "reason": "mock",
                "close": 1.58,
                "pct_chg": -10.0,
                "net_amount": -9e6,
                "buy_amount": 2e7,
                "sell_amount": 3e7,
                "source_event_id": f"000078|{ds}|mock",
                "source": self.source,
            }
        ]

    def _block(self, request: FetchRequest) -> list[dict]:
        ds = self._dates(request)[-1] if self._dates(request) else "2026-07-22"
        return [
            {
                "symbol": "000012",
                "trade_date": ds,
                "price": 3.75,
                "volume": 2.8e7,
                "amount": 1.05e8,
                "premium_rate": 0.0,
                "buyer": "mock_buyer",
                "seller": "mock_seller",
                "source_event_id": f"000012|{ds}|3.75|28000000",
                "source": self.source,
            }
        ]
