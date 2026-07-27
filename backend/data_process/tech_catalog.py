from __future__ import annotations

"""技术指标分类目录（基于 pandas-ta Category）。

公开实现可复现规模：pandas-ta ~150 个函数 → 默认参数下约 250+ 输出序列
（接近常说的「两三百个指标」；不含需专有数据的券商私有指标）。
"""

from dataclasses import dataclass
from typing import Any

# 日更默认：手写核心子集（与历史 MA_*/MACD_* 码兼容）
SUITE_CORE = "core"
SUITE_FULL = "full"

CATEGORIES: tuple[str, ...] = (
    "candle",
    "cycle",
    "momentum",
    "overlap",
    "performance",
    "statistics",
    "trend",
    "volatility",
    "volume",
)

# 全量计算时跳过：强依赖 TA-Lib 或易失败的项
SKIP_KINDS: frozenset[str] = frozenset(
    {
        "cdl_pattern",  # 需 TA-Lib 完整形态库
    }
)

# 全量预热（日历日）
FULL_LOOKBACK_CALENDAR_DAYS = 260
CORE_LOOKBACK_CALENDAR_DAYS = 120


@dataclass(frozen=True)
class IndicatorKind:
    kind: str
    category: str


def load_pandas_ta_kinds(
    *,
    categories: list[str] | None = None,
) -> list[IndicatorKind]:
    """从 pandas-ta.Category 加载 kind 列表。"""
    import pandas_ta as ta

    allow = set(categories) if categories else set(CATEGORIES)
    out: list[IndicatorKind] = []
    for cat, kinds in ta.Category.items():
        if cat not in allow:
            continue
        for k in kinds:
            if k in SKIP_KINDS:
                continue
            out.append(IndicatorKind(kind=str(k), category=str(cat)))
    return out


def kind_to_category_map(
    kinds: list[IndicatorKind] | None = None,
) -> dict[str, str]:
    items = kinds or load_pandas_ta_kinds()
    return {i.kind: i.category for i in items}


def categorize_column(col: str, kind_map: dict[str, str]) -> str:
    """把 pandas-ta 输出列名映射到 category。"""
    cl = col.strip()
    cu = cl.upper()
    # 长 kind 优先，避免 ama 误匹配
    for kind in sorted(kind_map.keys(), key=len, reverse=True):
        ku = kind.upper()
        if cu == ku or cu.startswith(ku + "_") or cu.startswith(ku):
            return kind_map[kind]
    # Heikin-Ashi
    if cu.startswith("HA_"):
        return "candle"
    return "unknown"


def build_study(kinds: list[IndicatorKind]) -> Any:
    import pandas_ta as ta

    return ta.Study(
        name="evo_full",
        ta=[{"kind": k.kind} for k in kinds],
        cores=0,  # 单进程更稳（Windows / 嵌入式 PG 任务）
    )


def catalog_summary() -> dict[str, Any]:
    kinds = load_pandas_ta_kinds()
    by: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for k in kinds:
        by.setdefault(k.category, []).append(k.kind)
    return {
        "suite_full_functions": len(kinds),
        "categories": {c: len(by.get(c, [])) for c in CATEGORIES},
        "skip_kinds": sorted(SKIP_KINDS),
        "note": "函数数≈150；多输出列合计约 250+ 序列",
    }
