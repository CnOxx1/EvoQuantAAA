from __future__ import annotations

"""兼容转发：实现已迁至 data_ingest.ingest_common.parse。"""

from data_ingest.ingest_common.parse import (
    as_float,
    as_str,
    board_from_code,
    col_by_keywords,
    infer_st_type,
)

__all__ = [
    "as_str",
    "as_float",
    "col_by_keywords",
    "board_from_code",
    "infer_st_type",
]
