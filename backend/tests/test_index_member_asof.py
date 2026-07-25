from __future__ import annotations

from security_master.repository import SecurityMasterRepository


class _FakeConn:
    def __init__(self, rows_by_sql_key: dict):
        self._rows = rows_by_sql_key
        self._last = None

    def execute(self, sql, params=()):
        self._last = (sql, params)
        key = "max_le" if "trade_date<=?" in sql and "MAX" in sql else None
        if key is None and "MAX(trade_date)" in sql and "trade_date<=?" not in sql:
            key = "max_any"
        if key is None and "FROM raw_index_member" in sql and "trade_date=?" in sql:
            key = "members"
        rows = self._rows.get(key, [])
        return _Result(rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


def test_asof_between_two_periods(monkeypatch):
    """as_of 落在两期之间应取旧一期。"""
    repo = SecurityMasterRepository()

    def fake_get_conn():
        class CM:
            def __enter__(self):
                return _FakeConn(
                    {
                        "max_le": [{"d": "2024-06-01"}],
                        "members": [
                            {
                                "index_symbol": "000300",
                                "symbol": "600000",
                                "trade_date": "2024-06-01",
                                "weight": 1.0,
                                "source": "akshare",
                            }
                        ],
                    }
                )

            def __exit__(self, *a):
                return False

        return CM()

    monkeypatch.setattr("security_master.repository.get_conn", fake_get_conn)
    members, eff, fallback = repo.load_index_members(
        index_symbol="000300", as_of="2024-12-01", preferred_source="akshare"
    )
    assert eff == "2024-06-01"
    assert fallback is False
    assert [m["symbol"] for m in members] == ["600000"]
