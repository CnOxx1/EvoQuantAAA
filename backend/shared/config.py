from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    # backend/shared/config.py -> repo root
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    default_source: str = "cninfo"
    default_channel: str = "cninfo"

    @classmethod
    def load(cls) -> "Settings":
        root = _repo_root()
        data_dir = Path(os.getenv("ASHARE_DATA_DIR", root / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)

        raw = os.getenv("ASHARE_DATABASE_URL", "").strip()
        if raw:
            database_url = raw
            if database_url.startswith("postgresql://"):
                database_url = (
                    "postgresql+psycopg://" + database_url[len("postgresql://") :]
                )
            elif database_url.startswith("postgres://"):
                database_url = (
                    "postgresql+psycopg://" + database_url[len("postgres://") :]
                )
        else:
            # 默认：嵌入式 PostgreSQL（专业库，数据落在 data/pgdata）
            from shared.pg_local import ensure_local_postgres

            database_url = ensure_local_postgres(data_dir)

        if database_url.startswith("sqlite:"):
            raise RuntimeError(
                "已弃用 SQLite 文件库。请使用 PostgreSQL，例如：\n"
                "  ASHARE_DATABASE_URL=postgresql+psycopg://ashare:ashare@localhost:5432/ashare\n"
                "或不设该变量，使用内置嵌入式 PostgreSQL（需 pip install pgembed）。"
            )

        return cls(database_url=database_url, data_dir=data_dir)


settings = Settings.load()
