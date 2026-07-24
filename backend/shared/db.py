from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result, Row

from shared.config import settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None

# 避免把 SQL 字符串字面量里的 ? 误替换（本项目 SQL 无此情形；保守处理注释外 ?）
_QMARK_RE = re.compile(r"\?")


class RowMap(Mapping[str, Any]):
    """兼容 sqlite3.Row 的下标访问：row['col']。"""

    def __init__(self, row: Row[Any]) -> None:
        self._data = dict(row._mapping)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self):
        return self._data.keys()


class ResultProxy:
    def __init__(self, result: Result[Any]) -> None:
        self._result = result

    def fetchone(self) -> RowMap | None:
        row = self._result.fetchone()
        return None if row is None else RowMap(row)

    def fetchall(self) -> list[RowMap]:
        return [RowMap(r) for r in self._result.fetchall()]


class ConnectionProxy:
    """对外保持 conn.execute(sql, params).fetchone() 形态，内部走 SQLAlchemy。"""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> ResultProxy:
        converted, binds = _qmark_to_binds(sql, tuple(params))
        result = self._conn.execute(text(converted), binds)
        return ResultProxy(result)


def _qmark_to_binds(sql: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
    binds: dict[str, Any] = {}
    idx = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal idx
        if idx >= len(params):
            raise ValueError(f"SQL 占位符多于参数: sql={sql!r} params={params!r}")
        key = f"p{idx}"
        binds[key] = params[idx]
        idx += 1
        return f":{key}"

    converted = _QMARK_RE.sub(repl, sql)
    if idx != len(params):
        raise ValueError(f"SQL 参数多于占位符: sql={sql!r} params={params!r}")
    return converted, binds


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
        )
        logger.info("database engine ready url=%s", _safe_url(settings.database_url))
    return _engine


def _safe_url(url: str) -> str:
    # 隐藏密码
    if "@" in url and "://" in url:
        head, tail = url.split("://", 1)
        if "@" in tail and ":" in tail.split("@", 1)[0]:
            cred, rest = tail.split("@", 1)
            user = cred.split(":", 1)[0]
            return f"{head}://{user}:***@{rest}"
    return url


@contextmanager
def get_conn() -> Iterator[ConnectionProxy]:
    eng = get_engine()
    with eng.begin() as conn:
        yield ConnectionProxy(conn)


def execute_script(sql: str) -> None:
    """执行整份迁移脚本（按分号拆分；跳过空段与纯注释段）。"""
    statements = _split_sql(sql)
    eng = get_engine()
    with eng.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def _split_sql(sql: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            chunk = "\n".join(buf).strip().rstrip(";").strip()
            buf = []
            if chunk:
                parts.append(chunk)
    tail = "\n".join(buf).strip().rstrip(";").strip()
    if tail:
        parts.append(tail)
    return parts


def fetchall(sql: str, params: tuple[Any, ...] = ()) -> list[RowMap]:
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def apply_migration_file(path: Path) -> None:
    """幂等应用单个迁移文件（记录 schema_migrations）。"""
    _ensure_migrations_table()
    name = path.name
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE filename = ?", (name,)
        ).fetchone()
        if exists:
            logger.info("skip migration (already applied): %s", name)
            return
    execute_script(path.read_text(encoding="utf-8"))
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)",
            (name,),
        )
    logger.info("applied migration: %s", name)


def _ensure_migrations_table() -> None:
    execute_script(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename    TEXT PRIMARY KEY,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
