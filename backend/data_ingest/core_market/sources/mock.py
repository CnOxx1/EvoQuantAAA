from __future__ import annotations

from datetime import date, timedelta

from data_ingest.core_market.models import FetchBundle, FetchRequest
from data_ingest.core_market.sources.base import CoreMarketSource


class MockCoreMarketSource(CoreMarketSource):
    """离线夹具：覆盖 P0 kinds。"""

    source = "mock"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        if request.kind == "equity_1d":
            rows = self._equity(request)
        elif request.kind == "adj_factor":
            rows = self._adj(request)
        elif request.kind == "suspend":
            rows = self._suspend(request)
        elif request.kind == "limit":
            rows = self._limit(request)
        elif request.kind == "index_1d":
            rows = self._index(request)
        elif request.kind == "corp_action":
            rows = self._corp(request)
        elif request.kind == "market_rank":
            rows = self._market_rank(request)
        elif request.kind == "abnormal_move":
            rows = self._abnormal_move(request)
        elif request.kind == "board_1d":
            rows = self._board_1d(request)
        elif request.kind == "equity_15m":
            rows = self._equity_min(request, freq="15m")
        elif request.kind == "equity_60m":
            rows = self._equity_min(request, freq="60m")
        else:
            raise ValueError(f"unsupported kind: {request.kind}")
        return FetchBundle(kind=request.kind, rows=rows, source=self.source)

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

    def _symbols(self, request: FetchRequest) -> list[str]:
        return request.symbols or ["600000", "000001"]

    def _equity(self, request: FetchRequest) -> list[dict]:
        rows = []
        for symbol in self._symbols(request):
            px = 10.0 if symbol.startswith("6") else 12.0
            for i, ds in enumerate(self._dates(request)):
                c = px + i * 0.1
                rows.append(
                    {
                        "symbol": symbol,
                        "trade_date": ds,
                        "open": c - 0.05,
                        "high": c + 0.1,
                        "low": c - 0.1,
                        "close": c,
                        "volume": 1_000_000 + i * 1000,
                        "amount": (c * 1_000_000),
                        "turnover": 0.5,
                        "source": self.source,
                    }
                )
        return rows

    def _adj(self, request: FetchRequest) -> list[dict]:
        rows = []
        for symbol in self._symbols(request):
            for ds in self._dates(request):
                for ft, factor in (("qfq", 1.0), ("hfq", 1.5)):
                    rows.append(
                        {
                            "symbol": symbol,
                            "trade_date": ds,
                            "factor_type": ft,
                            "factor": factor,
                            "source": self.source,
                        }
                    )
        return rows

    def _suspend(self, request: FetchRequest) -> list[dict]:
        dates = self._dates(request)
        if not dates:
            return []
        return [
            {
                "symbol": "300955",
                "trade_date": dates[-1],
                "event_type": "SUSPEND",
                "suspend_type": "连续停牌",
                "reason": "mock",
                "resume_date": None,
                "source": self.source,
            }
        ]

    def _limit(self, request: FetchRequest) -> list[dict]:
        dates = self._dates(request)
        if not dates:
            return []
        ds = dates[-1]
        return [
            {
                "symbol": "600000",
                "trade_date": ds,
                "event_type": "UP",
                "close": 11.0,
                "pct_chg": 10.0,
                "amount": 1e8,
                "first_time": "093000",
                "last_time": "093000",
                "source": self.source,
            },
            {
                "symbol": "000001",
                "trade_date": ds,
                "event_type": "DOWN",
                "close": 9.0,
                "pct_chg": -10.0,
                "amount": 2e8,
                "first_time": "140000",
                "last_time": "150000",
                "source": self.source,
            },
        ]

    def _index(self, request: FetchRequest) -> list[dict]:
        indexes = request.index_symbols or ["000300"]
        rows = []
        for idx in indexes:
            base = 4000.0
            for i, ds in enumerate(self._dates(request)):
                c = base + i
                rows.append(
                    {
                        "index_symbol": idx.split(".")[0],
                        "trade_date": ds,
                        "open": c - 5,
                        "high": c + 10,
                        "low": c - 10,
                        "close": c,
                        "volume": 1e10,
                        "amount": None,
                        "source": self.source,
                    }
                )
        return rows

    def _corp(self, request: FetchRequest) -> list[dict]:
        day = (request.end or "2026-07-16")[:10]
        return [
            {
                "symbol": "600000",
                "ex_date": day,
                "action_type": "DIVIDEND",
                "raw_payload": '{"cash_per_10":1.0,"cash":0.1}',
                "source": self.source,
            },
            {
                "symbol": "600000",
                "ex_date": day,
                "action_type": "BONUS",
                "raw_payload": '{"bonus_ratio_per_10":0.0,"transfer_ratio_per_10":5.0}',
                "source": self.source,
            },
            {
                "symbol": "600000",
                "ex_date": day,
                "action_type": "ADJ_FACTOR_CHANGE",
                "raw_payload": '{"qfq_factor":1.1,"prev_qfq_factor":1.0}',
                "source": self.source,
            },
        ]

    def _market_rank(self, request: FetchRequest) -> list[dict]:
        top_n = max(1, int(getattr(request, "top_n", None) or 100))
        rank_types = list(getattr(request, "rank_types", None) or []) or [
            "PCT_CHG_UP",
            "VOLUME",
            "AMOUNT",
        ]
        symbols = self._symbols(request)[:top_n]
        rows: list[dict] = []
        for ds in self._dates(request):
            for i, symbol in enumerate(symbols):
                base = {
                    "trade_date": ds,
                    "rank_no": i + 1,
                    "symbol": symbol,
                    "name": f"MOCK-{symbol}",
                    "close": 10.0 + i,
                    "pct_chg": 9.0 - i,
                    "volume": 1_000_000.0 - i * 1000,
                    "amount": 50_000_000.0 - i * 10_000,
                    "turnover": 5.0 - i * 0.1,
                    "extra_json": None,
                    "source": self.source,
                }
                for rt in rank_types:
                    metric = {
                        "PCT_CHG_UP": base["pct_chg"],
                        "PCT_CHG_DOWN": -base["pct_chg"],
                        "VOLUME": base["volume"],
                        "AMOUNT": base["amount"],
                        "TURNOVER": base["turnover"],
                        "HOT": float(100 - i),
                    }.get(rt, base["pct_chg"])
                    rows.append({**base, "rank_type": rt, "metric_value": metric})
        return rows

    def _abnormal_move(self, request: FetchRequest) -> list[dict]:
        day = (request.end or "2026-07-23")[:10]
        types = list(getattr(request, "change_types", None) or []) or ["火箭发射", "大笔买入"]
        symbols = self._symbols(request)
        rows: list[dict] = []
        for i, symbol in enumerate(symbols):
            for ct in types:
                rows.append(
                    {
                        "trade_date": day,
                        "event_time": f"09:30:{i:02d}",
                        "symbol": symbol,
                        "name": f"MOCK-{symbol}",
                        "change_type": ct,
                        "related_info": "mock",
                        "extra_json": None,
                        "source_event_id": f"{symbol}|{day}|{ct}|09:30:{i:02d}|{i}",
                        "source": self.source,
                    }
                )
        return rows

    def _board_1d(self, request: FetchRequest) -> list[dict]:
        names = list(request.board_names) or ["煤炭行业", "银行"]
        types = [t.upper() for t in (request.board_types or [])] or ["INDUSTRY"]
        rows: list[dict] = []
        for board_type in types:
            for name in names:
                for d in self._dates(request):
                    rows.append(
                        {
                            "board_type": board_type,
                            "board_code": "BK0001",
                            "board_name": name,
                            "trade_date": d,
                            "open": 1000.0,
                            "high": 1010.0,
                            "low": 990.0,
                            "close": 1005.0,
                            "volume": 1e8,
                            "amount": 1e10,
                            "pct_chg": 0.5,
                            "turnover": 1.2,
                            "source": self.source,
                        }
                    )
        return rows

    def _equity_min(self, request: FetchRequest, *, freq: str) -> list[dict]:
        times_15 = ("09:45:00", "10:00:00", "10:15:00", "10:30:00", "14:45:00", "15:00:00")
        times_60 = ("10:30:00", "11:30:00", "14:00:00", "15:00:00")
        slots = times_15 if freq == "15m" else times_60
        rows: list[dict] = []
        px = 10.0
        for symbol in self._symbols(request):
            for d in self._dates(request):
                for t in slots:
                    px += 0.01
                    rows.append(
                        {
                            "symbol": symbol,
                            "bar_time": f"{d} {t}",
                            "freq": freq,
                            "open": px - 0.02,
                            "high": px + 0.05,
                            "low": px - 0.05,
                            "close": px,
                            "volume": 100000.0,
                            "amount": px * 100000.0,
                            "source": self.source,
                        }
                    )
        return rows
