from __future__ import annotations

from data_ingest.alpha_fundamental.models import FetchBundle, FetchRequest
from data_ingest.alpha_fundamental.sources.base import FundamentalSource


class MockFundamentalSource(FundamentalSource):
    source = "mock"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        if request.kind == "statement":
            rows = self._statement(request)
        elif request.kind == "indicator":
            rows = self._indicator(request)
        elif request.kind == "consensus":
            rows = self._consensus(request)
        elif request.kind == "valuation":
            rows = self._valuation(request)
        elif request.kind == "holder":
            rows = self._holder(request)
        else:
            raise ValueError(f"unsupported kind: {request.kind}")
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

    def _symbols(self, request: FetchRequest) -> list[str]:
        return request.symbols or ["600000", "000001"]

    def _statement(self, request: FetchRequest) -> list[dict]:
        types = request.statement_types or ["INCOME", "BALANCE", "CASHFLOW"]
        periods = [("2025-12-31", "2026-03-31"), ("2026-03-31", "2026-04-30")]
        items = {
            "INCOME": [("OPERATE_INCOME", 1e10), ("NETPROFIT", 1e9)],
            "BALANCE": [("TOTAL_ASSETS", 5e11), ("TOTAL_LIABILITIES", 4e11)],
            "CASHFLOW": [("NETCASH_OPERATE", 2e9), ("END_CCE", 3e9)],
        }
        rows = []
        for symbol in self._symbols(request):
            for st in types:
                for report_period, announce_date in periods:
                    for code, val in items[st]:
                        rows.append(
                            {
                                "symbol": symbol,
                                "statement_type": st,
                                "report_period": report_period,
                                "announce_date": announce_date,
                                "item_code": code,
                                "item_value": val,
                                "currency": "CNY",
                                "report_type": "mock",
                                "source": self.source,
                            }
                        )
        return rows

    def _indicator(self, request: FetchRequest) -> list[dict]:
        rows = []
        for symbol in self._symbols(request):
            for period, ann in (("2025-12-31", "2026-03-31"), ("2026-03-31", "2026-04-30")):
                for code, val in (("roe", 12.5), ("eps", 1.2), ("debt_ratio", 55.0)):
                    rows.append(
                        {
                            "symbol": symbol,
                            "report_period": period,
                            "announce_date": ann,
                            "indicator_code": code,
                            "indicator_value": val,
                            "source": self.source,
                        }
                    )
        return rows

    def _consensus(self, request: FetchRequest) -> list[dict]:
        asof = (request.end or "2026-07-24")[:10]
        rows = []
        for symbol in self._symbols(request):
            for year, eps in (("2026", 1.5), ("2027", 1.7)):
                rows.append(
                    {
                        "symbol": symbol,
                        "asof_date": asof,
                        "metric": "EPS",
                        "period_year": year,
                        "value": eps,
                        "version": "latest",
                        "source": self.source,
                    }
                )
        return rows

    def _valuation(self, request: FetchRequest) -> list[dict]:
        day = (request.end or request.start or "2026-07-23")[:10]
        rows = []
        for symbol in self._symbols(request):
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": day,
                    "close": 100.0,
                    "pe_ttm": 15.0,
                    "pe_static": 14.0,
                    "pb": 2.0,
                    "ps_ttm": 3.0,
                    "pcf_ttm": 10.0,
                    "peg": 1.1,
                    "total_mv": 1e11,
                    "float_mv": 8e10,
                    "total_shares": 1e9,
                    "float_shares": 8e8,
                    "source": self.source,
                }
            )
        return rows

    def _holder(self, request: FetchRequest) -> list[dict]:
        asof = (request.end or "2026-06-30")[:10]
        rows = []
        for symbol in self._symbols(request):
            rows.append(
                {
                    "symbol": symbol,
                    "asof_date": asof,
                    "announce_date": asof,
                    "holder_count": 100000.0,
                    "holder_count_prev": 105000.0,
                    "holder_change": -5000.0,
                    "holder_change_pct": -4.76,
                    "avg_market_cap": 5e5,
                    "avg_shares": 5000.0,
                    "total_mv": 5e10,
                    "total_shares": 5e8,
                    "source": self.source,
                }
            )
        return rows
