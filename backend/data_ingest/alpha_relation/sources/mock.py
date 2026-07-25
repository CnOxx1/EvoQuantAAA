from __future__ import annotations

import json

from data_ingest.alpha_relation.models import FetchBundle, FetchRequest
from data_ingest.alpha_relation.sources.base import RelationSource


class MockRelationSource(RelationSource):
    source = "mock"

    def fetch(self, request: FetchRequest) -> FetchBundle:
        asof = (request.end or "2026-07-25")[:10]
        want = {s.strip() for s in (request.symbols or []) if s.strip()}
        rows: list[dict] = []

        if request.kind == "hot_relate":
            samples = [
                ("600519", "000858", 1.2),
                ("600519", "000568", 0.8),
                ("000001", "600000", 0.5),
            ]
            for a, b, w in samples:
                if want and (a not in want and b not in want):
                    continue
                if want and not (a in want and b in want) and not (
                    a in want or b in want
                ):
                    pass
                src, dst = (a, b) if a < b else (b, a)
                if want and src not in want and dst not in want:
                    continue
                rows.append(
                    {
                        "src_symbol": src,
                        "dst_symbol": dst,
                        "relation_type": "HOT_RELATE",
                        "as_of_date": asof,
                        "weight": w,
                        "board_name": None,
                        "holder_name": None,
                        "holder_type": None,
                        "coop_holder_name": None,
                        "extra_json": json.dumps({"mock": True}, ensure_ascii=False),
                        "source_event_id": f"mock-hot-{src}-{dst}-{asof}",
                        "source": self.source,
                    }
                )
        elif request.kind == "holder_team":
            a, b = "601668", "002271"
            if not want or (a in want and b in want) or (a in want or b in want):
                src, dst = (a, b) if a < b else (b, a)
                rows.append(
                    {
                        "src_symbol": src,
                        "dst_symbol": dst,
                        "relation_type": "HOLDER_TEAM",
                        "as_of_date": asof,
                        "weight": 93.0,
                        "board_name": None,
                        "holder_name": "全国社保基金一一零组合",
                        "holder_type": request.holder_type or "社保",
                        "coop_holder_name": "香港中央结算有限公司",
                        "extra_json": json.dumps({"mock": True}, ensure_ascii=False),
                        "source_event_id": f"mock-team-{src}-{dst}-{asof}",
                        "source": self.source,
                    }
                )
        elif request.kind == "board_co":
            board = (request.board_names or ["人工智能"])[0]
            members = ["300308", "000977", "002230"]
            if want:
                members = [m for m in members if m in want] or members
            members = sorted(set(members))
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    rows.append(
                        {
                            "src_symbol": a,
                            "dst_symbol": b,
                            "relation_type": "CONCEPT_CO"
                            if request.board_type != "INDUSTRY"
                            else "INDUSTRY_CO",
                            "as_of_date": asof,
                            "weight": 1.0,
                            "board_name": board,
                            "holder_name": None,
                            "holder_type": None,
                            "coop_holder_name": None,
                            "extra_json": json.dumps(
                                {"board_type": request.board_type}, ensure_ascii=False
                            ),
                            "source_event_id": f"mock-board-{a}-{b}-{board}-{asof}",
                            "source": self.source,
                        }
                    )
        else:
            raise ValueError(request.kind)

        return FetchBundle(kind=request.kind, rows=rows, source=self.source)
