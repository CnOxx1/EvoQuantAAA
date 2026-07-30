from __future__ import annotations

import json
from typing import Any

from shared.db import get_conn

from api_gateway.indicator_meta import enrich_indicator_code


def _bare_symbol(symbol: str) -> str:
    """processed 表用纯数字代码；兼容 600000.SH / SH600000。"""
    s = (symbol or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    if s.startswith(("SH", "SZ", "BJ")) and len(s) >= 8 and s[2:].isdigit():
        s = s[2:]
    if "." in s:
        s = s.split(".", 1)[0]
    return s


class GatewayRepository:
    def list_strategies(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM strategy_version WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["params"] = json.loads(str(r.pop("params_json", None) or "{}"))
            except json.JSONDecodeError:
                r["params"] = {}
        return rows

    def get_strategy(self, strategy_version: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_version WHERE strategy_version=?",
                (strategy_version,),
            ).fetchone()
            if not row:
                return None
            transitions = conn.execute(
                """
                SELECT transition_id, from_status, to_status, actor, reason, created_at
                FROM strategy_transition
                WHERE strategy_version=?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (strategy_version,),
            ).fetchall()
            gates = conn.execute(
                """
                SELECT gate_id, to_status, gate_version, passed, skipped,
                       backtest_run_id, research_run_id, metrics_json, checks_json,
                       actor, reason, created_at
                FROM promotion_gate_result
                WHERE strategy_version=?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (strategy_version,),
            ).fetchall()
        d = dict(row)
        try:
            d["params"] = json.loads(str(d.pop("params_json", None) or "{}"))
        except json.JSONDecodeError:
            d["params"] = {}
        d["transitions"] = [dict(t) for t in transitions]
        gate_rows: list[dict[str, Any]] = []
        for g in gates:
            gd = dict(g)
            for key in ("metrics_json", "checks_json"):
                raw = gd.pop(key, None)
                name = key.replace("_json", "")
                try:
                    gd[name] = json.loads(str(raw or "{}"))
                except json.JSONDecodeError:
                    gd[name] = {}
            gd["passed"] = bool(int(gd.get("passed") or 0))
            gd["skipped"] = bool(int(gd.get("skipped") or 0))
            gate_rows.append(gd)
        d["gate_results"] = gate_rows
        return d

    def get_research_run(self, run_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM research_run WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            freezes = conn.execute(
                """
                SELECT freeze_id, evidence_run_id, universe_code, start_date, end_date,
                       status, split_mode, hard_gates_json, summary_json, artifact_hash,
                       actor, reason, created_at
                FROM research_evidence_freeze
                WHERE evidence_run_id=?
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (run_id,),
            ).fetchall()
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        freeze_rows: list[dict[str, Any]] = []
        for f in freezes:
            fd = dict(f)
            for key in ("hard_gates_json", "summary_json"):
                raw = fd.pop(key, None)
                name = key.replace("_json", "")
                try:
                    fd[name] = json.loads(str(raw or "{}"))
                except json.JSONDecodeError:
                    fd[name] = {}
            freeze_rows.append(fd)
        d["freezes"] = freeze_rows
        return d

    def get_risk_decision(self, decision_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM risk_decision WHERE decision_id=?",
                (decision_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["breaches"] = json.loads(str(d.pop("breaches_json", None) or "[]"))
        except json.JSONDecodeError:
            d["breaches"] = []
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        d["kill_switch_on"] = bool(int(d.get("kill_switch_on") or 0))
        return d

    def ops_pipeline(self) -> dict[str, Any]:
        """总览轻量管道状态（只读聚合，不做 ingest 探活）。"""
        with get_conn() as conn:
            alerts = conn.execute(
                """
                SELECT severity, COUNT(*) AS n FROM ops_alert
                WHERE COALESCE(status, 'open') IN ('open', 'OPEN', '')
                   OR status IS NULL
                GROUP BY severity
                """
            ).fetchall()
            # fallback if status column semantics differ — count recent alerts
            alert_recent = conn.execute(
                """
                SELECT COUNT(*) AS n FROM ops_alert
                WHERE created_at >= (CURRENT_TIMESTAMP - INTERVAL '7 days')
                """
            ).fetchone()
            live_n = conn.execute(
                "SELECT COUNT(*) AS n FROM strategy_version WHERE status='LIVE'"
            ).fetchone()
            paper_n = conn.execute(
                "SELECT COUNT(*) AS n FROM strategy_version WHERE status='PAPER'"
            ).fetchone()
            port_draft = conn.execute(
                "SELECT COUNT(*) AS n FROM portfolio_target WHERE status='draft'"
            ).fetchone()
            port_approved = conn.execute(
                "SELECT COUNT(*) AS n FROM portfolio_target WHERE status='approved'"
            ).fetchone()
            exec_n = conn.execute(
                "SELECT COUNT(*) AS n FROM execution_run"
            ).fetchone()
            pending_n = conn.execute(
                "SELECT COUNT(*) AS n FROM execution_pending WHERE status='open'"
            ).fetchone()
            posting_n = conn.execute(
                "SELECT COUNT(*) AS n FROM ledger_posting WHERE status='committed'"
            ).fetchone()
            kill = conn.execute(
                "SELECT is_on FROM kill_switch WHERE scope_key='GLOBAL'"
            ).fetchone()
            dq = conn.execute(
                """
                SELECT status FROM dq_gate
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 1
                """
            ).fetchone()
        by_level = {str(r["severity"] or "info"): int(r["n"] or 0) for r in alerts}
        open_alerts = sum(by_level.values())
        kill_on = bool(int(kill["is_on"]) if kill else 0)
        dq_status = str(dq["status"]) if dq else "unknown"
        stages = [
            {
                "name": "alerts",
                "ok": open_alerts == 0,
                "detail": f"open={open_alerts}",
            },
            {
                "name": "DQ",
                "ok": dq_status.lower() in ("pass", "passed", "ok"),
                "detail": dq_status,
            },
            {
                "name": "signal",
                "ok": int(live_n["n"] if live_n else 0) + int(paper_n["n"] if paper_n else 0)
                > 0,
                "detail": f"LIVE={int(live_n['n'] if live_n else 0)} PAPER={int(paper_n['n'] if paper_n else 0)}",
            },
            {
                "name": "portfolio",
                "ok": int(port_draft["n"] if port_draft else 0)
                + int(port_approved["n"] if port_approved else 0)
                > 0,
                "detail": f"draft={int(port_draft['n'] if port_draft else 0)} approved={int(port_approved['n'] if port_approved else 0)}",
            },
            {
                "name": "risk",
                "ok": not kill_on,
                "detail": "kill_on" if kill_on else "kill_off",
            },
            {
                "name": "exec",
                "ok": int(exec_n["n"] if exec_n else 0) > 0,
                "detail": f"runs={int(exec_n['n'] if exec_n else 0)} pending={int(pending_n['n'] if pending_n else 0)}",
            },
            {
                "name": "ledger",
                "ok": int(posting_n["n"] if posting_n else 0) > 0,
                "detail": f"postings={int(posting_n['n'] if posting_n else 0)}",
            },
        ]
        return {
            "stages": stages,
            "counts": {
                "open_alerts": open_alerts,
                "alerts_7d": int(alert_recent["n"] if alert_recent else 0),
                "live_strategies": int(live_n["n"] if live_n else 0),
                "paper_strategies": int(paper_n["n"] if paper_n else 0),
                "draft_portfolios": int(port_draft["n"] if port_draft else 0),
                "approved_portfolios": int(port_approved["n"] if port_approved else 0),
                "executions": int(exec_n["n"] if exec_n else 0),
                "open_pending": int(pending_n["n"] if pending_n else 0),
                "ledger_postings": int(posting_n["n"] if posting_n else 0),
            },
            "kill_on": kill_on,
            "dq_status": dq_status,
            "alert_levels": by_level,
        }

    def list_signal_batches(
        self, *, strategy_version: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM signal_batch WHERE 1=1"
        params: list[Any] = []
        if strategy_version:
            sql += " AND strategy_version=?"
            params.append(strategy_version)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_portfolios(
        self,
        *,
        status: str | None = None,
        as_of: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM portfolio_target WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if as_of:
            sql += " AND as_of_date=?"
            params.append(as_of[:10])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            head = conn.execute(
                "SELECT * FROM portfolio_target WHERE portfolio_id=?",
                (portfolio_id,),
            ).fetchone()
            if not head:
                return None
            positions = conn.execute(
                """
                SELECT symbol, target_weight, target_shares, target_value, price, status
                FROM portfolio_target_position
                WHERE portfolio_id=?
                ORDER BY target_weight DESC, symbol
                """,
                (portfolio_id,),
            ).fetchall()
        d = dict(head)
        d["positions"] = [dict(p) for p in positions]
        return d

    def list_kill_switches(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM kill_switch ORDER BY scope_key"
            ).fetchall()
        return [dict(r) for r in rows]

    def list_risk_decisions(
        self, *, portfolio_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM risk_decision WHERE 1=1"
        params: list[Any] = []
        if portfolio_id:
            sql += " AND portfolio_id=?"
            params.append(portfolio_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        out: list[dict[str, Any]] = []
        for d in rows:
            try:
                d["breaches"] = json.loads(str(d.pop("breaches_json", None) or "[]"))
            except json.JSONDecodeError:
                d["breaches"] = []
            try:
                d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            d["kill_switch_on"] = bool(int(d.get("kill_switch_on") or 0))
            out.append(d)
        return out

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            run = conn.execute(
                "SELECT * FROM execution_run WHERE execution_id=?",
                (execution_id,),
            ).fetchone()
            if not run:
                return None
            fills = conn.execute(
                """
                SELECT fill_id, symbol, side, qty, price, amount, commission, stamp_tax, trade_date
                FROM fill_event WHERE execution_id=?
                ORDER BY symbol
                """,
                (execution_id,),
            ).fetchall()
            orders = conn.execute(
                """
                SELECT event_id, order_id, symbol, side, qty, limit_price, status,
                       event_type, reason, created_at
                FROM order_event WHERE execution_id=?
                ORDER BY created_at, symbol
                """,
                (execution_id,),
            ).fetchall()
        d = dict(run)
        d["fills"] = [dict(f) for f in fills]
        d["orders"] = [dict(o) for o in orders]
        return d

    def list_executions(
        self,
        *,
        account_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM execution_run WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_pending(
        self,
        *,
        account_id: str | None = None,
        status: str | None = "open",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM execution_pending WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_research_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM research_run
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    def list_market_ranks(
        self,
        *,
        trade_date: str | None = None,
        rank_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT trade_date, rank_type, rank_no, symbol, name, metric_value,
                   close, pct_chg, volume, amount, turnover, source
            FROM raw_market_rank_1d WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_market_rank_1d
                )
            """
        if rank_type:
            sql += " AND rank_type=?"
            params.append(rank_type)
        sql += " ORDER BY rank_type, rank_no ASC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_rank_meta(self) -> dict[str, Any]:
        with get_conn() as conn:
            dates = [
                str(r["d"])
                for r in conn.execute(
                    """
                    SELECT DISTINCT trade_date AS d FROM raw_market_rank_1d
                    ORDER BY trade_date DESC LIMIT 30
                    """
                ).fetchall()
            ]
            types = [
                str(r["rank_type"])
                for r in conn.execute(
                    """
                    SELECT DISTINCT rank_type FROM raw_market_rank_1d
                    ORDER BY rank_type
                    """
                ).fetchall()
            ]
        return {"trade_dates": dates, "rank_types": types}

    def list_abnormal_moves(
        self,
        *,
        trade_date: str | None = None,
        change_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT trade_date, event_time, symbol, name, change_type,
                   related_info, source_event_id, source
            FROM raw_abnormal_move WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_abnormal_move
                )
            """
        if change_type:
            sql += " AND change_type=?"
            params.append(change_type)
        sql += " ORDER BY event_time DESC NULLS LAST, symbol LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_news(
        self,
        *,
        channel: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT source_news_id, symbol, title, summary, publish_time, url,
                   media_source, channel, source, content_type, extra_json
            FROM raw_news_media WHERE 1=1
        """
        params: list[Any] = []
        if channel:
            sql += " AND channel=?"
            params.append(channel)
        if symbol:
            sql += " AND (symbol=? OR symbol=? OR symbol LIKE ?)"
            bare = symbol.strip().upper()
            for suf in (".SH", ".SZ", ".BJ"):
                if bare.endswith(suf):
                    bare = bare[: -len(suf)]
                    break
            params.append(symbol.strip())
            params.append(bare)
            params.append(f"{bare}.%")
        sql += " ORDER BY publish_time DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["extra"] = json.loads(str(r.pop("extra_json", None) or "{}"))
            except json.JSONDecodeError:
                r["extra"] = {}
        return rows

    def list_dragon_tiger(
        self,
        *,
        trade_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT symbol, trade_date, reason, close, pct_chg, net_amount,
                   buy_amount, sell_amount, source_event_id, source
            FROM raw_dragon_tiger WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(
                    SELECT MAX(trade_date) FROM raw_dragon_tiger
                )
            """
        sql += " ORDER BY ABS(COALESCE(net_amount,0)) DESC, symbol LIMIT ?"
        params.append(max(1, min(limit, 300)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_equity_bars(
        self,
        *,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        factor_type: str = "qfq",
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        """日线 K：processed_equity_bar_1d（只读，默认前复权）。"""
        sym = _bare_symbol(symbol)
        if not sym:
            return []
        ft = (factor_type or "qfq").strip() or "qfq"
        lim = max(1, min(int(limit), 800))
        params: list[Any] = [sym, ft]
        date_clause = ""
        if start:
            date_clause += " AND trade_date>=?"
            params.append(start[:10])
        if end:
            date_clause += " AND trade_date<=?"
            params.append(end[:10])
        # 无起止时取最近 lim 根；有起止时同样截断 lim（按日期升序返回）
        sql = f"""
            SELECT * FROM (
                SELECT symbol, trade_date, factor_type,
                       open, high, low, close, volume, amount,
                       adj_open, adj_high, adj_low, adj_close, adj_factor,
                       ret_1d, can_buy, can_sell, is_suspended,
                       is_limit_up, is_limit_down, source
                FROM processed_equity_bar_1d
                WHERE symbol=? AND factor_type=?{date_clause}
                ORDER BY trade_date DESC
                LIMIT ?
            ) t
            ORDER BY trade_date ASC
        """
        params.append(lim)
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        out: list[dict[str, Any]] = []
        for r in rows:
            # 图表默认用复权 OHLC；缺失则回退未复权
            o = r.get("adj_open") if r.get("adj_open") is not None else r.get("open")
            h = r.get("adj_high") if r.get("adj_high") is not None else r.get("high")
            l = r.get("adj_low") if r.get("adj_low") is not None else r.get("low")
            c = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
            out.append(
                {
                    "symbol": r.get("symbol"),
                    "trade_date": str(r.get("trade_date") or "")[:10],
                    "factor_type": r.get("factor_type"),
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": r.get("volume"),
                    "amount": r.get("amount"),
                    "raw_open": r.get("open"),
                    "raw_high": r.get("high"),
                    "raw_low": r.get("low"),
                    "raw_close": r.get("close"),
                    "adj_factor": r.get("adj_factor"),
                    "ret_1d": r.get("ret_1d"),
                    "can_buy": r.get("can_buy"),
                    "can_sell": r.get("can_sell"),
                    "is_suspended": r.get("is_suspended"),
                    "is_limit_up": r.get("is_limit_up"),
                    "is_limit_down": r.get("is_limit_down"),
                    "source": r.get("source"),
                }
            )
        return out

    CORE_INDICATOR_CODES: tuple[str, ...] = (
        "MA_5",
        "MA_10",
        "MA_20",
        "MA_60",
        "EMA_12",
        "EMA_26",
        "MACD_DIF",
        "MACD_DEA",
        "MACD_HIST",
        "RSI_14",
        "BOLL_MID",
        "BOLL_UP",
        "BOLL_LOW",
    )

    def list_tech_indicator_meta(self, *, symbol: str | None = None) -> dict[str, Any]:
        params: list[Any] = []
        where = ""
        if symbol and symbol.strip():
            where = " WHERE symbol=?"
            params.append(_bare_symbol(symbol))
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT indicator_code, COUNT(*) AS n
                FROM processed_tech_indicator_1d
                {where}
                GROUP BY indicator_code
                ORDER BY indicator_code
                """,
                tuple(params),
            ).fetchall()
        codes = [
            enrich_indicator_code(
                str(r["indicator_code"]), count=int(r["n"] or 0)
            )
            for r in rows
        ]
        core = [
            c
            for c in self.CORE_INDICATOR_CODES
            if any(x["code"] == c for x in codes)
        ]
        cats = sorted({str(x["category"]) for x in codes})
        return {
            "core_codes": list(core) if core else list(self.CORE_INDICATOR_CODES),
            "categories": cats,
            "codes": codes,
            "total": len(codes),
        }

    def list_tech_indicators(
        self,
        *,
        symbol: str,
        codes: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
        factor_type: str = "qfq",
        limit: int = 180,
    ) -> dict[str, Any]:
        """日线技术指标：processed_tech_indicator_1d（长表 → series）。"""
        sym = _bare_symbol(symbol)
        if not sym:
            return {"symbol": "", "factor_type": factor_type, "series": {}}
        ft = (factor_type or "qfq").strip() or "qfq"
        lim = max(1, min(int(limit), 800))
        want = [c.strip() for c in (codes or list(self.CORE_INDICATOR_CODES)) if c.strip()]
        if not want:
            want = list(self.CORE_INDICATOR_CODES)
        # 先按日期窗口取最近 lim 个交易日（与 bars 对齐）
        date_params: list[Any] = [sym, ft]
        date_clause = ""
        if start:
            date_clause += " AND trade_date>=?"
            date_params.append(start[:10])
        if end:
            date_clause += " AND trade_date<=?"
            date_params.append(end[:10])
        with get_conn() as conn:
            date_rows = conn.execute(
                f"""
                SELECT * FROM (
                    SELECT DISTINCT trade_date
                    FROM processed_tech_indicator_1d
                    WHERE symbol=? AND factor_type=?{date_clause}
                    ORDER BY trade_date DESC
                    LIMIT ?
                ) t ORDER BY trade_date ASC
                """,
                (*date_params, lim),
            ).fetchall()
            dates = [str(r["trade_date"])[:10] for r in date_rows]
            if not dates:
                return {
                    "symbol": sym,
                    "factor_type": ft,
                    "codes": want,
                    "count": 0,
                    "series": {c: [] for c in want},
                }
            ph_c = ",".join("?" * len(want))
            ph_d = ",".join("?" * len(dates))
            rows = conn.execute(
                f"""
                SELECT trade_date, indicator_code, value
                FROM processed_tech_indicator_1d
                WHERE symbol=? AND factor_type=?
                  AND indicator_code IN ({ph_c})
                  AND trade_date IN ({ph_d})
                ORDER BY trade_date ASC, indicator_code
                """,
                (sym, ft, *want, *dates),
            ).fetchall()
        series: dict[str, list[dict[str, Any]]] = {c: [] for c in want}
        for r in rows:
            code = str(r["indicator_code"])
            if code not in series:
                series[code] = []
            val = r["value"]
            if val is None:
                continue
            try:
                fv = float(val)
            except (TypeError, ValueError):
                continue
            if not (fv == fv):  # NaN
                continue
            series[code].append(
                {"trade_date": str(r["trade_date"])[:10], "value": fv}
            )
        return {
            "symbol": sym,
            "factor_type": ft,
            "codes": want,
            "count": sum(len(v) for v in series.values()),
            "series": series,
        }

    def get_ledger_account(self, account_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            acct = conn.execute(
                "SELECT * FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
            if not acct:
                return None
            cash = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            positions = conn.execute(
                """
                SELECT symbol, qty FROM ledger_balance
                WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                ORDER BY symbol
                """,
                (account_id,),
            ).fetchall()
            try:
                sleeves = conn.execute(
                    """
                    SELECT strategy_version, symbol, qty, updated_at
                    FROM ledger_sleeve_position
                    WHERE account_id=? AND qty<>0
                    ORDER BY strategy_version, symbol
                    """,
                    (account_id,),
                ).fetchall()
            except Exception:  # noqa: BLE001
                sleeves = []
            try:
                lots = conn.execute(
                    """
                    SELECT lot_id, symbol, buy_date, qty_remaining,
                           COALESCE(strategy_version, '') AS strategy_version,
                           fill_id, created_at
                    FROM ledger_lot
                    WHERE account_id=? AND qty_remaining>0
                    ORDER BY buy_date, symbol
                    LIMIT 200
                    """,
                    (account_id,),
                ).fetchall()
            except Exception:  # noqa: BLE001
                lots = []
            postings = conn.execute(
                """
                SELECT posting_id, execution_id, status, as_of_date, entry_count,
                       cash_after, error_message, created_at, finished_at
                FROM ledger_posting
                WHERE account_id=?
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (account_id,),
            ).fetchall()
        d = dict(acct)
        d["cash"] = float(cash["qty"]) if cash else float(d.get("opening_cash") or 0)
        d["positions"] = [dict(p) for p in positions]
        d["sleeves"] = [dict(s) for s in sleeves]
        d["lots"] = [dict(x) for x in lots]
        d["postings"] = [dict(p) for p in postings]
        return d

    def mark_ledger_nav(self, account_id: str, as_of: str) -> dict[str, Any]:
        """Mark positions with latest raw close <= as_of (paper NAV)."""
        day = (as_of or "")[:10]
        if not day:
            return {}
        with get_conn() as conn:
            cash_row = conn.execute(
                """
                SELECT qty FROM ledger_balance
                WHERE account_id=? AND asset_type='CASH' AND symbol=''
                """,
                (account_id,),
            ).fetchone()
            acct = conn.execute(
                "SELECT opening_cash FROM ledger_account WHERE account_id=?",
                (account_id,),
            ).fetchone()
            cash = (
                float(cash_row["qty"])
                if cash_row
                else float(acct["opening_cash"] if acct else 0)
            )
            try:
                pos_rows = conn.execute(
                    """
                    SELECT symbol, SUM(qty) AS qty
                    FROM ledger_sleeve_position
                    WHERE account_id=? AND qty<>0
                    GROUP BY symbol
                    ORDER BY symbol
                    """,
                    (account_id,),
                ).fetchall()
            except Exception:  # noqa: BLE001
                pos_rows = conn.execute(
                    """
                    SELECT symbol, qty
                    FROM ledger_balance
                    WHERE account_id=? AND asset_type='POSITION' AND qty<>0
                    ORDER BY symbol
                    """,
                    (account_id,),
                ).fetchall()
            marked: list[dict[str, Any]] = []
            market_value = 0.0
            missing = 0
            for r in pos_rows:
                sym = str(r["symbol"] or "")
                qty = float(r["qty"] or 0)
                if not sym or qty == 0:
                    continue
                bar = conn.execute(
                    """
                    SELECT trade_date, close
                    FROM processed_equity_bar_1d
                    WHERE symbol=? AND trade_date<=? AND factor_type='qfq'
                    ORDER BY trade_date DESC
                    LIMIT 1
                    """,
                    (sym, day),
                ).fetchone()
                if not bar:
                    bar = conn.execute(
                        """
                        SELECT trade_date, close
                        FROM processed_equity_bar_1d
                        WHERE symbol=? AND trade_date<=?
                        ORDER BY trade_date DESC
                        LIMIT 1
                        """,
                        (sym, day),
                    ).fetchone()
                # close = 未复权收盘；纸面持仓按实物股数计价
                px = float(bar["close"]) if bar and bar["close"] is not None else None
                mv = (px * qty) if px is not None else None
                if mv is None:
                    missing += 1
                else:
                    market_value += mv
                marked.append(
                    {
                        "symbol": sym,
                        "qty": qty,
                        "price": px,
                        "market_value": mv,
                        "price_date": (
                            str(bar["trade_date"])[:10] if bar else None
                        ),
                    }
                )
        nav = cash + market_value
        opening = float(acct["opening_cash"]) if acct and acct["opening_cash"] is not None else cash
        return {
            "as_of": day,
            "cash": cash,
            "market_value": market_value,
            "nav": nav,
            "pnl": nav - opening,
            "pnl_pct": (nav / opening - 1.0) if opening else None,
            "position_count": len(marked),
            "missing_prices": missing,
            "marked_positions": marked,
        }

    def list_alerts(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ops_alert
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_audit(self, row: dict[str, Any]) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO api_audit_log (
                    audit_id, actor, method, path, status_code,
                    request_json, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["audit_id"],
                    row.get("actor"),
                    row["method"],
                    row["path"],
                    row.get("status_code"),
                    json.dumps(row.get("request") or {}, ensure_ascii=False),
                    json.dumps(row.get("result") or {}, ensure_ascii=False),
                    row["created_at"],
                ),
            )

    # ── Phase extensions: backtest / search / min bars / boards / DQ / F10 / events ──

    def list_backtest_runs(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT run_id, strategy_code, status, start_date, end_date,
                   universe_code, factor_type, benchmark_index, initial_cash,
                   final_nav, total_return, benchmark_return, max_drawdown,
                   trade_count, job_id, error_message, created_at, finished_at
            FROM backtest_run WHERE 1=1
        """
        params: list[Any] = []
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_backtest_run(self, run_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_run WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            nav = conn.execute(
                """
                SELECT trade_date, nav, cash, market_value, benchmark_nav
                FROM backtest_nav WHERE run_id=?
                ORDER BY trade_date
                """,
                (run_id,),
            ).fetchall()
            trades = conn.execute(
                """
                SELECT trade_date, symbol, side, shares, price, amount, cost, reason
                FROM backtest_trade WHERE run_id=?
                ORDER BY trade_date, symbol
                """,
                (run_id,),
            ).fetchall()
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        d["nav"] = [dict(r) for r in nav]
        d["trades"] = [dict(r) for r in trades]
        return d

    def search_securities(
        self,
        *,
        q: str,
        as_of: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = (q or "").strip()
        if not query:
            return []
        lim = max(1, min(limit, 50))
        as_of_d = (as_of or "9999-12-31")[:10]
        like = f"%{query}%"
        prefix = f"{query}%"
        sql = """
            SELECT DISTINCT ON (symbol)
                   symbol, name, exchange, board, list_date, delist_date, effective_date
            FROM raw_security_listing
            WHERE effective_date<=?
              AND (symbol LIKE ? OR symbol LIKE ? OR name LIKE ?)
            ORDER BY symbol, effective_date DESC
            LIMIT ?
        """
        # Prefer exact/prefix code hits: fetch then re-rank in Python
        with get_conn() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    sql, (as_of_d, prefix, like, like, lim * 3)
                ).fetchall()
            ]
        bare = _bare_symbol(query)
        def score(r: dict[str, Any]) -> tuple[int, str]:
            sym = str(r.get("symbol") or "")
            name = str(r.get("name") or "")
            if sym == bare or sym == query:
                return (0, sym)
            if sym.startswith(bare) or sym.startswith(query):
                return (1, sym)
            if query in name:
                return (2, sym)
            return (3, sym)
        rows.sort(key=score)
        return rows[:lim]

    def list_equity_min_bars(
        self,
        *,
        symbol: str,
        freq: str = "15m",
        start: str | None = None,
        end: str | None = None,
        factor_type: str = "qfq",
        limit: int = 240,
    ) -> list[dict[str, Any]]:
        sym = _bare_symbol(symbol)
        if not sym:
            return []
        fq = (freq or "15m").strip().lower()
        if fq not in ("15m", "60m"):
            fq = "15m"
        ft = (factor_type or "qfq").strip() or "qfq"
        lim = max(1, min(int(limit), 2000))
        params: list[Any] = [sym, fq, ft]
        date_clause = ""
        if start:
            date_clause += " AND bar_time>=?"
            params.append(f"{start[:10]} 00:00:00")
        if end:
            date_clause += " AND bar_time<=?"
            params.append(f"{end[:10]} 23:59:59")
        sql = f"""
            SELECT * FROM (
                SELECT symbol, bar_time, freq, factor_type,
                       open, high, low, close, volume, amount,
                       adj_open, adj_high, adj_low, adj_close, adj_factor, source
                FROM processed_equity_bar_min
                WHERE symbol=? AND freq=? AND factor_type=?{date_clause}
                ORDER BY bar_time DESC
                LIMIT ?
            ) t
            ORDER BY bar_time ASC
        """
        params.append(lim)
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        out: list[dict[str, Any]] = []
        for r in rows:
            o = r.get("adj_open") if r.get("adj_open") is not None else r.get("open")
            h = r.get("adj_high") if r.get("adj_high") is not None else r.get("high")
            l = r.get("adj_low") if r.get("adj_low") is not None else r.get("low")
            c = r.get("adj_close") if r.get("adj_close") is not None else r.get("close")
            out.append(
                {
                    "symbol": r.get("symbol"),
                    "bar_time": str(r.get("bar_time") or ""),
                    "trade_date": str(r.get("bar_time") or "")[:10],
                    "freq": r.get("freq"),
                    "factor_type": r.get("factor_type"),
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": r.get("volume"),
                    "amount": r.get("amount"),
                    "source": r.get("source"),
                }
            )
        return out

    def list_board_bars(
        self,
        *,
        trade_date: str | None = None,
        board_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT board_type, board_code, board_name, trade_date,
                   open, high, low, close, volume, amount, pct_chg, turnover, source
            FROM raw_board_bar_1d WHERE 1=1
        """
        params: list[Any] = []
        if trade_date:
            sql += " AND trade_date=?"
            params.append(trade_date[:10])
        else:
            sql += """
                AND trade_date=(SELECT MAX(trade_date) FROM raw_board_bar_1d)
            """
        if board_type:
            sql += " AND board_type=?"
            params.append(board_type.strip().upper())
        sql += " ORDER BY pct_chg DESC NULLS LAST, amount DESC NULLS LAST LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_board_history(
        self,
        *,
        board_name: str,
        board_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        name = (board_name or "").strip()
        if not name:
            return []
        sql = """
            SELECT board_type, board_code, board_name, trade_date,
                   open, high, low, close, volume, amount, pct_chg, turnover, source
            FROM raw_board_bar_1d WHERE board_name=?
        """
        params: list[Any] = [name]
        if board_type:
            sql += " AND board_type=?"
            params.append(board_type.strip().upper())
        if start:
            sql += " AND trade_date>=?"
            params.append(start[:10])
        if end:
            sql += " AND trade_date<=?"
            params.append(end[:10])
        sql = f"""
            SELECT * FROM (
                {sql}
                ORDER BY trade_date DESC
                LIMIT ?
            ) t ORDER BY trade_date ASC
        """
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_board_members(
        self,
        *,
        industry_name: str | None = None,
        industry_code: str | None = None,
        as_of: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        as_of_d = (as_of or "9999-12-31")[:10]
        sql = """
            SELECT DISTINCT ON (symbol)
                   symbol, standard, industry_code, industry_name, effective_date, source
            FROM raw_industry_class
            WHERE effective_date<=?
        """
        params: list[Any] = [as_of_d]
        if industry_code:
            sql += " AND industry_code=?"
            params.append(industry_code.strip())
        if industry_name:
            sql += " AND industry_name=?"
            params.append(industry_name.strip())
        sql += " ORDER BY symbol, effective_date DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_dq_runs(self, *, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
            SELECT dq_run_id, scope, status, start_date, end_date, factor_type,
                   job_id, summary_json, created_at, finished_at
            FROM dq_run WHERE 1=1
        """
        params: list[Any] = []
        if scope:
            sql += " AND scope=?"
            params.append(scope.strip().upper())
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for r in rows:
            try:
                r["summary"] = json.loads(str(r.pop("summary_json", None) or "{}"))
            except json.JSONDecodeError:
                r["summary"] = {}
        return rows

    def get_dq_run(self, dq_run_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM dq_run WHERE dq_run_id=?",
                (dq_run_id,),
            ).fetchone()
            if not row:
                return None
            results = conn.execute(
                """
                SELECT rule_code, severity, status, message, detail_json, checked_at
                FROM dq_result WHERE dq_run_id=?
                ORDER BY checked_at DESC
                """,
                (dq_run_id,),
            ).fetchall()
        d = dict(row)
        for key in ("meta_json", "summary_json"):
            name = key.replace("_json", "")
            try:
                d[name] = json.loads(str(d.pop(key, None) or "{}"))
            except json.JSONDecodeError:
                d[name] = {}
        out_results: list[dict[str, Any]] = []
        for r in results:
            rd = dict(r)
            try:
                rd["detail"] = json.loads(str(rd.pop("detail_json", None) or "{}"))
            except json.JSONDecodeError:
                rd["detail"] = {}
            out_results.append(rd)
        d["results"] = out_results
        return d

    def list_dq_gates(self, *, scope: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = """
            SELECT scope, start_date, end_date, factor_type, status, dq_run_id, updated_at
            FROM dq_gate WHERE 1=1
        """
        params: list[Any] = []
        if scope:
            sql += " AND scope=?"
            params.append(scope.strip().upper())
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_f10(self, symbol: str, *, as_of: str | None = None) -> dict[str, Any] | None:
        sym = _bare_symbol(symbol)
        if not sym:
            return None
        as_of_d = (as_of or "9999-12-31")[:10]
        with get_conn() as conn:
            listing = conn.execute(
                """
                SELECT symbol, name, exchange, board, list_date, delist_date, effective_date
                FROM raw_security_listing
                WHERE symbol=? AND effective_date<=?
                ORDER BY effective_date DESC LIMIT 1
                """,
                (sym, as_of_d),
            ).fetchone()
            industry = conn.execute(
                """
                SELECT industry_code, industry_name, standard, effective_date, source
                FROM raw_industry_class
                WHERE symbol=? AND effective_date<=?
                ORDER BY effective_date DESC LIMIT 1
                """,
                (sym, as_of_d),
            ).fetchone()
            valuation = conn.execute(
                """
                SELECT trade_date, pe_ttm, pe_static, pb, ps_ttm, pcf_ttm, peg,
                       total_mv, float_mv
                FROM raw_valuation_1d
                WHERE symbol=? AND trade_date<=?
                ORDER BY trade_date DESC LIMIT 1
                """,
                (sym, as_of_d),
            ).fetchone()
            fund = conn.execute(
                """
                SELECT report_period, publish_date, valid_from, valid_to,
                       revenue, net_profit, total_assets, total_liabilities, roe, eps
                FROM processed_fund_snapshot
                WHERE symbol=? AND valid_from<=?
                  AND (valid_to IS NULL OR CAST(valid_to AS TEXT)>=?)
                ORDER BY valid_from DESC LIMIT 1
                """,
                (sym, as_of_d, as_of_d),
            ).fetchone()
            holders = conn.execute(
                """
                SELECT asof_date, announce_date, holder_count, holder_change_pct, avg_market_cap
                FROM raw_holder_count
                WHERE symbol=? AND asof_date<=?
                ORDER BY asof_date DESC LIMIT 1
                """,
                (sym, as_of_d),
            ).fetchone()
            share = conn.execute(
                """
                SELECT total_shares, float_shares, effective_date
                FROM raw_share_capital
                WHERE symbol=? AND effective_date<=?
                ORDER BY effective_date DESC LIMIT 1
                """,
                (sym, as_of_d),
            ).fetchone()
        if not any([listing, industry, valuation, fund, holders, share]):
            return None
        return {
            "symbol": sym,
            "as_of": as_of_d if as_of else None,
            "listing": dict(listing) if listing else None,
            "industry": dict(industry) if industry else None,
            "valuation": dict(valuation) if valuation else None,
            "fundamentals": dict(fund) if fund else None,
            "holders": dict(holders) if holders else None,
            "share_capital": dict(share) if share else None,
        }

    def list_market_events(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Unified corp events: unlock / corp_action / major_contract / announcement."""
        lim = max(1, min(limit, 300))
        start_d = (start or "1970-01-01")[:10]
        end_d = (end or "9999-12-31")[:10]
        sym = _bare_symbol(symbol) if symbol else ""
        events: list[dict[str, Any]] = []
        with get_conn() as conn:
            # unlock
            sql = """
                SELECT release_date AS event_date, symbol, name,
                       share_type, release_shares, actual_mv, float_ratio, source
                FROM raw_restricted_release
                WHERE release_date>=? AND release_date<=?
            """
            params: list[Any] = [start_d, end_d]
            if sym:
                sql += " AND symbol=?"
                params.append(sym)
            sql += " ORDER BY release_date DESC LIMIT ?"
            params.append(lim)
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                events.append(
                    {
                        "event_type": "unlock",
                        "event_date": str(d.get("event_date") or "")[:10],
                        "symbol": d.get("symbol"),
                        "title": f"解禁 {d.get('name') or d.get('symbol') or ''}".strip(),
                        "detail": d,
                    }
                )
            # corp action
            sql = """
                SELECT ex_date AS event_date, symbol, action_type, source, raw_payload
                FROM raw_corp_action
                WHERE ex_date>=? AND ex_date<=?
            """
            params = [start_d, end_d]
            if sym:
                sql += " AND symbol=?"
                params.append(sym)
            sql += " ORDER BY ex_date DESC LIMIT ?"
            params.append(lim)
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                events.append(
                    {
                        "event_type": "corp_action",
                        "event_date": str(d.get("event_date") or "")[:10],
                        "symbol": d.get("symbol"),
                        "title": f"公司行为 {d.get('action_type') or ''}".strip(),
                        "detail": {
                            k: d.get(k)
                            for k in ("action_type", "source", "raw_payload")
                        },
                    }
                )
            # major contract
            sql = """
                SELECT announce_date AS event_date, symbol, contract_type, contract_name,
                       amount, is_win_bid, source
                FROM raw_major_contract
                WHERE announce_date>=? AND announce_date<=?
            """
            params = [start_d, end_d]
            if sym:
                sql += " AND symbol=?"
                params.append(sym)
            sql += " ORDER BY announce_date DESC LIMIT ?"
            params.append(lim)
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                events.append(
                    {
                        "event_type": "major_contract",
                        "event_date": str(d.get("event_date") or "")[:10],
                        "symbol": d.get("symbol"),
                        "title": str(d.get("contract_name") or d.get("contract_type") or "重大合同"),
                        "detail": d,
                    }
                )
            # announcements
            sql = """
                SELECT CAST(publish_time AS TEXT) AS event_date, symbol, title,
                       category_norm, category_raw, url, channel, source
                FROM raw_announcement
                WHERE CAST(publish_time AS TEXT)>=? AND CAST(publish_time AS TEXT)<=?
            """
            params = [start_d, end_d + " 23:59:59"]
            if sym:
                sql += " AND symbol=?"
                params.append(sym)
            sql += " ORDER BY publish_time DESC LIMIT ?"
            params.append(lim)
            for r in conn.execute(sql, tuple(params)).fetchall():
                d = dict(r)
                events.append(
                    {
                        "event_type": "announcement",
                        "event_date": str(d.get("event_date") or "")[:10],
                        "symbol": d.get("symbol"),
                        "title": d.get("title") or "公告",
                        "detail": d,
                    }
                )
        events.sort(key=lambda e: (e.get("event_date") or "", e.get("event_type") or ""), reverse=True)
        return events[:lim]

    def list_econ_calendar(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Macro/policy calendar: trade days + policy/econ news in range."""
        lim = max(1, min(limit, 300))
        start_d = (start or "1970-01-01")[:10]
        end_d = (end or "9999-12-31")[:10]
        with get_conn() as conn:
            trade_days = conn.execute(
                """
                SELECT trade_date, exchange, is_open, is_half_day
                FROM raw_trade_calendar
                WHERE trade_date>=? AND trade_date<=?
                ORDER BY trade_date
                LIMIT ?
                """,
                (start_d, end_d, lim),
            ).fetchall()
            news = conn.execute(
                """
                SELECT CAST(publish_time AS TEXT) AS publish_time, channel, title,
                       symbol, url, source
                FROM raw_news_media
                WHERE CAST(publish_time AS TEXT)>=? AND CAST(publish_time AS TEXT)<=?
                  AND (
                    channel IN ('policy', 'econ', 'official')
                    OR channel LIKE '%policy%'
                    OR channel LIKE '%econ%'
                  )
                ORDER BY publish_time DESC
                LIMIT ?
                """,
                (start_d, end_d + " 23:59:59", lim),
            ).fetchall()
        return {
            "start": start_d,
            "end": end_d,
            "trade_days": [dict(r) for r in trade_days],
            "macro_news": [dict(r) for r in news],
        }

    def list_module_catalog(self) -> dict[str, Any]:
        """后端模块地图 + 表行数，供运维台导航。"""

        def _count(conn: Any, sql: str) -> int:
            try:
                row = conn.execute(sql).fetchone()
                return int(row["n"] if row else 0)
            except Exception:  # noqa: BLE001
                return 0

        with get_conn() as conn:
            counts = {
                "ingest_batch": _count(conn, "SELECT COUNT(*) AS n FROM ingest_batch"),
                "universe_snapshot": _count(
                    conn, "SELECT COUNT(*) AS n FROM universe_snapshot"
                ),
                "dq_run": _count(conn, "SELECT COUNT(*) AS n FROM dq_run"),
                "research_run": _count(conn, "SELECT COUNT(*) AS n FROM research_run"),
                "research_evidence_freeze": _count(
                    conn, "SELECT COUNT(*) AS n FROM research_evidence_freeze"
                ),
                "backtest_run": _count(conn, "SELECT COUNT(*) AS n FROM backtest_run"),
                "strategy_version": _count(
                    conn, "SELECT COUNT(*) AS n FROM strategy_version"
                ),
                "signal_batch": _count(conn, "SELECT COUNT(*) AS n FROM signal_batch"),
                "portfolio_target": _count(
                    conn, "SELECT COUNT(*) AS n FROM portfolio_target"
                ),
                "risk_decision": _count(conn, "SELECT COUNT(*) AS n FROM risk_decision"),
                "execution_run": _count(conn, "SELECT COUNT(*) AS n FROM execution_run"),
                "execution_adapter_params": _count(
                    conn, "SELECT COUNT(*) AS n FROM execution_adapter_params"
                ),
                "ledger_posting": _count(
                    conn, "SELECT COUNT(*) AS n FROM ledger_posting"
                ),
                "ops_alert": _count(conn, "SELECT COUNT(*) AS n FROM ops_alert"),
                "process_batch": _count(
                    conn, "SELECT COUNT(*) AS n FROM process_batch"
                ),
                "research_factor_value": _count(
                    conn, "SELECT COUNT(*) AS n FROM research_factor_value"
                ),
                "cost_params": _count(conn, "SELECT COUNT(*) AS n FROM cost_params"),
                "risk_limits": _count(conn, "SELECT COUNT(*) AS n FROM risk_limits"),
                "promotion_gate_result": _count(
                    conn, "SELECT COUNT(*) AS n FROM promotion_gate_result"
                ),
                "strategy_capital_alloc": _count(
                    conn, "SELECT COUNT(*) AS n FROM strategy_capital_alloc"
                ),
                "api_audit_log": _count(
                    conn, "SELECT COUNT(*) AS n FROM api_audit_log"
                ),
                "ledger_account": _count(
                    conn, "SELECT COUNT(*) AS n FROM ledger_account"
                ),
            }

        modules = [
            {
                "id": "data_ingest",
                "name": "取数",
                "path": "backend/data_ingest",
                "route": "/data/ingest",
                "count_key": "ingest_batch",
                "desc": "CORE/ALPHA 外部取数批次",
            },
            {
                "id": "data_process",
                "name": "加工",
                "path": "backend/data_process",
                "route": "/data/process",
                "count_key": "process_batch",
                "desc": "复权/掩码/技术指标加工批次",
            },
            {
                "id": "data_quality",
                "name": "数据质量",
                "path": "backend/data_quality",
                "route": "/data/quality",
                "count_key": "dq_run",
                "desc": "DQ 规则与门禁",
            },
            {
                "id": "security_master",
                "name": "Universe",
                "path": "backend/security_master",
                "route": "/data/universe",
                "count_key": "universe_snapshot",
                "desc": "证券主数据与日快照",
            },
            {
                "id": "research_lab",
                "name": "研究实验",
                "path": "backend/research_lab",
                "route": "/research",
                "count_key": "research_run",
                "desc": "因子/IC/证据包",
            },
            {
                "id": "research_factors",
                "name": "因子值",
                "path": "backend/research_lab",
                "route": "/research/factors",
                "count_key": "research_factor_value",
                "desc": "research_factor_value 截面",
            },
            {
                "id": "evidence_freeze",
                "name": "证据冻结",
                "path": "backend/research_lab",
                "route": "/research/freezes",
                "count_key": "research_evidence_freeze",
                "desc": "OOS 证据冻结产物",
            },
            {
                "id": "ref_params",
                "name": "参考参数",
                "path": "database/seeds",
                "route": "/system/params",
                "count_key": "cost_params",
                "desc": "费用 / 风控限额 / 晋升门阈值",
            },
            {
                "id": "capital_alloc",
                "name": "资本配额",
                "path": "backend/portfolio_construct",
                "route": "/portfolio/capital",
                "count_key": "strategy_capital_alloc",
                "desc": "同账户多策略 NAV 切分",
            },
            {
                "id": "backtest",
                "name": "回测",
                "path": "backend/backtest",
                "route": "/backtest",
                "count_key": "backtest_run",
                "desc": "A 股约束回测",
            },
            {
                "id": "strategy_registry",
                "name": "策略注册",
                "path": "backend/strategy_registry",
                "route": "/strategies",
                "count_key": "strategy_version",
                "desc": "版本与晋升质量门",
            },
            {
                "id": "signal_prod",
                "name": "生产信号",
                "path": "backend/signal_prod",
                "route": "/signals",
                "count_key": "signal_batch",
                "desc": "已晋升策略日更权重",
            },
            {
                "id": "portfolio_construct",
                "name": "组合构建",
                "path": "backend/portfolio_construct",
                "route": "/portfolio",
                "count_key": "portfolio_target",
                "desc": "目标持仓草稿",
            },
            {
                "id": "risk_engine",
                "name": "风控",
                "path": "backend/risk_engine",
                "route": "/risk",
                "count_key": "risk_decision",
                "desc": "硬规则与 Kill Switch",
            },
            {
                "id": "execution",
                "name": "执行 OMS",
                "path": "backend/execution",
                "route": "/trade",
                "count_key": "execution_run",
                "desc": "纸面委托/成交/残差",
            },
            {
                "id": "execution_adapters",
                "name": "执行适配器",
                "path": "backend/execution/adapters",
                "route": "/system/adapters",
                "count_key": "execution_adapter_params",
                "desc": "paper / stub / live_gated",
            },
            {
                "id": "ledger",
                "name": "账本",
                "path": "backend/ledger",
                "route": "/ledger",
                "count_key": "ledger_posting",
                "desc": "过账与 T+1 可卖",
            },
            {
                "id": "ops_monitor",
                "name": "运维告警",
                "path": "backend/ops_monitor",
                "route": "/ops",
                "count_key": "ops_alert",
                "desc": "告警与覆盖度",
            },
            {
                "id": "orchestrator",
                "name": "编排",
                "path": "backend/orchestrator",
                "route": "/ops/schedule",
                "count_key": None,
                "desc": "日更 schedule / 活动时间线",
            },
            {
                "id": "api_audit",
                "name": "API 审计",
                "path": "backend/api_gateway",
                "route": "/system/audit",
                "count_key": "api_audit_log",
                "desc": "写操作审计日志",
            },
            {
                "id": "api_gateway",
                "name": "API 网关",
                "path": "backend/api_gateway",
                "route": "/settings",
                "count_key": None,
                "desc": "前端唯一入口",
            },
            {
                "id": "market_f10",
                "name": "F10 资料",
                "path": "backend/api_gateway",
                "route": "/market/f10",
                "count_key": None,
                "desc": "上市/估值/基本面聚合",
            },
        ]
        for m in modules:
            key = m.get("count_key")
            m["count"] = int(counts.get(key, 0)) if key else None
        return {"modules": modules, "counts": counts}

    def get_signal_batch(self, signal_batch_id: str) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM signal_batch WHERE signal_batch_id=?",
                (signal_batch_id,),
            ).fetchone()
            if not row:
                return None
            weights = conn.execute(
                """
                SELECT strategy_version, trade_date, symbol, weight, signal_value,
                       signal_batch_id, created_at
                FROM signal_prod_weight
                WHERE signal_batch_id=?
                ORDER BY weight DESC, symbol
                LIMIT 500
                """,
                (signal_batch_id,),
            ).fetchall()
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        d["weights"] = [dict(w) for w in weights]
        return d

    def list_universe_snapshots(
        self,
        *,
        universe_code: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM universe_snapshot WHERE 1=1"
        params: list[Any] = []
        if universe_code:
            sql += " AND universe_code=?"
            params.append(universe_code)
        sql += " ORDER BY as_of_date DESC, universe_code LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def get_universe_snapshot(
        self, universe_snapshot_id: str
    ) -> dict[str, Any] | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM universe_snapshot WHERE universe_snapshot_id=?",
                (universe_snapshot_id,),
            ).fetchone()
            if not row:
                return None
            members = conn.execute(
                """
                SELECT symbol, name, exchange, board, industry_code, industry_name,
                       is_st, treat_type, index_weight, is_eligible
                FROM universe_snapshot_member
                WHERE universe_snapshot_id=?
                ORDER BY COALESCE(index_weight, 0) DESC, symbol
                LIMIT 500
                """,
                (universe_snapshot_id,),
            ).fetchall()
        d = dict(row)
        try:
            d["meta"] = json.loads(str(d.get("meta_json") or "{}"))
        except json.JSONDecodeError:
            d["meta"] = {}
        d["members"] = [dict(m) for m in members]
        return d

    def list_ingest_batches(
        self,
        *,
        lane: str | None = None,
        module: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ingest_batch WHERE 1=1"
        params: list[Any] = []
        if lane:
            sql += " AND lane=?"
            params.append(lane)
        if module:
            sql += " AND ingest_module=?"
            params.append(module)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for d in rows:
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
        return rows

    def list_execution_adapters(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT kind, enabled, allow_fills, require_live_env, meta_json, created_at
                FROM execution_adapter_params
                ORDER BY kind
                """
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            d["enabled"] = bool(int(d.get("enabled") or 0))
            d["allow_fills"] = bool(int(d.get("allow_fills") or 0))
            d["require_live_env"] = bool(int(d.get("require_live_env") or 0))
            out.append(d)
        return out

    def list_evidence_freezes(self, *, limit: int = 50) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 200))
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT freeze_id, evidence_run_id, universe_code, start_date, end_date,
                       status, split_mode, hard_gates_json, summary_json, artifact_hash,
                       actor, reason, created_at
                FROM research_evidence_freeze
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            for key in ("hard_gates_json", "summary_json"):
                raw = d.pop(key, None)
                name = key.replace("_json", "")
                try:
                    d[name] = json.loads(str(raw or "{}"))
                except json.JSONDecodeError:
                    d[name] = {}
            out.append(d)
        return out

    def list_process_batches(
        self, *, kind: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM process_batch WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND process_kind=?"
            params.append(kind)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        for d in rows:
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
        return rows

    def list_cost_params(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cost_params ORDER BY version"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    def list_risk_limits(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM risk_limits ORDER BY version"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    def list_promotion_gate_params(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM promotion_gate_params ORDER BY version"
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["thresholds"] = json.loads(
                    str(d.pop("thresholds_json", None) or "{}")
                )
            except json.JSONDecodeError:
                d["thresholds"] = {}
            try:
                d["meta"] = json.loads(str(d.pop("meta_json", None) or "{}"))
            except json.JSONDecodeError:
                d["meta"] = {}
            out.append(d)
        return out

    def list_promotion_gate_results(self, *, limit: int = 50) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 200))
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM promotion_gate_result
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            for key in ("metrics_json", "checks_json"):
                raw = d.pop(key, None)
                name = key.replace("_json", "")
                try:
                    d[name] = json.loads(str(raw or "{}"))
                except json.JSONDecodeError:
                    d[name] = {}
            d["passed"] = bool(int(d.get("passed") or 0))
            d["skipped"] = bool(int(d.get("skipped") or 0))
            out.append(d)
        return out

    def list_capital_alloc(
        self, *, account_id: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM strategy_capital_alloc WHERE 1=1"
        params: list[Any] = []
        if account_id:
            sql += " AND account_id=?"
            params.append(account_id)
        sql += " ORDER BY account_id, strategy_version"
        with get_conn() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def list_factor_catalog(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT factor_code, universe_code,
                       COUNT(*) AS row_count,
                       COUNT(DISTINCT symbol) AS symbol_count,
                       MIN(trade_date) AS min_date,
                       MAX(trade_date) AS max_date
                FROM research_factor_value
                GROUP BY factor_code, universe_code
                ORDER BY factor_code, universe_code
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def list_factor_values(
        self,
        *,
        factor_code: str,
        universe_code: str | None = None,
        as_of: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        code = (factor_code or "").strip()
        if not code:
            return {"factor_code": "", "count": 0, "items": []}
        lim = max(1, min(limit, 500))
        day = (as_of or "")[:10] or None
        sql = """
            SELECT factor_code, symbol, trade_date, value, universe_code, run_id
            FROM research_factor_value
            WHERE factor_code=?
        """
        params: list[Any] = [code]
        if universe_code:
            sql += " AND universe_code=?"
            params.append(universe_code)
        if day:
            sql += " AND trade_date=?"
            params.append(day)
        sql += " ORDER BY trade_date DESC, value DESC NULLS LAST, symbol LIMIT ?"
        params.append(lim)
        with get_conn() as conn:
            rows = [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
        return {
            "factor_code": code,
            "universe_code": universe_code,
            "as_of": day,
            "count": len(rows),
            "items": rows,
        }

    def list_audit_logs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        lim = max(1, min(limit, 200))
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT audit_id, actor, method, path, status_code,
                       request_json, result_json, created_at
                FROM api_audit_log
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            for key in ("request_json", "result_json"):
                raw = d.pop(key, None)
                name = key.replace("_json", "")
                try:
                    d[name] = json.loads(str(raw or "{}"))
                except json.JSONDecodeError:
                    d[name] = {}
            out.append(d)
        return out

    def list_ledger_accounts(self) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT a.account_id, a.currency, a.opening_cash, a.status,
                       a.created_at,
                       (
                         SELECT qty FROM ledger_balance b
                         WHERE b.account_id=a.account_id
                           AND b.asset_type='CASH' AND b.symbol=''
                       ) AS cash
                FROM ledger_account a
                ORDER BY a.account_id
                """
            ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("cash") is None:
                d["cash"] = float(d.get("opening_cash") or 0)
            out.append(d)
        return out

    def list_ops_activity(self, *, limit: int = 40) -> list[dict[str, Any]]:
        """跨模块最近活动时间线（只读合并）。"""
        lim = max(1, min(limit, 100))
        per = max(5, lim // 4)
        events: list[dict[str, Any]] = []
        with get_conn() as conn:
            queries = [
                (
                    "ingest",
                    """
                    SELECT batch_id AS ref_id, status, created_at,
                           lane || '/' || ingest_module || '/' || ingest_kind AS label
                    FROM ingest_batch
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
                (
                    "process",
                    """
                    SELECT process_batch_id AS ref_id, status, created_at,
                           process_kind AS label
                    FROM process_batch
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
                (
                    "dq",
                    """
                    SELECT dq_run_id AS ref_id, status, created_at,
                           scope AS label
                    FROM dq_run
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
                (
                    "signal",
                    """
                    SELECT signal_batch_id AS ref_id, status,
                           CAST(created_at AS TEXT) AS created_at,
                           strategy_version AS label
                    FROM signal_batch
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
                (
                    "execution",
                    """
                    SELECT execution_id AS ref_id, status,
                           CAST(created_at AS TEXT) AS created_at,
                           COALESCE(adapter, 'paper') AS label
                    FROM execution_run
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
                (
                    "alert",
                    """
                    SELECT alert_id AS ref_id, COALESCE(status, 'open') AS status,
                           CAST(created_at AS TEXT) AS created_at,
                           COALESCE(code, severity) AS label
                    FROM ops_alert
                    ORDER BY created_at DESC LIMIT ?
                    """,
                ),
            ]
            for kind, sql in queries:
                try:
                    rows = conn.execute(sql, (per,)).fetchall()
                except Exception:  # noqa: BLE001
                    continue
                for r in rows:
                    d = dict(r)
                    events.append(
                        {
                            "kind": kind,
                            "ref_id": d.get("ref_id"),
                            "status": d.get("status"),
                            "label": d.get("label"),
                            "created_at": str(d.get("created_at") or ""),
                        }
                    )
        events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
        return events[:lim]
