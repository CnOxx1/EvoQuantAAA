from __future__ import annotations

from research_lab.evidence import (
    artifact_hash,
    format_evidence_pack,
    hard_oos_verdict,
    oos_eval_windows,
    pack_freeze_eligibility,
    soft_verdict,
    summarize_oos,
    walk_forward_windows,
    year_windows,
)


def test_year_windows_span():
    wins = year_windows("2024-06-15", "2026-02-01")
    assert [w[0] for w in wins] == ["2024", "2025", "2026"]
    assert wins[0] == ("2024", "2024-06-15", "2024-12-31")
    assert wins[-1] == ("2026", "2026-01-01", "2026-02-01")


def test_year_windows_empty_when_inverted():
    assert year_windows("2026-01-02", "2026-01-01") == []


def test_walk_forward_windows_smoke():
    # 短窗冒烟：train=10 test=5 step=5 → 多折
    folds = walk_forward_windows(
        "2026-01-01", "2026-02-15", train_days=10, test_days=5, step_days=5
    )
    assert len(folds) >= 2
    lab, tr0, tr1, te0, te1 = folds[0]
    assert tr0 == "2026-01-01"
    assert te0 > tr1
    assert all(x[3] <= "2026-02-15" and x[4] <= "2026-02-15" for x in folds)


def test_oos_eval_windows_modes():
    assert oos_eval_windows("2026-01-01", "2026-03-01", split_mode="none") == []
    years = oos_eval_windows("2025-12-01", "2026-02-01", split_mode="year")
    assert years[0][0] == "2025"
    wf = oos_eval_windows(
        "2026-01-01",
        "2026-02-20",
        split_mode="walk_forward",
        train_days=7,
        test_days=5,
        step_days=5,
    )
    assert len(wf) >= 1


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
    assert s["fold_count"] == 3
    assert abs(s["positive_ic_fold_ratio"] - 2 / 3) < 1e-9
    assert s["ic_mean_min"] == -0.02
    assert s["ic_mean_max"] == 0.03


def test_hard_oos_and_freeze_eligibility():
    summary_ok = {
        "fold_count": 3,
        "positive_ic_fold_ratio": 0.67,
        "ic_mean_avg": 0.01,
    }
    assert hard_oos_verdict(summary_ok)["passed"] is True
    assert hard_oos_verdict({"fold_count": 1})["passed"] is False

    pack = {
        "universe_code": "TOP100",
        "start": "2024-01-01",
        "end": "2026-01-01",
        "split_mode": "year",
        "factors": {
            "MOM_20": {
                "status": "committed",
                "report": {"ic_mean": 0.02, "icir": 0.3, "ic_days": 40},
                "verdict": soft_verdict(
                    {"ic_mean": 0.02, "icir": 0.3, "ic_days": 40}
                ),
                "oos": {"summary": summary_ok},
                "hard_oos": hard_oos_verdict(summary_ok),
            }
        },
    }
    elig = pack_freeze_eligibility(pack)
    assert elig["eligible"] is True
    assert "MOM_20" in elig["eligible_factors"]
    h = artifact_hash(pack)
    assert len(h) == 64
    assert artifact_hash(pack) == h


def test_format_evidence_pack_contains_factor_row():
    text = format_evidence_pack(
        {
            "universe_code": "TOP100",
            "start": "2026-01-01",
            "end": "2026-06-30",
            "year_split": True,
            "split_mode": "year",
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
                    "hard_oos": {"passed": True, "failing": []},
                    "oos": {
                        "summary": {
                            "fold_count": 1,
                            "year_count": 1,
                            "ic_mean_avg": 0.01,
                            "positive_ic_fold_ratio": 1.0,
                            "positive_ic_year_ratio": 1.0,
                        }
                    },
                }
            },
        }
    )
    assert "MOM_20" in text
    assert "PASS" in text
    assert "oos folds=1" in text
