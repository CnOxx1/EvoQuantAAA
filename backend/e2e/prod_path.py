from __future__ import annotations

"""
生产链路端到端回归（短窗、自备种子，不拉 ALL_LISTED）。

用法（在 backend/ 下）:
  python main.py migrate
  python -m e2e.prod_path
  # 或
  python main.py e2e
"""

import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from shared.db import get_conn  # noqa: E402

AS_OF = "2026-06-10"
START = "2026-06-09"
END = "2026-06-10"
UNIVERSE = "E2E_TOP10"
FACTOR = "MOM_20"
ACCOUNT = "e2e_smoke"
STRATEGY_CODE = "E2E_FTN"
COST = "v1_ashare_default"
NAV = 1_000_000.0


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _weekdays(start: str, end: str) -> list[str]:
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    out: list[str] = []
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def seed_minimal() -> tuple[str, str]:
    """写入 E2E 专用 universe / bars / factors / account；返回 (backtest_run_id, research_run_id)。"""
    symbols = [f"{600000 + i:06d}" for i in range(10)]
    bar_start = (date.fromisoformat(START) - timedelta(days=25)).isoformat()
    dates = _weekdays(bar_start, END)
    if len(dates) < 5:
        raise RuntimeError("E2E 日期窗口过短")

    snap_id = f"us_e2e_{AS_OF.replace('-', '')}"
    run_id = f"rr_e2e_{uuid.uuid4().hex[:12]}"
    batch_id = f"pb_e2e_{uuid.uuid4().hex[:12]}"
    bt = f"bt_e2e_{uuid.uuid4().hex[:12]}"
    now = _utcnow()
    research_meta = {
        "mode": "evaluate",
        "e2e": True,
        "report": {
            "ic_mean": 0.05,
            "icir": 0.8,
            "ic_days": 20,
            "ic_win_rate": 0.55,
        },
    }

    with get_conn() as conn:
        conn.execute(
            "DELETE FROM universe_snapshot_member WHERE universe_snapshot_id=?",
            (snap_id,),
        )
        conn.execute(
            "DELETE FROM universe_snapshot WHERE universe_snapshot_id=?",
            (snap_id,),
        )
        conn.execute(
            """
            INSERT INTO universe_snapshot (
                universe_snapshot_id, as_of_date, universe_code, status,
                member_count, source_note, meta_json, created_at
            ) VALUES (?, ?, ?, 'committed', ?, 'e2e', ?, ?)
            """,
            (snap_id, AS_OF, UNIVERSE, len(symbols), json.dumps({"e2e": True}), now),
        )
        for sym in symbols:
            conn.execute(
                """
                INSERT INTO universe_snapshot_member (
                    universe_snapshot_id, symbol, name, is_eligible
                ) VALUES (?, ?, ?, 1)
                """,
                (snap_id, sym, sym),
            )

        conn.execute(
            """
            INSERT INTO research_run (
                run_id, factor_code, universe_code, start_date, end_date,
                status, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, 'committed', ?, ?)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (run_id, FACTOR, UNIVERSE, dates[0], END, json.dumps(research_meta), now),
        )

        for di, d in enumerate(dates):
            for si, sym in enumerate(symbols):
                val = float(1000 + di * 10 - si)
                px = 10.0 + si * 0.5
                conn.execute(
                    """
                    INSERT INTO research_factor_value (
                        factor_code, symbol, trade_date, value, universe_code,
                        run_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (factor_code, symbol, trade_date, universe_code)
                    DO UPDATE SET value=EXCLUDED.value, run_id=EXCLUDED.run_id
                    """,
                    (FACTOR, sym, d, val, UNIVERSE, run_id, now),
                )
                conn.execute(
                    """
                    INSERT INTO processed_equity_bar_1d (
                        process_batch_id, symbol, trade_date,
                        open, high, low, close, volume, amount,
                        adj_factor, factor_type,
                        adj_open, adj_high, adj_low, adj_close, ret_1d,
                        is_suspended, is_limit_up, is_limit_down,
                        can_buy, can_sell, source, processed_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, 1000000, 10000000,
                        1.0, 'qfq',
                        ?, ?, ?, ?, 0.01,
                        0, 0, 0, 1, 1, 'e2e', ?
                    )
                    ON CONFLICT (symbol, trade_date, factor_type) DO UPDATE SET
                        adj_close=EXCLUDED.adj_close, can_buy=1, can_sell=1
                    """,
                    (batch_id, sym, d, px, px, px, px, px, px, px, px, now),
                )

        conn.execute(
            """
            INSERT INTO ledger_account (
                account_id, currency, opening_cash, status, meta_json, created_at
            ) VALUES (?, 'CNY', ?, 'active', ?, ?)
            ON CONFLICT (account_id) DO NOTHING
            """,
            (ACCOUNT, NAV, json.dumps({"e2e": True}), now),
        )
        # 清空历史持仓/sleeve，保证差额成交产生 fill（可重复跑）
        conn.execute(
            "DELETE FROM ledger_lot WHERE account_id=?",
            (ACCOUNT,),
        )
        conn.execute(
            "DELETE FROM ledger_sleeve_position WHERE account_id=?",
            (ACCOUNT,),
        )
        conn.execute(
            """
            DELETE FROM ledger_balance
            WHERE account_id=? AND asset_type='POSITION'
            """,
            (ACCOUNT,),
        )
        conn.execute(
            """
            INSERT INTO ledger_balance (account_id, asset_type, symbol, qty, updated_at)
            VALUES (?, 'CASH', '', ?, ?)
            ON CONFLICT (account_id, asset_type, symbol) DO UPDATE SET
                qty=EXCLUDED.qty, updated_at=EXCLUDED.updated_at
            """,
            (ACCOUNT, NAV, now),
        )
        conn.execute(
            """
            INSERT INTO kill_switch (scope_key, is_on, reason, actor, updated_at)
            VALUES ('GLOBAL', 0, 'e2e ensure off', 'e2e', ?)
            ON CONFLICT (scope_key) DO UPDATE SET is_on=0, updated_at=EXCLUDED.updated_at
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO kill_switch (scope_key, is_on, reason, actor, updated_at)
            VALUES (?, 0, 'e2e ensure off', 'e2e', ?)
            ON CONFLICT (scope_key) DO UPDATE SET is_on=0, updated_at=EXCLUDED.updated_at
            """,
            (ACCOUNT, now),
        )
        conn.execute(
            """
            INSERT INTO backtest_run (
                run_id, strategy_code, status, start_date, end_date,
                universe_code, factor_type, cost_version, initial_cash,
                final_nav, total_return, benchmark_return, max_drawdown, trade_count,
                dq_required, meta_json, created_at, finished_at
            ) VALUES (
                ?, ?, 'committed', ?, ?, ?, 'qfq', ?, ?,
                ?, 0.01, 0.0, 0.05, 3, 0, ?, ?, ?
            )
            ON CONFLICT (run_id) DO NOTHING
            """,
            (
                bt,
                STRATEGY_CODE,
                dates[0],
                END,
                UNIVERSE,
                COST,
                NAV,
                NAV * 1.01,
                json.dumps({"e2e": True}),
                now,
                now,
            ),
        )
    return bt, run_id


def _fail(step: str, msg: str) -> int:
    print(f"status=failed step={step} message={msg}")
    return 2


def run() -> int:
    print(f"e2e start as_of={AS_OF} universe={UNIVERSE} account={ACCOUNT}")
    try:
        bt_id, research_id = seed_minimal()
    except Exception as exc:  # noqa: BLE001
        return _fail("seed", str(exc))
    print(f"seed=ok backtest={bt_id} research={research_id}")

    from strategy_registry.models import PromoteRequest, RegisterRequest
    from strategy_registry.service import StrategyRegistryService

    reg = StrategyRegistryService()
    for row in reg.list(status="LIVE", strategy_code=STRATEGY_CODE):
        reg.retire(strategy_version=row.strategy_version, reason="e2e reset")

    r0 = reg.register(
        RegisterRequest(
            strategy_code=STRATEGY_CODE,
            strategy_kind="FACTOR_TOP_N",
            params={
                "factor_code": FACTOR,
                "top_n": 10,
                "rebalance_days": 1,
                "universe_code": UNIVERSE,
                "factor_type": "qfq",
            },
            research_run_id=research_id,
            note="e2e smoke",
            actor="e2e",
        )
    )
    if r0.status != "ok":
        return _fail("register", r0.message)
    sv = r0.strategy_version
    print(f"register=ok version={sv}")

    for to, kw in (
        ("BACKTESTED", {"backtest_run_id": bt_id}),
        ("PAPER", {}),
        ("LIVE", {}),
    ):
        pr = reg.promote(
            PromoteRequest(
                strategy_version=sv,
                to_status=to,  # type: ignore[arg-type]
                actor="e2e",
                reason=f"e2e → {to}",
                **kw,
            )
        )
        if pr.status != "ok":
            return _fail(f"promote_{to}", pr.message)
        print(f"promote={to} ok")

    from signal_prod.models import SignalRunRequest
    from signal_prod.service import SignalProdService

    sg = SignalProdService().run(
        SignalRunRequest(
            strategy_version=sv,
            start=START,
            end=END,
            require_dq=False,
            job_id="e2e",
        )
    )
    if sg.status != "committed":
        return _fail("signal", sg.message or sg.status)
    print(f"signal=ok batch={sg.signal_batch_id} rows={sg.row_count}")

    from portfolio_construct.models import PortfolioBuildRequest
    from portfolio_construct.service import PortfolioConstructService

    pf_svc = PortfolioConstructService()
    p1 = pf_svc.build(
        PortfolioBuildRequest(
            strategy_version=sv,
            as_of=AS_OF,
            nav=NAV,
            account_id=ACCOUNT,
            cost_version=COST,
            use_ledger_nav=True,
            job_id="e2e",
        )
    )
    if p1.status != "draft":
        return _fail("portfolio", p1.message or p1.status)
    pf_id = p1.portfolio_id
    print(f"portfolio=ok id={pf_id} rows={p1.row_count}")

    p2 = pf_svc.build(
        PortfolioBuildRequest(
            strategy_version=sv,
            as_of=AS_OF,
            nav=NAV,
            account_id=ACCOUNT,
            cost_version=COST,
            use_ledger_nav=True,
            job_id="e2e",
        )
    )
    if p2.status != "skipped" or p2.portfolio_id != pf_id:
        return _fail(
            "portfolio_idempotent",
            f"期望 skipped 同一 portfolio，got status={p2.status} id={p2.portfolio_id}",
        )
    print("portfolio_idempotent=ok")

    from risk_engine.models import RiskReviewRequest
    from risk_engine.service import RiskEngineService

    rk = RiskEngineService().review(
        RiskReviewRequest(portfolio_id=pf_id, actor="e2e", job_id="e2e")
    )
    if rk.status != "approved":
        return _fail("risk", f"{rk.status} breaches={rk.breaches} {rk.message}")
    print(f"risk=ok decision={rk.decision_id}")

    from execution.models import ExecutionRequest
    from execution.service import ExecutionService

    ex_svc = ExecutionService()
    ex1 = ex_svc.run(
        ExecutionRequest(portfolio_id=pf_id, cost_version=COST, job_id="e2e")
    )
    if ex1.status != "committed":
        return _fail("execution", ex1.message or ex1.status)
    print(
        f"execution=ok id={ex1.execution_id} orders={ex1.order_count} fills={ex1.fill_count}"
    )

    ex2 = ex_svc.run(
        ExecutionRequest(portfolio_id=pf_id, cost_version=COST, job_id="e2e")
    )
    if ex2.status != "skipped":
        return _fail("execution_idempotent", f"{ex2.status} {ex2.message}")
    print("execution_idempotent=ok")

    from ledger.models import PostRequest
    from ledger.service import LedgerService

    ld_svc = LedgerService()
    ld1 = ld_svc.post(
        PostRequest(execution_id=ex1.execution_id, account_id=ACCOUNT, job_id="e2e")
    )
    if ld1.status != "committed":
        return _fail("ledger", ld1.message or ld1.status)
    print(f"ledger=ok posting={ld1.posting_id} cash={ld1.cash_after:.2f}")

    ld2 = ld_svc.post(
        PostRequest(execution_id=ex1.execution_id, account_id=ACCOUNT, job_id="e2e")
    )
    if ld2.status != "skipped":
        return _fail("ledger_idempotent", f"{ld2.status} {ld2.message}")
    print("ledger_idempotent=ok")

    from fastapi.testclient import TestClient

    from api_gateway.app import create_app

    client = TestClient(create_app())
    if client.get("/health").json().get("ok") is not True:
        return _fail("api_health", "health failed")
    if not client.get("/v1/strategies", params={"status": "LIVE"}).json().get("ok"):
        return _fail("api_strategies", "strategies failed")
    if not client.get("/v1/risk/kill").json().get("ok"):
        return _fail("api_kill", "kill failed")
    if not client.get(f"/v1/ledger/accounts/{ACCOUNT}", params={"as_of": AS_OF}).json().get(
        "ok"
    ):
        return _fail("api_ledger", "ledger failed")
    print("api=ok")

    print(
        f"status=ok version={sv} portfolio={pf_id} "
        f"execution={ex1.execution_id} posting={ld1.posting_id}"
    )
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
