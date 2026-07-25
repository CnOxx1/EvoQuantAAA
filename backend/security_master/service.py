from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from security_master.models import (
    P0_UNIVERSES,
    UniverseBuildRequest,
    UniverseBuildResult,
    UniverseCode,
)
from security_master.repository import SecurityMasterRepository

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _score_symbol(
    sym: str,
    *,
    shares: dict[str, dict[str, Any]],
    closes: dict[str, float],
) -> tuple[float | None, str]:
    """
    排名分：优先 股本×收盘（近似市值）；无收盘则用流通/总股本。
    返回 (score, metric_name)。
    """
    cap = shares.get(sym) or {}
    total = cap.get("total_shares")
    float_s = cap.get("float_shares")
    try:
        total_f = float(total) if total is not None else None
    except (TypeError, ValueError):
        total_f = None
    try:
        float_f = float(float_s) if float_s is not None else None
    except (TypeError, ValueError):
        float_f = None
    px = closes.get(sym)
    if total_f and total_f > 0 and px:
        return total_f * px, "total_shares*close"
    if float_f and float_f > 0 and px:
        return float_f * px, "float_shares*close"
    if float_f and float_f > 0:
        return float_f, "float_shares"
    if total_f and total_f > 0:
        return total_f, "total_shares"
    return None, "none"


class SecurityMasterService:
    def __init__(self, *, repo: SecurityMasterRepository | None = None) -> None:
        self.repo = repo or SecurityMasterRepository()

    def build(self, request: UniverseBuildRequest) -> UniverseBuildResult:
        as_of, adjusted = self.repo.resolve_as_of(request.as_of_date)
        if adjusted and not request.allow_non_open_day:
            return UniverseBuildResult(
                status="failed",
                universe_snapshot_id="",
                universe_code=request.universe_code,
                as_of_date=request.as_of_date[:10],
                message=f"{request.as_of_date} 非开市日",
            )

        listings = self.repo.load_listings(
            as_of=as_of, preferred_source=request.preferred_source
        )
        if not listings:
            return UniverseBuildResult(
                status="failed",
                universe_snapshot_id="",
                universe_code=request.universe_code,
                as_of_date=as_of,
                message="无可用上市名单（请先跑 core_ref listing）",
            )

        industry = self.repo.load_industry_map(
            as_of=as_of,
            standard=request.industry_standard,
            preferred_source=request.preferred_source,
        )
        st_map = self.repo.load_st_map(as_of=as_of)
        index_rows: list[dict[str, Any]] = []
        index_set: set[str] = set()
        if request.universe_code in ("HS300", "HS300_EX_ST"):
            index_rows = self.repo.load_index_members(
                index_symbol=request.index_symbol,
                as_of=as_of,
                preferred_source=request.preferred_source,
            )
            index_set = {str(r["symbol"]) for r in index_rows}
            if not index_set:
                return UniverseBuildResult(
                    status="failed",
                    universe_snapshot_id="",
                    universe_code=request.universe_code,
                    as_of_date=as_of,
                    message=f"无 {request.index_symbol} 成分（请先跑 core_ref index_member）",
                )

        shares = {}
        closes = {}
        if request.universe_code in ("TOP100", "SECTOR_LEADERS"):
            shares = self.repo.load_share_capital_map(as_of=as_of)
            closes = self.repo.load_latest_close_map(as_of=as_of)

        weight_map = {str(r["symbol"]): r.get("weight") for r in index_rows}
        members, rank_meta = self._assemble(
            listings=listings,
            industry=industry,
            st_map=st_map,
            universe_code=request.universe_code,
            index_set=index_set,
            weight_map=weight_map,
            shares=shares,
            closes=closes,
            top_n=request.top_n,
            sector_top_k=request.sector_top_k,
        )
        if request.universe_code != "ALL_LISTED" and not members:
            return UniverseBuildResult(
                status="failed",
                universe_snapshot_id="",
                universe_code=request.universe_code,
                as_of_date=as_of,
                message="Universe 成员为空（检查股本/行业/成分数据）",
            )

        snapshot_id = f"univ_{uuid.uuid4().hex}"
        meta = {
            "requested_as_of": request.as_of_date[:10],
            "as_of_adjusted": adjusted,
            "industry_standard": request.industry_standard,
            "index_symbol": request.index_symbol,
            "listing_count": len(listings),
            "st_active_count": len(st_map),
            "index_member_count": len(index_set),
            "share_capital_count": len(shares),
            "close_quote_count": len(closes),
            **rank_meta,
            "policy": "local_focus_leaders_ondemand_rest",
        }
        note = f"source={request.preferred_source}"
        if adjusted:
            note += f"; as_of adjusted from {request.as_of_date[:10]} to {as_of}"
        if request.universe_code in ("TOP100", "SECTOR_LEADERS"):
            note += f"; rank={rank_meta.get('rank_mode')}"

        self.repo.replace_snapshot(
            snapshot_id=snapshot_id,
            as_of_date=as_of,
            universe_code=request.universe_code,
            members=members,
            meta=meta,
            job_id=request.job_id,
            created_at=_utcnow(),
            source_note=note,
        )
        logger.info(
            "universe committed code=%s as_of=%s members=%s id=%s",
            request.universe_code,
            as_of,
            len(members),
            snapshot_id,
        )
        return UniverseBuildResult(
            status="committed",
            universe_snapshot_id=snapshot_id,
            universe_code=request.universe_code,
            as_of_date=as_of,
            member_count=len(members),
            message=note if adjusted or request.universe_code in (
                "TOP100",
                "SECTOR_LEADERS",
            ) else "",
        )

    def build_p0(self, request_base: UniverseBuildRequest) -> list[UniverseBuildResult]:
        out: list[UniverseBuildResult] = []
        for code in P0_UNIVERSES:
            req = UniverseBuildRequest(
                universe_code=code,
                as_of_date=request_base.as_of_date,
                industry_standard=request_base.industry_standard,
                preferred_source=request_base.preferred_source,
                index_symbol=request_base.index_symbol,
                job_id=request_base.job_id,
                allow_non_open_day=request_base.allow_non_open_day,
                top_n=request_base.top_n,
                sector_top_k=request_base.sector_top_k,
            )
            out.append(self.build(req))
        return out

    def _member_row(
        self,
        li: dict[str, Any],
        *,
        industry: dict[str, dict[str, Any]],
        st_map: dict[str, dict[str, Any]],
        weight_map: dict[str, Any],
        index_weight_override: float | None = None,
    ) -> dict[str, Any]:
        sym = str(li["symbol"])
        st = st_map.get(sym)
        ind = industry.get(sym) or {}
        return {
            "symbol": sym,
            "name": li.get("name"),
            "exchange": li.get("exchange"),
            "board": li.get("board"),
            "list_date": (li.get("list_date") or None),
            "delist_date": (li.get("delist_date") or None),
            "industry_code": ind.get("industry_code"),
            "industry_name": ind.get("industry_name"),
            "is_st": 1 if st else 0,
            "treat_type": st.get("treat_type") if st else None,
            "index_weight": (
                index_weight_override
                if index_weight_override is not None
                else weight_map.get(sym)
            ),
            "is_eligible": 1,
        }

    def _assemble(
        self,
        *,
        listings: list[dict[str, Any]],
        industry: dict[str, dict[str, Any]],
        st_map: dict[str, dict[str, Any]],
        universe_code: UniverseCode,
        index_set: set[str],
        weight_map: dict[str, Any],
        shares: dict[str, dict[str, Any]],
        closes: dict[str, float],
        top_n: int,
        sector_top_k: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if universe_code == "TOP100":
            return self._assemble_top_n(
                listings=listings,
                industry=industry,
                st_map=st_map,
                weight_map=weight_map,
                shares=shares,
                closes=closes,
                top_n=top_n,
                exclude_st=True,
            )
        if universe_code == "SECTOR_LEADERS":
            return self._assemble_sector_leaders(
                listings=listings,
                industry=industry,
                st_map=st_map,
                weight_map=weight_map,
                shares=shares,
                closes=closes,
                top_k=sector_top_k,
                exclude_st=True,
            )

        members: list[dict[str, Any]] = []
        for li in listings:
            sym = str(li["symbol"])
            if universe_code in ("HS300", "HS300_EX_ST") and sym not in index_set:
                continue
            if universe_code == "HS300_EX_ST" and sym in st_map:
                continue
            members.append(
                self._member_row(
                    li, industry=industry, st_map=st_map, weight_map=weight_map
                )
            )
        members.sort(key=lambda m: m["symbol"])
        return members, {"rank_mode": "filter_only"}

    def _assemble_top_n(
        self,
        *,
        listings: list[dict[str, Any]],
        industry: dict[str, dict[str, Any]],
        st_map: dict[str, dict[str, Any]],
        weight_map: dict[str, Any],
        shares: dict[str, dict[str, Any]],
        closes: dict[str, float],
        top_n: int,
        exclude_st: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        scored: list[tuple[float, str, dict[str, Any], str]] = []
        unscored: list[dict[str, Any]] = []
        for li in listings:
            sym = str(li["symbol"])
            if exclude_st and sym in st_map:
                continue
            score, metric = _score_symbol(sym, shares=shares, closes=closes)
            if score is None:
                unscored.append(li)
                continue
            scored.append((score, sym, li, metric))
        scored.sort(key=lambda x: (-x[0], x[1]))

        picked: list[dict[str, Any]] = []
        metrics: dict[str, int] = defaultdict(int)
        for score, sym, li, metric in scored[:top_n]:
            row = self._member_row(
                li,
                industry=industry,
                st_map=st_map,
                weight_map=weight_map,
                index_weight_override=float(score),
            )
            picked.append(row)
            metrics[metric] += 1

        # 股本稀疏时用上市名单补齐（按 list_date 升序优先老票）
        if len(picked) < top_n:
            pad = sorted(
                unscored,
                key=lambda r: (
                    str(r.get("list_date") or "9999"),
                    str(r["symbol"]),
                ),
            )
            have = {m["symbol"] for m in picked}
            for li in pad:
                if len(picked) >= top_n:
                    break
                sym = str(li["symbol"])
                if sym in have:
                    continue
                picked.append(
                    self._member_row(
                        li, industry=industry, st_map=st_map, weight_map=weight_map
                    )
                )
                metrics["listing_fallback"] += 1

        picked.sort(key=lambda m: m["symbol"])
        return picked, {
            "rank_mode": "top_n_by_size",
            "top_n": top_n,
            "scored_count": len(scored),
            "metric_counts": dict(metrics),
        }

    def _assemble_sector_leaders(
        self,
        *,
        listings: list[dict[str, Any]],
        industry: dict[str, dict[str, Any]],
        st_map: dict[str, dict[str, Any]],
        weight_map: dict[str, Any],
        shares: dict[str, dict[str, Any]],
        closes: dict[str, float],
        top_k: int,
        exclude_st: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        by_ind: dict[str, list[tuple[float, str, dict[str, Any]]]] = defaultdict(list)
        no_industry = 0
        for li in listings:
            sym = str(li["symbol"])
            if exclude_st and sym in st_map:
                continue
            ind = industry.get(sym) or {}
            code = str(ind.get("industry_code") or "").strip()
            if not code:
                no_industry += 1
                continue
            score, _metric = _score_symbol(sym, shares=shares, closes=closes)
            if score is None:
                # 无分也进组，用 0 垫底，保证每行业尽量有龙头
                score = 0.0
            by_ind[code].append((score, sym, li))

        picked: list[dict[str, Any]] = []
        for _code, rows in by_ind.items():
            rows.sort(key=lambda x: (-x[0], x[1]))
            for score, _sym, li in rows[: max(1, top_k)]:
                picked.append(
                    self._member_row(
                        li,
                        industry=industry,
                        st_map=st_map,
                        weight_map=weight_map,
                        index_weight_override=float(score) if score else None,
                    )
                )

        # 去重（极端情况同一票多行业映射）
        uniq: dict[str, dict[str, Any]] = {}
        for m in picked:
            uniq[m["symbol"]] = m
        members = sorted(uniq.values(), key=lambda m: m["symbol"])
        return members, {
            "rank_mode": "sector_leaders",
            "sector_top_k": top_k,
            "industry_bucket_count": len(by_ind),
            "no_industry_skipped": no_industry,
        }
