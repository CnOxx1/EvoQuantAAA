from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from data_ingest.alpha_announcement.timeutil import normalize_publish_time
from data_ingest.alpha_news_monitor.models import (
    FORUM_MEDIA,
    FORUM_MEDIA_DEFAULT,
    OFFICIAL_MEDIA,
    POLICY_MEDIA,
    POLICY_MEDIA_DEFAULT,
    FetchRequest,
    NewsRecord,
)
from data_ingest.alpha_news_monitor.sources.base import FetchResult, NewsSource
from data_ingest.core_ref.sources._parse import as_float, as_str, col_by_keywords
from shared.akshare_call import call_with_retry

logger = logging.getLogger(__name__)


def _require_akshare():
    try:
        import akshare as ak  # noqa: WPS433
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("未安装 akshare") from exc
    return ak


def _plain(symbol: str) -> str:
    s = symbol.split(".")[0].strip().upper()
    for p in ("SH", "SZ", "BJ"):
        if s.startswith(p) and len(s) > len(p):
            s = s[len(p) :]
    return s


def _news_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:32]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 政策语境关键词（启发式，供后续利好利空标注；非模型结论）
_POLICY_KW = (
    "证监会",
    "国务院",
    "央行",
    "人民银行",
    "发改委",
    "财政部",
    "工信部",
    "银保监",
    "金融监管",
    "政策",
    "监管",
    "降准",
    "降息",
    "注册制",
    "印花税",
    "国常会",
    "中央经济",
    "货币政策",
    "财政政策",
)
_BULLISH_HINT = ("降准", "降息", "利好", "支持", "扩大", "减税", "减费", "宽松", "提振", "稳增长")
_BEARISH_HINT = ("查处", "处罚", "收紧", "限制", "禁令", "立案", "严打", "问询", "风险警示", "退市")


def _tone_hint(text: str) -> str | None:
    t = text or ""
    bull = sum(1 for k in _BULLISH_HINT if k in t)
    bear = sum(1 for k in _BEARISH_HINT if k in t)
    if bull == 0 and bear == 0:
        return None
    if bull > bear:
        return "bullish_hint"
    if bear > bull:
        return "bearish_hint"
    return "mixed_hint"


def _policy_tags(text: str) -> list[str]:
    t = text or ""
    return [k for k in _POLICY_KW if k in t]


class AkshareNewsSource(NewsSource):
    """
    - news_incremental / backfill：东财全球快讯（+ backfill 时 CCTV）
    - news_watchlist：东财个股资讯
    - news_official：通讯社快讯 + 财经早餐/财新
    - news_forum：千股千评/雪球/微博 + 可选百度热搜与明细
    - news_policy：政策语境原料（早餐/财新/CCTV/经济日历/EPU/财联社政策过滤）
    """

    source = "akshare"
    channel = "eastmoney"

    def fetch(self, request: FetchRequest, *, since: str | None = None) -> FetchResult:
        ak = _require_akshare()
        if request.kind == "news_official":
            self.channel = "official"
            records = self._official(ak, request)
        elif request.kind == "news_forum":
            self.channel = "forum"
            records = self._forum(ak, request)
        elif request.kind == "news_policy":
            self.channel = "policy"
            records = self._policy(ak, request)
        elif request.kind == "news_watchlist" or (
            request.kind != "news_backfill" and request.symbols
        ):
            self.channel = "eastmoney"
            records = self._by_symbols(ak, request)
        else:
            self.channel = "eastmoney"
            records = self._global_em(ak, request)
            if request.kind == "news_backfill" and request.start and request.end:
                records.extend(self._cctv_backfill(ak, request))

        since_n = normalize_publish_time(since) if since else None
        if since_n:
            records = [r for r in records if r.publish_time > since_n]
        max_pt = max((r.publish_time for r in records), default=None)
        return FetchResult(records=records, max_publish_time=max_pt)

    def _want(
        self,
        request: FetchRequest,
        name: str,
        *,
        group: tuple[str, ...],
        default_group: tuple[str, ...] | None = None,
    ) -> bool:
        filters = [m.strip().lower() for m in (request.media_filters or []) if m.strip()]
        if not filters:
            return name in (default_group if default_group is not None else group)
        return name in filters

    def _call(self, fn: Any, *, label: str) -> Any:
        return call_with_retry(fn, label=label, attempts=3, pause=0.15, backoff=0.6)

    # ---- 既有：东财快讯 / 个股 / CCTV ----

    def _global_em(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        try:
            df = self._call(lambda: ak.stock_info_global_em(), label="stock_info_global_em")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_em 失败: %s", exc)
            return []
        return self._rows_from_title_frame(
            df,
            request,
            id_prefix="em_global",
            channel="eastmoney",
            media_source="eastmoney_global",
            content_type="wire",
        )

    def _by_symbols(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        symbols = [_plain(s) for s in request.symbols if s.strip()]
        if not symbols:
            raise ValueError("news_watchlist 必须提供 --symbol")
        out: list[NewsRecord] = []
        for symbol in symbols:
            try:
                df = self._call(
                    lambda s=symbol: ak.stock_news_em(symbol=s),
                    label=f"stock_news_em:{symbol}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("stock_news_em %s 失败: %s", symbol, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            c_title = col_by_keywords(df.columns, ("新闻标题", "标题"))
            c_sum = col_by_keywords(df.columns, ("新闻内容", "内容", "摘要"))
            c_time = col_by_keywords(df.columns, ("发布时间", "时间"))
            c_media = col_by_keywords(df.columns, ("文章来源", "来源"))
            c_url = col_by_keywords(df.columns, ("新闻链接", "链接", "地址"))
            for _, r in df.iterrows():
                title = as_str(r[c_title]) if c_title is not None else ""
                if not title:
                    continue
                try:
                    pt = normalize_publish_time(r[c_time] if c_time is not None else None)
                except Exception:
                    continue
                if not self._in_date_range(pt, request):
                    continue
                url = as_str(r[c_url]) if c_url is not None else ""
                nid = _news_id("em_stock", symbol, title, pt, url)
                out.append(
                    NewsRecord(
                        source_news_id=nid,
                        symbol=symbol,
                        title=title,
                        summary=as_str(r[c_sum]) if c_sum is not None else None,
                        publish_time=pt,
                        url=url or None,
                        media_source=as_str(r[c_media]) if c_media is not None else None,
                        channel="eastmoney",
                        source=self.source,
                        content_type="news",
                    )
                )
        return out

    def _cctv_backfill(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        if not (request.start and request.end):
            return []
        start = date.fromisoformat(request.start[:10])
        end = date.fromisoformat(request.end[:10])
        out: list[NewsRecord] = []
        d = start
        while d <= end:
            ymd = d.strftime("%Y%m%d")
            try:
                df = self._call(
                    lambda y=ymd: ak.news_cctv(date=y), label=f"news_cctv:{ymd}"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("news_cctv %s 失败: %s", ymd, exc)
                d += timedelta(days=1)
                continue
            if df is not None and not getattr(df, "empty", True):
                c_title = col_by_keywords(df.columns, ("title", "标题")) or df.columns[1]
                c_content = col_by_keywords(df.columns, ("content", "内容"))
                for _, r in df.iterrows():
                    title = as_str(r[c_title])
                    if not title:
                        continue
                    pt = normalize_publish_time(f"{d.isoformat()} 19:00:00")
                    nid = _news_id("cctv", ymd, title)
                    out.append(
                        NewsRecord(
                            source_news_id=nid,
                            symbol=None,
                            title=title,
                            summary=as_str(r[c_content])[:500] if c_content else None,
                            publish_time=pt,
                            url=None,
                            media_source="cctv",
                            channel="cctv",
                            source=self.source,
                            content_type="wire",
                        )
                    )
            d += timedelta(days=1)
        return out

    # ---- 官方通讯社 ----

    def _official(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        out: list[NewsRecord] = []
        if self._want(request, "cls", group=OFFICIAL_MEDIA):
            out.extend(self._cls(ak, request))
        if self._want(request, "sina", group=OFFICIAL_MEDIA):
            out.extend(self._sina(ak, request))
        if self._want(request, "futu", group=OFFICIAL_MEDIA):
            out.extend(self._futu(ak, request))
        if self._want(request, "ths", group=OFFICIAL_MEDIA):
            out.extend(self._ths(ak, request))
        if self._want(request, "cjzc", group=OFFICIAL_MEDIA):
            out.extend(self._cjzc(ak, request, channel="official", content_type="wire"))
        if self._want(request, "caixin", group=OFFICIAL_MEDIA):
            out.extend(self._caixin(ak, request, channel="official", content_type="wire"))
        if self._want(request, "cctv", group=OFFICIAL_MEDIA) and request.start and request.end:
            out.extend(self._cctv_backfill(ak, request))
        return out

    def _cls(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        try:
            df = self._call(
                lambda: ak.stock_info_global_cls(symbol="全部"),
                label="stock_info_global_cls",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_cls 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_title = col_by_keywords(df.columns, ("标题",)) or df.columns[0]
        c_sum = col_by_keywords(df.columns, ("内容",))
        c_date = col_by_keywords(df.columns, ("发布日期", "日期"))
        c_time = col_by_keywords(df.columns, ("发布时间", "时间"))
        out: list[NewsRecord] = []
        for _, r in df.iterrows():
            title = as_str(r[c_title]) or (as_str(r[c_sum])[:80] if c_sum else "")
            if not title:
                continue
            day = as_str(r[c_date])[:10] if c_date is not None else ""
            tm = as_str(r[c_time]) if c_time is not None else "00:00:00"
            raw_pt = f"{day} {tm}".strip() if day else tm
            try:
                pt = normalize_publish_time(raw_pt)
            except Exception:
                continue
            if not self._in_date_range(pt, request):
                continue
            summary = as_str(r[c_sum])[:800] if c_sum is not None else None
            nid = _news_id("cls", title, pt)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=title[:300],
                    summary=summary,
                    publish_time=pt,
                    media_source="cls",
                    channel="official",
                    source=self.source,
                    content_type="wire",
                    url="https://www.cls.cn/telegraph",
                )
            )
        return out

    def _sina(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        try:
            df = self._call(lambda: ak.stock_info_global_sina(), label="stock_info_global_sina")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_sina 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_time = col_by_keywords(df.columns, ("时间",)) or df.columns[0]
        c_content = col_by_keywords(df.columns, ("内容",)) or df.columns[-1]
        out: list[NewsRecord] = []
        for _, r in df.iterrows():
            content = as_str(r[c_content])
            if not content:
                continue
            try:
                pt = normalize_publish_time(r[c_time])
            except Exception:
                continue
            if not self._in_date_range(pt, request):
                continue
            title = content[:80]
            nid = _news_id("sina", title, pt)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=title,
                    summary=content[:800],
                    publish_time=pt,
                    media_source="sina",
                    channel="official",
                    source=self.source,
                    content_type="wire",
                )
            )
        return out

    def _futu(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        try:
            df = self._call(lambda: ak.stock_info_global_futu(), label="stock_info_global_futu")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_futu 失败: %s", exc)
            return []
        return self._rows_from_title_frame(
            df,
            request,
            id_prefix="futu",
            channel="official",
            media_source="futu",
            content_type="wire",
        )

    def _ths(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        try:
            df = self._call(lambda: ak.stock_info_global_ths(), label="stock_info_global_ths")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_global_ths 失败: %s", exc)
            return []
        return self._rows_from_title_frame(
            df,
            request,
            id_prefix="ths",
            channel="official",
            media_source="ths",
            content_type="wire",
        )

    # ---- 论坛 / 社媒情绪 ----

    def _forum(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        out: list[NewsRecord] = []
        if self._want(
            request, "em_comment", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._em_comment(ak, request))
        if self._want(
            request, "em_detail", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._em_comment_detail(ak, request))
        if self._want(
            request, "xueqiu", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._xueqiu_rank(ak, request, kind="tweet"))
        if self._want(
            request,
            "xueqiu_follow",
            group=FORUM_MEDIA,
            default_group=FORUM_MEDIA_DEFAULT,
        ):
            out.extend(self._xueqiu_rank(ak, request, kind="follow"))
        if self._want(
            request, "xueqiu_deal", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._xueqiu_rank(ak, request, kind="deal"))
        if self._want(
            request, "weibo", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._weibo(ak, request))
        if self._want(
            request, "baidu_hot", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._baidu_hot(ak, request))
        if self._want(
            request, "baidu_vote", group=FORUM_MEDIA, default_group=FORUM_MEDIA_DEFAULT
        ):
            out.extend(self._baidu_vote(ak, request))
        return out

    def _em_comment(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """东财千股千评：综合得分/关注指数，情绪模型日频截面。"""
        try:
            df = self._call(lambda: ak.stock_comment_em(), label="stock_comment_em")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_comment_em 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("代码",))
        c_name = col_by_keywords(df.columns, ("名称",))
        c_day = col_by_keywords(df.columns, ("交易日",))
        c_score = col_by_keywords(df.columns, ("综合得分",))
        c_rank = col_by_keywords(df.columns, ("目前排名",))
        c_focus = col_by_keywords(df.columns, ("关注指数",))
        c_inst = col_by_keywords(df.columns, ("机构参与度",))
        want = {_plain(s) for s in (request.symbols or []) if s.strip()}
        rows_iter = list(df.iterrows())
        if want:
            filtered = []
            for i, r in rows_iter:
                code = _plain(as_str(r[c_code])) if c_code is not None else ""
                if code in want:
                    filtered.append((i, r))
            rows_iter = filtered
        else:
            # 开发机默认截断：按关注指数取 top_n
            if c_focus is not None:
                try:
                    df2 = df.copy()
                    df2["_focus"] = df2[c_focus].apply(as_float)
                    df2 = df2.sort_values("_focus", ascending=False).head(
                        max(1, request.forum_top_n)
                    )
                    rows_iter = list(df2.iterrows())
                except Exception:
                    rows_iter = rows_iter[: max(1, request.forum_top_n)]
            else:
                rows_iter = rows_iter[: max(1, request.forum_top_n)]

        out: list[NewsRecord] = []
        for _, r in rows_iter:
            code = _plain(as_str(r[c_code])) if c_code is not None else ""
            if not code:
                continue
            day = as_str(r[c_day])[:10] if c_day is not None else date.today().isoformat()
            try:
                pt = normalize_publish_time(f"{day} 15:00:00")
            except Exception:
                pt = normalize_publish_time(day)
            if not self._in_date_range(pt, request):
                continue
            name = as_str(r[c_name]) if c_name is not None else code
            score = as_float(r[c_score]) if c_score is not None else None
            focus = as_float(r[c_focus]) if c_focus is not None else None
            rank = as_float(r[c_rank]) if c_rank is not None else None
            inst = as_float(r[c_inst]) if c_inst is not None else None
            extra = {
                "score": score,
                "focus": focus,
                "rank": rank,
                "institution_participation": inst,
                "trade_date": day,
            }
            title = f"{name} 千股千评"
            nid = _news_id("em_comment", code, day)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=code,
                    title=title,
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="em_comment",
                    channel="forum",
                    source=self.source,
                    content_type="forum_score",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _xueqiu_rank(
        self, ak: Any, request: FetchRequest, *, kind: str
    ) -> list[NewsRecord]:
        """雪球热度：tweet=讨论 / follow=关注 / deal=交易热度。"""
        api_map = {
            "tweet": ("stock_hot_tweet_xq", "本周新增", "xueqiu", "雪球讨论热度"),
            "follow": ("stock_hot_follow_xq", "最热门", "xueqiu_follow", "雪球关注热度"),
            "deal": ("stock_hot_deal_xq", "最热门", "xueqiu_deal", "雪球交易热度"),
        }
        fn_name, symbol_arg, media, title_suffix = api_map[kind]
        fn = getattr(ak, fn_name, None)
        if fn is None:
            logger.warning("%s 不可用", fn_name)
            return []
        try:
            df = self._call(lambda: fn(symbol=symbol_arg), label=fn_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s 失败: %s", fn_name, exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_code = col_by_keywords(df.columns, ("股票代码", "代码"))
        c_name = col_by_keywords(df.columns, ("股票简称", "名称", "简称"))
        c_attn = col_by_keywords(df.columns, ("关注", "讨论"))
        c_price = col_by_keywords(df.columns, ("最新价",))
        want = {_plain(s) for s in (request.symbols or []) if s.strip()}
        asof = (request.end or date.today().isoformat())[:10]
        try:
            pt = normalize_publish_time(f"{asof} 15:00:00")
        except Exception:
            pt = _now_iso()
        out: list[NewsRecord] = []
        n = 0
        for _, r in df.iterrows():
            raw_code = as_str(r[c_code]) if c_code is not None else ""
            code = _plain(raw_code)
            if not code:
                continue
            if want and code not in want:
                continue
            n += 1
            if not want and n > max(1, request.forum_top_n):
                break
            name = as_str(r[c_name]) if c_name is not None else code
            attn = as_float(r[c_attn]) if c_attn is not None else None
            extra = {
                "metric": kind,
                "attention": attn,
                "price": as_float(r[c_price]) if c_price is not None else None,
                "rank": n,
                "asof": asof,
            }
            nid = _news_id(f"xueqiu_{kind}", code, asof)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=code,
                    title=f"{name} {title_suffix}",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source=media,
                    channel="forum",
                    source=self.source,
                    content_type="forum_heat",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                    url=f"https://xueqiu.com/S/{raw_code}",
                )
            )
        return out

    def _weibo(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """金十微博舆情：名称 + 情绪 rate。"""
        try:
            df = self._call(
                lambda: ak.stock_js_weibo_report(time_period="CNHOUR12"),
                label="stock_js_weibo_report",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_js_weibo_report 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_name = col_by_keywords(df.columns, ("name", "名称")) or df.columns[0]
        c_rate = col_by_keywords(df.columns, ("rate", "情绪")) or df.columns[-1]
        asof = datetime.now().strftime("%Y-%m-%d %H:00:00")
        try:
            pt = normalize_publish_time(asof)
        except Exception:
            pt = _now_iso()
        out: list[NewsRecord] = []
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            if i > max(1, request.forum_top_n):
                break
            name = as_str(r[c_name])
            if not name:
                continue
            rate = as_float(r[c_rate])
            extra = {"rate": rate, "window": "CNHOUR12"}
            nid = _news_id("weibo", name, pt[:13])
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=None,
                    title=f"{name} 微博舆情",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="weibo",
                    channel="forum",
                    source=self.source,
                    content_type="forum_score",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _em_comment_detail(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """千股千评明细：市场热度/主力参与/评分/交易意愿（需 --symbol/--universe）。"""
        symbols = [_plain(s) for s in (request.symbols or []) if s.strip()]
        if not symbols:
            logger.warning("em_detail 需要 --symbol 或 --universe，已跳过")
            return []
        # 开发机保护：单票多次接口
        symbols = symbols[: max(1, min(request.forum_top_n, 20))]
        asof = (request.end or date.today().isoformat())[:10]
        out: list[NewsRecord] = []
        detail_fns = (
            ("desire", "stock_comment_detail_scrd_desire_em", ("交易意愿", "日度交易意愿")),
            ("focus", "stock_comment_detail_scrd_focus_em", ("用户关注指数", "关注")),
            ("score", "stock_comment_detail_zhpj_lspf_em", ("评分",)),
            ("inst", "stock_comment_detail_zlkp_jgcyd_em", ("机构参与度",)),
        )
        for code in symbols:
            extra: dict[str, Any] = {"trade_date": asof, "metrics": {}}
            for key, fn_name, val_keys in detail_fns:
                fn = getattr(ak, fn_name, None)
                if fn is None:
                    continue
                try:
                    df = self._call(lambda f=fn, c=code: f(symbol=c), label=f"{fn_name}:{code}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("%s(%s) 失败: %s", fn_name, code, exc)
                    continue
                if df is None or getattr(df, "empty", True):
                    continue
                c_day = col_by_keywords(df.columns, ("交易日", "日期"))
                c_val = col_by_keywords(df.columns, val_keys) or df.columns[-1]
                # 取最近一行
                row = df.iloc[-1]
                day = as_str(row[c_day])[:10] if c_day is not None else asof
                extra["metrics"][key] = {
                    "value": as_float(row[c_val]),
                    "asof": day,
                }
            if not extra["metrics"]:
                continue
            try:
                pt = normalize_publish_time(f"{asof} 15:00:00")
            except Exception:
                pt = _now_iso()
            if not self._in_date_range(pt, request):
                continue
            nid = _news_id("em_detail", code, asof)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=code,
                    title=f"{code} 千股千评明细",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="em_detail",
                    channel="forum",
                    source=self.source,
                    content_type="forum_score",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _baidu_hot(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """百度 A 股热搜（日截面）。"""
        day = (request.end or date.today().isoformat())[:10]
        ymd = day.replace("-", "")
        try:
            df = self._call(
                lambda: ak.stock_hot_search_baidu(symbol="A股", date=ymd, time="今日"),
                label="stock_hot_search_baidu",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_hot_search_baidu 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_name = col_by_keywords(df.columns, ("名称", "股票", "关键词")) or df.columns[0]
        c_chg = col_by_keywords(df.columns, ("涨跌幅",))
        c_heat = col_by_keywords(df.columns, ("热度", "综合热度"))
        try:
            pt = normalize_publish_time(f"{day} 15:00:00")
        except Exception:
            pt = _now_iso()
        if not self._in_date_range(pt, request):
            return []
        out: list[NewsRecord] = []
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            if i > max(1, request.forum_top_n):
                break
            name = as_str(r[c_name])
            if not name:
                continue
            extra = {
                "rank": i,
                "pct_chg": as_float(r[c_chg]) if c_chg is not None else None,
                "heat": as_float(r[c_heat]) if c_heat is not None else None,
                "asof": day,
            }
            nid = _news_id("baidu_hot", name, day)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=f"{name} 百度热搜",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="baidu_hot",
                    channel="forum",
                    source=self.source,
                    content_type="forum_heat",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _baidu_vote(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """百度看涨看跌投票（需标的）。"""
        symbols = [_plain(s) for s in (request.symbols or []) if s.strip()]
        if not symbols:
            logger.warning("baidu_vote 需要 --symbol 或 --universe，已跳过")
            return []
        symbols = symbols[: max(1, min(request.forum_top_n, 30))]
        asof = (request.end or date.today().isoformat())[:10]
        try:
            pt = normalize_publish_time(f"{asof} 15:00:00")
        except Exception:
            pt = _now_iso()
        out: list[NewsRecord] = []
        for code in symbols:
            try:
                df = self._call(
                    lambda c=code: ak.stock_zh_vote_baidu(symbol=c, indicator="指数"),
                    label=f"stock_zh_vote_baidu:{code}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("stock_zh_vote_baidu(%s) 失败: %s", code, exc)
                continue
            if df is None or getattr(df, "empty", True):
                continue
            # 常见列：看涨/看跌人数或比例
            c_up = col_by_keywords(df.columns, ("看涨", "看多"))
            c_down = col_by_keywords(df.columns, ("看跌", "看空"))
            c_up_pct = col_by_keywords(df.columns, ("看涨比例",))
            c_down_pct = col_by_keywords(df.columns, ("看跌比例",))
            row = df.iloc[0]
            extra = {
                "bull_count": as_float(row[c_up]) if c_up is not None else None,
                "bear_count": as_float(row[c_down]) if c_down is not None else None,
                "bull_pct": as_str(row[c_up_pct]) if c_up_pct is not None else None,
                "bear_pct": as_str(row[c_down_pct]) if c_down_pct is not None else None,
                "asof": asof,
                "raw_rows": int(len(df)),
            }
            nid = _news_id("baidu_vote", code, asof)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    symbol=code,
                    title=f"{code} 百度看涨看跌",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="baidu_vote",
                    channel="forum",
                    source=self.source,
                    content_type="forum_score",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    # ---- 政策语境 / 利好利空原料 ----

    def _policy(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        out: list[NewsRecord] = []
        if self._want(
            request, "cjzc", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            out.extend(self._cjzc(ak, request, channel="policy", content_type="policy"))
        if self._want(
            request, "caixin", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            out.extend(
                self._caixin(ak, request, channel="policy", content_type="policy")
            )
        if self._want(
            request, "cctv", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            if request.start and request.end:
                rows = self._cctv_backfill(ak, request)
                for r in rows:
                    text = f"{r.title} {r.summary or ''}"
                    tags = _policy_tags(text)
                    tone = _tone_hint(text)
                    extra = {"policy_tags": tags, "tone_hint": tone}
                    out.append(
                        NewsRecord(
                            source_news_id=r.source_news_id,
                            title=r.title,
                            summary=r.summary,
                            publish_time=r.publish_time,
                            url=r.url,
                            media_source="cctv",
                            channel="policy",
                            source=self.source,
                            content_type="policy",
                            extra_json=json.dumps(extra, ensure_ascii=False),
                        )
                    )
            else:
                logger.warning("policy/cctv 需要 --start/--end，已跳过")
        if self._want(
            request, "econ", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            out.extend(self._econ_baidu(ak, request))
        if self._want(
            request, "epu", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            out.extend(self._epu_china(ak, request))
        if self._want(
            request, "cls_policy", group=POLICY_MEDIA, default_group=POLICY_MEDIA_DEFAULT
        ):
            out.extend(self._cls_policy(ak, request))
        return out

    def _cjzc(
        self,
        ak: Any,
        request: FetchRequest,
        *,
        channel: str,
        content_type: str,
    ) -> list[NewsRecord]:
        """东财财经早餐：常含证监会/监管/宏观政策要点。"""
        try:
            df = self._call(lambda: ak.stock_info_cjzc_em(), label="stock_info_cjzc_em")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_info_cjzc_em 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_title = col_by_keywords(df.columns, ("标题",)) or df.columns[0]
        c_sum = col_by_keywords(df.columns, ("摘要", "内容"))
        c_time = col_by_keywords(df.columns, ("发布时间", "时间"))
        c_url = col_by_keywords(df.columns, ("链接", "地址", "url"))
        out: list[NewsRecord] = []
        for _, r in df.iterrows():
            title = as_str(r[c_title])
            summary = as_str(r[c_sum])[:1200] if c_sum is not None else None
            if not title and not summary:
                continue
            if not title:
                title = (summary or "")[:80]
            try:
                pt = normalize_publish_time(r[c_time] if c_time is not None else None)
            except Exception:
                continue
            if not self._in_date_range(pt, request):
                continue
            text = f"{title} {summary or ''}"
            tags = _policy_tags(text)
            tone = _tone_hint(text)
            # policy channel：优先保留带政策关键词的条目；无标签也保留早餐全文供人工筛
            extra = {"policy_tags": tags, "tone_hint": tone}
            url = as_str(r[c_url]) if c_url is not None else ""
            nid = _news_id("cjzc", title, pt, url)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=title[:300],
                    summary=summary,
                    publish_time=pt,
                    url=url or None,
                    media_source="cjzc",
                    channel=channel,
                    source=self.source,
                    content_type=content_type,
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _caixin(
        self,
        ak: Any,
        request: FetchRequest,
        *,
        channel: str,
        content_type: str,
    ) -> list[NewsRecord]:
        """财新要闻摘要。"""
        try:
            df = self._call(lambda: ak.stock_news_main_cx(), label="stock_news_main_cx")
        except Exception as exc:  # noqa: BLE001
            logger.warning("stock_news_main_cx 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_tag = col_by_keywords(df.columns, ("tag", "标签", "栏目"))
        c_sum = col_by_keywords(df.columns, ("summary", "摘要", "内容")) or (
            df.columns[1] if len(df.columns) > 1 else df.columns[0]
        )
        c_url = col_by_keywords(df.columns, ("url", "链接"))
        asof = (request.end or date.today().isoformat())[:10]
        try:
            pt = normalize_publish_time(f"{asof} 08:00:00")
        except Exception:
            pt = _now_iso()
        if not self._in_date_range(pt, request):
            return []
        out: list[NewsRecord] = []
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            if i > max(1, request.forum_top_n):
                break
            summary = as_str(r[c_sum])
            if not summary:
                continue
            tag = as_str(r[c_tag]) if c_tag is not None else ""
            title = (tag + "：" if tag else "") + summary[:80]
            text = f"{tag} {summary}"
            tags = _policy_tags(text)
            tone = _tone_hint(text)
            url = as_str(r[c_url]) if c_url is not None else ""
            extra = {"tag": tag or None, "policy_tags": tags, "tone_hint": tone}
            nid = _news_id("caixin", summary[:120], asof, url)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=title[:300],
                    summary=summary[:1200],
                    publish_time=pt,
                    url=url or None,
                    media_source="caixin",
                    channel=channel,
                    source=self.source,
                    content_type=content_type,
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _econ_baidu(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """百度财经日历（宏观/政策事件节点）。按日拉取，默认最近 1 个交易日。"""
        end = date.fromisoformat((request.end or date.today().isoformat())[:10])
        start = (
            date.fromisoformat(request.start[:10])
            if request.start
            else end - timedelta(days=0)
        )
        if start > end:
            start, end = end, start
        # 开发机保护：最多 3 天
        if (end - start).days > 2:
            start = end - timedelta(days=2)
        out: list[NewsRecord] = []
        d = start
        while d <= end:
            ymd = d.strftime("%Y%m%d")
            try:
                df = self._call(
                    lambda y=ymd: ak.news_economic_baidu(date=y),
                    label=f"news_economic_baidu:{ymd}",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("news_economic_baidu(%s) 失败: %s", ymd, exc)
                d += timedelta(days=1)
                continue
            if df is None or getattr(df, "empty", True):
                d += timedelta(days=1)
                continue
            c_title = col_by_keywords(df.columns, ("事件", "标题", "指标")) or df.columns[0]
            c_time = col_by_keywords(df.columns, ("时间", "日期"))
            c_region = col_by_keywords(df.columns, ("地区", "国家"))
            c_imp = col_by_keywords(df.columns, ("重要性", "星级"))
            for _, r in df.iterrows():
                title = as_str(r[c_title])
                if not title:
                    continue
                raw_pt = as_str(r[c_time]) if c_time is not None else d.isoformat()
                try:
                    pt = normalize_publish_time(raw_pt)
                except Exception:
                    try:
                        pt = normalize_publish_time(f"{d.isoformat()} 09:00:00")
                    except Exception:
                        continue
                text = title
                tags = _policy_tags(text)
                tone = _tone_hint(text)
                extra = {
                    "region": as_str(r[c_region]) if c_region is not None else None,
                    "importance": as_str(r[c_imp]) if c_imp is not None else None,
                    "policy_tags": tags,
                    "tone_hint": tone,
                    "calendar_date": d.isoformat(),
                }
                nid = _news_id("econ", title, pt)
                out.append(
                    NewsRecord(
                        source_news_id=nid,
                        title=title[:300],
                        summary=json.dumps(extra, ensure_ascii=False),
                        publish_time=pt,
                        media_source="econ",
                        channel="policy",
                        source=self.source,
                        content_type="policy",
                        extra_json=json.dumps(extra, ensure_ascii=False),
                    )
                )
            d += timedelta(days=1)
        return out

    def _epu_china(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """中国经济政策不确定性指数（月频量化，环境度量）。"""
        try:
            df = self._call(
                lambda: ak.article_epu_index(symbol="China"),
                label="article_epu_index",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("article_epu_index 失败: %s", exc)
            return []
        if df is None or getattr(df, "empty", True):
            return []
        c_year = col_by_keywords(df.columns, ("year", "年")) or df.columns[0]
        c_month = col_by_keywords(df.columns, ("month", "月"))
        c_idx = col_by_keywords(df.columns, ("China_Policy_Index", "index", "指数")) or (
            df.columns[-1]
        )
        out: list[NewsRecord] = []
        # 默认只保留最近 24 个月，可用 start/end 收窄
        rows = list(df.iterrows())[-24:]
        for _, r in rows:
            try:
                y = int(float(as_str(r[c_year])))
                m = int(float(as_str(r[c_month]))) if c_month is not None else 1
            except Exception:
                continue
            day = f"{y:04d}-{m:02d}-01"
            try:
                pt = normalize_publish_time(f"{day} 00:00:00")
            except Exception:
                continue
            if not self._in_date_range(pt, request):
                continue
            val = as_float(r[c_idx])
            extra = {"epu": val, "year": y, "month": m, "region": "China"}
            nid = _news_id("epu", "China", day)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=f"中国政策不确定性指数 {y}-{m:02d}",
                    summary=json.dumps(extra, ensure_ascii=False),
                    publish_time=pt,
                    media_source="epu",
                    channel="policy",
                    source=self.source,
                    content_type="policy_index",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    def _cls_policy(self, ak: Any, request: FetchRequest) -> list[NewsRecord]:
        """财联社电报中带政策/监管关键词的条目。"""
        rows = self._cls(ak, request)
        out: list[NewsRecord] = []
        for r in rows:
            text = f"{r.title} {r.summary or ''}"
            tags = _policy_tags(text)
            if not tags:
                continue
            tone = _tone_hint(text)
            extra = {"policy_tags": tags, "tone_hint": tone}
            out.append(
                NewsRecord(
                    source_news_id=_news_id("cls_policy", r.source_news_id),
                    title=r.title,
                    summary=r.summary,
                    publish_time=r.publish_time,
                    url=r.url,
                    media_source="cls_policy",
                    channel="policy",
                    source=self.source,
                    content_type="policy",
                    extra_json=json.dumps(extra, ensure_ascii=False),
                )
            )
        return out

    # ---- helpers ----

    def _in_date_range(self, pt: str, request: FetchRequest) -> bool:
        day = pt[:10]
        if request.start and day < request.start[:10]:
            return False
        if request.end and day > request.end[:10]:
            return False
        return True

    def _rows_from_title_frame(
        self,
        df: Any,
        request: FetchRequest,
        *,
        id_prefix: str,
        channel: str,
        media_source: str,
        content_type: str,
    ) -> list[NewsRecord]:
        if df is None or getattr(df, "empty", True):
            return []
        c_title = col_by_keywords(df.columns, ("标题", "title")) or df.columns[0]
        c_sum = col_by_keywords(df.columns, ("摘要", "内容", "content"))
        c_time = col_by_keywords(df.columns, ("发布时间", "时间", "日期"))
        c_url = col_by_keywords(df.columns, ("链接", "url", "地址"))
        out: list[NewsRecord] = []
        for _, r in df.iterrows():
            title = as_str(r[c_title])
            if not title and c_sum is not None:
                title = as_str(r[c_sum])[:80]
            if not title:
                continue
            try:
                pt = normalize_publish_time(r[c_time] if c_time is not None else None)
            except Exception:
                continue
            if not self._in_date_range(pt, request):
                continue
            url = as_str(r[c_url]) if c_url is not None else ""
            nid = _news_id(id_prefix, title, pt, url)
            out.append(
                NewsRecord(
                    source_news_id=nid,
                    title=title[:300],
                    summary=as_str(r[c_sum])[:800] if c_sum is not None else None,
                    publish_time=pt,
                    url=url or None,
                    media_source=media_source,
                    channel=channel,
                    source=self.source,
                    content_type=content_type,
                )
            )
        return out
