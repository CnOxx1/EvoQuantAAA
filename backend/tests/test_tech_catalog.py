from __future__ import annotations

from data_process.tech_catalog import (
    CATEGORIES,
    catalog_summary,
    categorize_column,
    kind_to_category_map,
    load_pandas_ta_kinds,
)
from data_process.tech_indicator import compute_tech_indicator_rows


def test_catalog_has_expected_categories():
    summary = catalog_summary()
    assert summary["suite_full_functions"] >= 100
    for c in CATEGORIES:
        assert c in summary["categories"]
    kinds = load_pandas_ta_kinds()
    assert any(k.category == "momentum" for k in kinds)
    assert any(k.kind == "rsi" for k in kinds)


def test_categorize_column():
    km = kind_to_category_map()
    assert categorize_column("RSI_14", km) == "momentum"
    assert categorize_column("SMA_10", km) == "overlap"
    assert categorize_column("ATR_14", km) == "volatility"


def test_full_suite_emits_categorized_rows():
    from datetime import date, timedelta

    bars = []
    px = 100.0
    for i in range(1, 91):
        px += 0.2
        day = (date(2026, 1, 1) + timedelta(days=i - 1)).isoformat()
        bars.append(
            {
                "symbol": "X",
                "trade_date": day,
                "adj_open": px - 0.1,
                "adj_high": px + 0.5,
                "adj_low": px - 0.5,
                "adj_close": px,
                "volume": 1_000_000.0,
            }
        )
    rows = compute_tech_indicator_rows(
        bars,
        start="2026-03-01",
        end="2026-03-20",
        factor_type="qfq",
        process_batch_id="b1",
        processed_at="t",
        suite="full",
        categories=["momentum", "overlap"],
    )
    assert len(rows) > 50
    codes = {r["indicator_code"] for r in rows}
    cats = {r["category"] for r in rows}
    assert any("RSI" in c for c in codes)
    assert "momentum" in cats
    assert "overlap" in cats
    assert all(r["category"] != "core" for r in rows)
