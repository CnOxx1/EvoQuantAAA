from __future__ import annotations

from shared.impact import (
    attach_adv_to_bars,
    compute_rolling_adv,
    effective_slippage_rate,
    slipped_fill_price,
)


def test_flat_ignores_adv():
    rate = effective_slippage_rate(
        base_slippage=0.0005,
        impact_model="flat",
        impact_coef=0.1,
        notional=1_000_000,
        adv=10_000_000,
    )
    assert abs(rate - 0.0005) < 1e-12


def test_sqrt_adv_impact():
    # participation=0.01 → sqrt=0.1 → extra=0.01；总=0.0005+0.01
    rate = effective_slippage_rate(
        base_slippage=0.0005,
        impact_model="sqrt_adv",
        impact_coef=0.1,
        notional=100_000,
        adv=10_000_000,
    )
    assert abs(rate - 0.0105) < 1e-12


def test_sqrt_adv_missing_adv_falls_back():
    rate = effective_slippage_rate(
        base_slippage=0.0005,
        impact_model="sqrt_adv",
        impact_coef=0.1,
        notional=100_000,
        adv=None,
    )
    assert abs(rate - 0.0005) < 1e-12


def test_slipped_fill_price_buy_sell():
    buy = slipped_fill_price(
        side="BUY",
        mid=100.0,
        base_slippage=0.0,
        impact_model="sqrt_adv",
        impact_coef=0.1,
        qty=1000,
        adv=1_000_000,  # notional=100k, part=0.1, sqrt≈0.3162, slip≈0.03162
    )
    sell = slipped_fill_price(
        side="SELL",
        mid=100.0,
        base_slippage=0.0,
        impact_model="sqrt_adv",
        impact_coef=0.1,
        qty=1000,
        adv=1_000_000,
    )
    assert buy > 100.0
    assert sell < 100.0
    assert abs((buy - 100.0) - (100.0 - sell)) < 1e-9


def test_rolling_adv_attach():
    bars = []
    for i in range(1, 6):
        bars.append(
            {
                "symbol": "A",
                "trade_date": f"2026-01-{i:02d}",
                "amount": 10.0 * i,
            }
        )
    adv = compute_rolling_adv(bars, lookback=3)
    # day5 amounts 30,40,50 → mean 40
    assert abs(adv[("A", "2026-01-05")] - 40.0) < 1e-9
    out = attach_adv_to_bars(bars, lookback=3)
    assert out[-1]["adv"] == adv[("A", "2026-01-05")]
