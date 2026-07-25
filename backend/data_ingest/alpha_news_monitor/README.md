# alpha_news_monitor

## 名称
量化 ALPHA · **新闻 / 官方快讯 / 论坛情绪 / 政策语境**监控获取：落库供舆情与利好利空研究（不阻塞 CORE）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 媒体新闻/资讯/论坛情绪/政策原料 | `raw_news_media` | 各 news_* kind |
| 新闻监控水位线 | `ingest_news_watermark` | 增量类任务更新 |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移：`006_alpha_news_monitor.sql`、`014_news_sentiment.sql`（`content_type` / `extra_json`）。  
**不写入** `raw_announcement`（法定公告见 `alpha_announcement`）。

### `raw_news_media` 关键字段

| 字段 | 含义 |
| --- | --- |
| `content_type` | `news` / `wire` / `forum_heat` / `forum_score` / `policy` / `policy_index` |
| `extra_json` | 情绪得分、关注度、`policy_tags`、`tone_hint`、EPU 等 |
| `channel` | `eastmoney` / `official` / `forum` / `policy` / `cctv` … |
| `media_source` | 细源：`cls` / `cjzc` / `em_comment` / `baidu_hot` / `epu` … |

## 本目录模块一览

| ingest_kind | 优先级 | 说明 |
| --- | --- | --- |
| `news_incremental` | P1 | 东财全球快讯增量 |
| `news_watchlist` | P1 | 个股资讯订阅 |
| `news_backfill` | P2 | 快讯 + 可选 CCTV 日更回填 |
| `news_official` | P1 | 通讯社快讯 + 财经早餐/财新 |
| `news_forum` | P1 | 论坛/社媒情绪（默认轻量；扩展源需 `--media`） |
| `news_policy` | P1 | **政策语境原料**：早餐/财新/EPU + 可选 CCTV/经济日历/财联社政策过滤 |

## 运行

```bash
cd backend
python main.py migrate

# 既有
python main.py alpha_news_monitor --kind news_incremental
python main.py alpha_news_monitor --kind news_watchlist --symbol 600000
python main.py alpha_news_monitor --kind news_backfill --start 2026-07-22 --end 2026-07-23

# 官方快讯
python main.py alpha_news_monitor --kind news_official
python main.py alpha_news_monitor --kind news_official --media cls --media cjzc

# 论坛情绪（默认：千股千评 + 雪球讨论 + 微博）
python main.py alpha_news_monitor --kind news_forum --forum-top-n 50
python main.py alpha_news_monitor --kind news_forum --media em_comment --universe TOP100
# 扩展子源（需显式 --media）
python main.py alpha_news_monitor --kind news_forum --media em_detail --symbol 600519 --forum-top-n 5
python main.py alpha_news_monitor --kind news_forum --media xueqiu_follow --media baidu_hot --forum-top-n 30
python main.py alpha_news_monitor --kind news_forum --media baidu_vote --symbol 000001 --symbol 600519

# 政策语境（利好利空分析原料；默认 cjzc + caixin + epu）
python main.py alpha_news_monitor --kind news_policy
python main.py alpha_news_monitor --kind news_policy --media cls_policy --media cjzc
python main.py alpha_news_monitor --kind news_policy --media cctv --start 2026-07-22 --end 2026-07-23
python main.py alpha_news_monitor --kind news_policy --media econ --end 2026-07-24

python -m data_ingest.alpha_news_monitor.selfcheck
```

### 真实源接口映射（`akshare`）

| kind / 子源 | 接口 | 产出 |
| --- | --- | --- |
| incremental / backfill | `stock_info_global_em` | 东财全球快讯 |
| watchlist | `stock_news_em` | 个股资讯 |
| official / policy `cctv` | `news_cctv` | 央视财经日更 |
| official `cls` | `stock_info_global_cls` | 财联社电报 |
| official `sina` | `stock_info_global_sina` | 新浪财经快讯 |
| official `futu` | `stock_info_global_futu` | 富途快讯 |
| official `ths` | `stock_info_global_ths` | 同花顺快讯 |
| official/policy `cjzc` | `stock_info_cjzc_em` | 东财财经早餐 |
| official/policy `caixin` | `stock_news_main_cx` | 财新要闻摘要 |
| forum `em_comment` | `stock_comment_em` | 千股千评得分/关注 |
| forum `em_detail` | `stock_comment_detail_*_em` | 意愿/关注/评分/机构参与（需标的） |
| forum `xueqiu` | `stock_hot_tweet_xq` | 雪球讨论热度 |
| forum `xueqiu_follow` | `stock_hot_follow_xq` | 雪球关注热度 |
| forum `xueqiu_deal` | `stock_hot_deal_xq` | 雪球交易热度 |
| forum `weibo` | `stock_js_weibo_report` | 微博舆情 rate |
| forum `baidu_hot` | `stock_hot_search_baidu` | 百度 A 股热搜 |
| forum `baidu_vote` | `stock_zh_vote_baidu` | 百度看涨看跌（需标的） |
| policy `econ` | `news_economic_baidu` | 百度财经日历 |
| policy `epu` | `article_epu_index(China)` | 政策不确定性指数（月频） |
| policy `cls_policy` | `stock_info_global_cls` + 关键词过滤 | 政策/监管电报子集 |

说明：
- 法定上市公司公告仍走 `alpha_announcement`，本模块不重复拉取。
- `news_forum` 无 `--media` 时只拉默认三源；`em_detail` / 雪球 follow·deal / 百度类需显式 `--media`。
- `extra_json.policy_tags` / `tone_hint` 为**关键词启发式**（`bullish_hint` / `bearish_hint` / `mixed_hint`），供后续标注与模型特征，不是最终利好利空结论。
- `econ`（百度日历）在部分环境可能因 SSL/Cookie 失败，失败只打日志不阻断其它子源。

## 情绪 / 政策用法（建议）

```text
wire/news     → 文本嵌入 / 事件抽取
forum_score   → 日频截面（得分、关注、微博 rate、百度投票）
forum_heat    → 拥挤度 / 热度排名（雪球/百度热搜）
policy        → 政策事件文本 + policy_tags + tone_hint
policy_index  → EPU 月频环境变量（不确定性升高常对应风险偏好下降）
点时一律用 publish_time，禁止用 ingested_at
```

## 不变量
- 幂等：`source_news_id` + `source`
- 策略只用 `publish_time`
- 与公告表物理分离；ALPHA 失败不阻塞 CORE
