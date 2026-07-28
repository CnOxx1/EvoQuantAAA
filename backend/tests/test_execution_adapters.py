from __future__ import annotations

from execution.adapters import get_adapter, list_adapters
from execution.adapters.base import AdapterContext
from execution.adapters.broker_stub import REJECT_REASON
from execution.models import CostSnapshot
from execution.paper import build_paper_intents


def _cost(**kwargs) -> CostSnapshot:
    base = dict(
        version="t",
        commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        slippage_rate=0.0,
        lot_size=100,
    )
    base.update(kwargs)
    return CostSnapshot(**base)


def test_registry_has_paper_and_stub():
    kinds = {r["kind"] for r in list_adapters()}
    assert kinds == {"broker_stub", "paper"}
    assert get_adapter("paper").kind == "paper"
    assert get_adapter("broker_stub").kind == "broker_stub"


def test_unknown_adapter_raises():
    try:
        get_adapter("ctp_live")
        assert False, "expected KeyError"
    except KeyError as exc:
        assert "ctp_live" in str(exc)


def test_broker_stub_rejects_without_fills():
    intents = build_paper_intents(
        positions=[
            {"symbol": "A", "target_shares": 200, "price": 10.0, "can_buy": 1}
        ],
        current_shares={},
    )
    assert any(not i.get("reject") for i in intents)
    orders, fills = get_adapter("broker_stub").execute(
        intents,
        AdapterContext(cost=_cost(), trade_date="2026-07-28", cash=100_000),
    )
    assert fills == []
    assert orders
    assert all(o["status"] == "REJECTED" for o in orders)
    assert any(o.get("reason") == REJECT_REASON for o in orders)


def test_paper_adapter_still_fills():
    intents = build_paper_intents(
        positions=[
            {"symbol": "A", "target_shares": 100, "price": 10.0, "can_buy": 1}
        ],
        current_shares={},
    )
    orders, fills = get_adapter("paper").execute(
        intents,
        AdapterContext(cost=_cost(), trade_date="2026-07-28", cash=100_000),
    )
    assert any(o["status"] == "FILLED" for o in orders)
    assert len(fills) >= 1
