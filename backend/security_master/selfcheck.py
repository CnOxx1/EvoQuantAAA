from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from security_master.models import UniverseBuildRequest
from security_master.service import SecurityMasterService
from shared.db import get_conn


def main() -> int:
    with get_conn() as conn:
        listing_n = int(
            conn.execute("SELECT COUNT(*) AS n FROM raw_security_listing").fetchone()[
                "n"
            ]
        )
        member_n = int(
            conn.execute("SELECT COUNT(*) AS n FROM raw_index_member").fetchone()["n"]
        )
    if listing_n < 100:
        print("status=skip message=需要先有 raw_security_listing")
        return 0
    if member_n < 10:
        print("status=skip message=需要先有 raw_index_member")
        return 0

    results = SecurityMasterService().build_p0(
        UniverseBuildRequest(universe_code="ALL_LISTED", as_of_date="2026-07-23")
    )
    ok = True
    for r in results:
        print(
            f"code={r.universe_code} status={r.status} "
            f"snapshot={r.universe_snapshot_id} as_of={r.as_of_date} "
            f"members={r.member_count}"
        )
        if r.message:
            print(f"message={r.message}")
        ok = ok and r.status == "committed"

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT universe_code, member_count FROM universe_snapshot
            WHERE as_of_date='2026-07-23'
            ORDER BY universe_code
            """
        ).fetchall()
        for r in rows:
            print(f"gate {r['universe_code']}={r['member_count']}")
        hs = conn.execute(
            """
            SELECT COUNT(*) AS n FROM universe_snapshot_member m
            JOIN universe_snapshot s ON s.universe_snapshot_id=m.universe_snapshot_id
            WHERE s.universe_code='HS300' AND s.as_of_date='2026-07-23'
            """
        ).fetchone()["n"]
        st_in_hs = conn.execute(
            """
            SELECT COUNT(*) AS n FROM universe_snapshot_member m
            JOIN universe_snapshot s ON s.universe_snapshot_id=m.universe_snapshot_id
            WHERE s.universe_code='HS300' AND s.as_of_date='2026-07-23' AND m.is_st=1
            """
        ).fetchone()["n"]
        ex = conn.execute(
            """
            SELECT COUNT(*) AS n FROM universe_snapshot_member m
            JOIN universe_snapshot s ON s.universe_snapshot_id=m.universe_snapshot_id
            WHERE s.universe_code='HS300_EX_ST' AND s.as_of_date='2026-07-23'
            """
        ).fetchone()["n"]
    assert int(hs) >= 250, f"HS300 成分过少: {hs}"
    assert int(ex) == int(hs) - int(st_in_hs), "EX_ST 数量应=HS300-ST"
    print("status=ok" if ok else "status=failed")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
