from __future__ import annotations

# 源分类关键词 -> category_norm（可映射则写；否则留给 data_process）
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("earnings_preview", ("业绩预告", "预告")),
    ("earnings_flash", ("业绩快报", "快报")),
    ("earnings_revision", ("业绩修正", "修正公告")),
    ("share_decrease", ("减持",)),
    ("share_increase", ("增持",)),
    ("buyback", ("回购",)),
    ("equity_incentive", ("股权激励", "激励计划")),
    ("investigation", ("立案调查", "立案告知")),
    ("penalty", ("处罚", "处分")),
    ("inquiry", ("问询函", "关注函", "监管函")),
    ("restructure", ("重组", "重大资产")),
    ("halt_related", ("停牌", "复牌")),
    ("dividend_plan", ("利润分配", "分红", "送转")),
]


def normalize_category(category_raw: str, title: str = "") -> str | None:
    text = f"{category_raw} {title}"
    for norm, keywords in _RULES:
        if any(k in text for k in keywords):
            return norm
    return None
