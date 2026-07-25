from __future__ import annotations

# 源分类关键词 / 标题关键词 -> category_norm（按序匹配，先命中先生效）
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
    # 中标优先于笼统「重大合同」
    ("win_bid", ("中标", "中选", "中标通知", "中标结果", "中标候选人")),
    ("major_contract", ("重大合同", "日常经营重大合同")),
]

# CLI / 文档用：已知规范化类别
KNOWN_CATEGORY_NORMS: tuple[str, ...] = tuple(code for code, _ in _RULES)

# 巨潮 searchkey 提示（服务端预过滤，仍以本地 category_norm 为准）
_CNINFO_SEARCHKEY: dict[str, str] = {
    "win_bid": "中标",
    "major_contract": "重大合同",
}


def normalize_category(category_raw: str, title: str = "") -> str | None:
    text = f"{category_raw} {title}"
    for norm, keywords in _RULES:
        if any(k in text for k in keywords):
            return norm
    return None


def matches_requested_categories(
    *,
    category_norm: str | None,
    category_raw: str,
    requested: list[str] | None,
) -> bool:
    """是否命中请求的 --category；major_contract 桶包含 win_bid。"""
    if not requested:
        return True
    want = {c.strip() for c in requested if c and c.strip()}
    if not want:
        return True
    if category_norm and category_norm in want:
        return True
    if category_raw in want:
        return True
    # 拉「重大合同」时一并保留中标类披露
    if "major_contract" in want and category_norm == "win_bid":
        return True
    return False


def cninfo_searchkey(categories: list[str] | None) -> str:
    """为巨潮构造 searchkey；多类时取第一个可映射的关键词。"""
    if not categories:
        return ""
    for c in categories:
        key = _CNINFO_SEARCHKEY.get(c.strip())
        if key:
            return key
    return ""
