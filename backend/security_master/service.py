from __future__ import annotations

import logging
import uuid
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

        weight_map = {
            str(r["symbol"]): r.get("weight") for r in index_rows
        }
        members = self._assemble(
            listings=listings,
            industry=industry,
            st_map=st_map,
            universe_code=request.universe_code,
            index_set=index_set,
            weight_map=weight_map,
        )
        if request.universe_code != "ALL_LISTED" and not members:
            return UniverseBuildResult(
                status="failed",
                universe_snapshot_id="",
                universe_code=request.universe_code,
                as_of_date=as_of,
                message="成分与上市名单交集为空（检查 index_member 代码解析）",
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
        }
        note = f"source={request.preferred_source}"
        if adjusted:
            note += f"; as_of adjusted from {request.as_of_date[:10]} to {as_of}"

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
            message=note if adjusted else "",
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
            )
            out.append(self.build(req))
        return out

    def _assemble(
        self,
        *,
        listings: list[dict[str, Any]],
        industry: dict[str, dict[str, Any]],
        st_map: dict[str, dict[str, Any]],
        universe_code: UniverseCode,
        index_set: set[str],
        weight_map: dict[str, Any],
    ) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        for li in listings:
            sym = str(li["symbol"])
            if universe_code in ("HS300", "HS300_EX_ST") and sym not in index_set:
                continue
            st = st_map.get(sym)
            is_st = 1 if st else 0
            if universe_code == "HS300_EX_ST" and is_st:
                continue
            ind = industry.get(sym) or {}
            members.append(
                {
                    "symbol": sym,
                    "name": li.get("name"),
                    "exchange": li.get("exchange"),
                    "board": li.get("board"),
                    "list_date": (li.get("list_date") or None),
                    "delist_date": (li.get("delist_date") or None),
                    "industry_code": ind.get("industry_code"),
                    "industry_name": ind.get("industry_name"),
                    "is_st": is_st,
                    "treat_type": st.get("treat_type") if st else None,
                    "index_weight": weight_map.get(sym),
                    "is_eligible": 1,
                }
            )
        members.sort(key=lambda m: m["symbol"])
        return members
