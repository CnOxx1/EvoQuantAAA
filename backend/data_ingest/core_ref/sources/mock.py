from __future__ import annotations

from datetime import date, timedelta

from data_ingest.core_ref.models import FetchBundle, FetchRequest
from data_ingest.core_ref.sources.base import CoreRefSource


class MockCoreRefSource(CoreRefSource):
    """稳定夹具：覆盖 P0/P1 全部 kind，便于离线联调。"""

    source = "mock"

    _LISTINGS = (
        ("600000", "浦发银行", "SSE", "主板", "1999-11-10", None),
        ("000001", "平安银行", "SZSE", "主板", "1991-04-03", None),
        ("300750", "宁德时代", "SZSE", "创业板", "2018-06-11", None),
        ("601318", "中国平安", "SSE", "主板", "2007-03-01", None),
        ("600001", "邯郸钢铁", "SSE", "主板", "1998-01-22", "2009-12-21"),
    )

    def fetch(self, request: FetchRequest) -> FetchBundle:
        src = self.source
        if request.kind == "calendar":
            return FetchBundle("calendar", self._calendar(request), src)
        if request.kind == "listing":
            return FetchBundle("listing", self._listing(), src)
        if request.kind == "industry":
            return FetchBundle("industry", self._industry(request), src)
        if request.kind == "share_capital":
            return FetchBundle("share_capital", self._share_capital(), src)
        if request.kind == "index_member":
            return FetchBundle("index_member", self._index_member(request), src)
        if request.kind == "special_treat":
            return FetchBundle("special_treat", self._special_treat(), src)
        raise ValueError(f"unsupported kind: {request.kind}")

    def _calendar(self, request: FetchRequest) -> list[dict]:
        start = date.fromisoformat(request.start or "2026-07-01")
        end = date.fromisoformat(request.end or "2026-07-31")
        rows = []
        d = start
        while d <= end:
            # 简单：周末休市
            is_open = 0 if d.weekday() >= 5 else 1
            rows.append(
                {
                    "exchange": request.exchange,
                    "trade_date": d.isoformat(),
                    "is_open": is_open,
                    "is_half_day": 0,
                    "source": self.source,
                }
            )
            d += timedelta(days=1)
        return rows

    def _listing(self) -> list[dict]:
        rows = []
        for symbol, name, exchange, board, list_date, delist_date in self._LISTINGS:
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "board": board,
                    "list_date": list_date,
                    "delist_date": delist_date,
                    "effective_date": list_date,
                    "source": self.source,
                }
            )
        return rows

    def _industry(self, request: FetchRequest) -> list[dict]:
        mapping = {
            "600000": ("801780", "银行"),
            "000001": ("801780", "银行"),
            "300750": ("801080", "电力设备"),
            "601318": ("801790", "非银金融"),
            "600001": ("801050", "有色金属"),
        }
        rows = []
        for symbol, (code, name) in mapping.items():
            rows.append(
                {
                    "symbol": symbol,
                    "standard": request.industry_standard,
                    "industry_code": code,
                    "industry_name": name,
                    "effective_date": "2021-01-01",
                    "source": self.source,
                }
            )
        return rows

    def _share_capital(self) -> list[dict]:
        caps = {
            "600000": (29_352_000_000, 29_352_000_000),
            "000001": (19_406_000_000, 19_406_000_000),
            "300750": (4_400_000_000, 2_200_000_000),
            "601318": (18_210_000_000, 10_800_000_000),
            "600001": (2_800_000_000, 2_800_000_000),
        }
        rows = []
        for symbol, (total, float_) in caps.items():
            rows.append(
                {
                    "symbol": symbol,
                    "total_shares": total,
                    "float_shares": float_,
                    "effective_date": "2026-01-01",
                    "source": self.source,
                }
            )
        return rows

    def _index_member(self, request: FetchRequest) -> list[dict]:
        indexes = request.index_symbols or ["000300"]
        members = ["600000", "000001", "300750", "601318"]
        trade_date = request.end or request.start or "2026-07-24"
        weight = round(1.0 / len(members), 6)
        rows = []
        for index_symbol in indexes:
            for symbol in members:
                rows.append(
                    {
                        "index_symbol": index_symbol,
                        "symbol": symbol,
                        "trade_date": trade_date[:10],
                        "weight": weight,
                        "source": self.source,
                    }
                )
        return rows

    def _special_treat(self) -> list[dict]:
        return [
            {
                "symbol": "600001",
                "treat_type": "ST",
                "effective_date": "2008-01-01",
                "end_date": "2009-12-21",
                "source": self.source,
            }
        ]
