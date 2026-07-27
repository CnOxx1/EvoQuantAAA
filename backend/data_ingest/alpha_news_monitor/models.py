from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

IngestKind = Literal[
    "news_incremental",
    "news_watchlist",
    "news_backfill",
    "news_official",
    "news_forum",
    "news_policy",
]

VALID_KINDS: tuple[str, ...] = (
    "news_incremental",
    "news_watchlist",
    "news_backfill",
    "news_official",
    "news_forum",
    "news_policy",
)

# 官方/通讯社快讯（空 --media 时默认全拉；cjzc/caixin 偏政策摘要也可走 official）
OFFICIAL_MEDIA: tuple[str, ...] = (
    "cls",
    "sina",
    "futu",
    "ths",
    "cctv",
    "cjzc",
    "caixin",
)

# 论坛默认子源（轻量，适合开发机）
FORUM_MEDIA_DEFAULT: tuple[str, ...] = ("em_comment", "xueqiu", "weibo")
# 论坛全部子源（需 --media 显式点名才会拉扩展源）
FORUM_MEDIA: tuple[str, ...] = (
    "em_comment",
    "em_detail",
    "xueqiu",
    "xueqiu_follow",
    "xueqiu_deal",
    "weibo",
    "baidu_hot",
    "baidu_vote",
)

# 政策/监管语境（利好利空分析原料）
POLICY_MEDIA_DEFAULT: tuple[str, ...] = ("cjzc", "caixin", "epu")
POLICY_MEDIA: tuple[str, ...] = (
    "cjzc",
    "caixin",
    "cctv",
    "econ",
    "epu",
    "cls_policy",
)


@dataclass(frozen=True)
class NewsRecord:
    source_news_id: str
    title: str
    publish_time: str
    channel: str
    source: str
    symbol: str | None = None
    summary: str | None = None
    url: str | None = None
    media_source: str | None = None
    content_type: str | None = None  # news|wire|forum_heat|forum_score|policy|policy_index
    extra_json: str | None = None


@dataclass
class FetchRequest:
    kind: IngestKind
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    job_id: str | None = None
    # 子源过滤；空=该 kind 的默认集合
    media_filters: list[str] = field(default_factory=list)
    forum_top_n: int = 200
    # 标题命中简称时回填 symbol（读 raw_security_listing）
    symbol_map: bool = False


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
