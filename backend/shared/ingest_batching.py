from __future__ import annotations

"""Ingest 批量辅助：Universe 解析 + 分块（无业务编排语义）。"""

from shared.universe_resolve import resolve_universe_symbols


def chunk_symbols(symbols: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size < 1:
        raise ValueError("chunk_size 必须 >= 1")
    if not symbols:
        return []
    return [symbols[i : i + chunk_size] for i in range(0, len(symbols), chunk_size)]


def should_chunk(
    symbols: list[str],
    *,
    chunked: bool = False,
    universe: str | None = None,
    chunk_size: int = 15,
    auto_threshold: int = 30,
) -> bool:
    """universe / 显式 --chunked / 标的数超阈值时启用分块。"""
    if not symbols:
        return False
    if chunked or universe:
        return True
    return len(symbols) > auto_threshold


def resolve_symbols_from_args(
    *,
    universe: str | None,
    symbols: list[str],
    as_of: str | None,
    as_of_end: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    解析最终标的列表。
    - 无 universe：返回清洗后的显式 symbols
    - 有 universe：需要 as_of；可与显式 symbols 求交
    """
    cleaned = [s.strip() for s in symbols if s and s.strip()]
    if not universe:
        return None, cleaned
    if not as_of:
        raise ValueError("--universe 需要 --start 或 --universe-as-of 作为点时")
    sid, uni_symbols = resolve_universe_symbols(
        universe_code=universe,
        as_of=as_of,
        as_of_end=as_of_end,
    )
    if not uni_symbols:
        raise ValueError(f"Universe {universe} 无成员快照")
    if cleaned:
        want = set(cleaned)
        uni_symbols = [s for s in uni_symbols if s in want]
    return sid, uni_symbols
