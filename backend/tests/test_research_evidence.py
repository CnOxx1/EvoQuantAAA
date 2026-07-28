from __future__ import annotations

from research_lab.evidence import (
    format_evidence_pack,
    soft_verdict,
    summarize_oos,
    year_windows,
)


def test_year_windows_span():
    wins = year_windows("2024-06-15", "2026-02-01")
    assert [w[0] for w in wins] == ["2024", "2025", "2026"]
    assert wins[0] == ("2024", "2024-06-15", "2024-12-31")
    assert wins[-1] == ("2026", "2026-01-01", "2026-02-01")


def test_year_windows_empty_when_inverted():
    assert year_windows("2026-01-02", "2026-01-01") == []


def test_soft_verdict_pass_and_fail():
    ok = soft_verdict(
        {"ic_mean": 0.02, "icir": 0.5, "ic_days": 30, "long_short_q5_q1": 0.01}
    )
    assert ok["passed"] is True
    assert ok["failing"] == []

    bad = soft_verdict(
        {"ic_mean": -0.01, "icir": -1.0, "ic_days": 5, "long_short_q5_q1": -0.1},
        gates={"min_ic_mean": 0.0, "min_ic_days": 20, "min_icir": 0.0},
    )
    assert bad["passed"] is False
    assert "ic_mean" in bad["failing"]
    assert "ic_days" in bad["failing"]
    assert "icir" in bad["failing"]


def test_summarize_oos_positive_ratio():
    by_year = {
        "2024": {"report": {"ic_mean": 0.01}},
        "2025": {"report": {"ic_mean": -0.02}},
        "2026": {"report": {"ic_mean": 0.03}},
    }
    s = summarize_oos(by_year)
    assert s["year_count"] == 3
    assert abs(s["positive_ic_year_ratio"] - 2 / 3) < 1e-9
    assert s["ic_mean_min"] == -0.02
    assert s["ic_mean_max"] == 0.03


def test_format_evidence_pack_contains_factor_row():
    text = format_evidence_pack(
        {
            "universe_code": "TOP100",
            "start": "2026-01-01",
            "end": "2026-06-30",
            "year_split": True,
            "with_backtest": False,
            "factors": {
                "MOM_20": {
                    "report": {
                        "ic_mean": 0.01,
                        "icir": 0.2,
                        "ic_days": 40,
                        "long_short_q5_q1": 0.005,
                    },
                    "verdict": {"passed": True, "failing": []},
                    "oos": {
                        "summary": {
                            "year_count": 1,
                            "ic_mean_avg": 0.01,
                            "positive_ic_year_ratio": 1.0,
                        }
                    },
                }
            },
        }
    )
    assert "MOM_20" in text
    assert "PASS" in text
    assert "oos years=1" in text
