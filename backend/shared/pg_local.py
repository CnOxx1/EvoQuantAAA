"""本地嵌入式 PostgreSQL（pgembed），无需 Docker / 系统安装。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_NAME = "ashare"
_server = None


def ensure_local_postgres(data_dir: Path) -> str:
    """
    启动/复用 data_dir/pgdata 中的嵌入式 PG，确保存在库 ashare。
    返回 SQLAlchemy/psycopg URL：postgresql+psycopg://...
    """
    global _server
    try:
        import pgembed
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "未设置 ASHARE_DATABASE_URL 且未安装 pgembed。"
            "请 pip install pgembed，或配置外部 PostgreSQL："
            "ASHARE_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/ashare"
        ) from exc

    pgdata = data_dir / "pgdata"
    pgdata.mkdir(parents=True, exist_ok=True)
    if _server is None:
        _server = pgembed.get_server(str(pgdata))
    _server.ensure_postgres_running()
    uri = _server.get_uri()  # postgresql://postgres:@127.0.0.1:PORT/postgres
    logger.info("local postgres up uri_base=%s", uri.rsplit("/", 1)[0] + "/")

    # 创建业务库
    admin_url = _to_psycopg_url(uri)
    _ensure_database(admin_url, _DB_NAME)
    host_part = uri.rsplit("/", 1)[0]
    return _to_psycopg_url(f"{host_part}/{_DB_NAME}")


def _to_psycopg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def _ensure_database(admin_url: str, db_name: str) -> None:
    from sqlalchemy import create_engine, text

    # CONNECT 到默认 postgres 库
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": db_name}
        ).fetchone()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            logger.info("created database %s", db_name)
    engine.dispose()
