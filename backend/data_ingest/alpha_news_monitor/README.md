# alpha_news_monitor

## 名称
量化 ALPHA · **新闻资讯监控获取**：持续/增量监控媒体与资讯源，落库供舆情与主题类研究（不阻塞 CORE）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 媒体新闻/资讯 | `raw_news_media` | kind=`news_incremental` / `news_watchlist` / `news_backfill` |
| 新闻监控水位线 | `ingest_news_watermark` | 增量/订阅任务更新 |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移：`database/migrations/006_alpha_news_monitor.sql`。  
**不写入** `raw_announcement`。

## 本目录模块一览

| ingest_kind | 优先级 | 输出表 | 说明 |
| --- | --- | --- | --- |
| `news_incremental` | P1 | `raw_news_media` | 东财全球快讯增量 |
| `news_watchlist` | P1 | `raw_news_media` | 个股资讯订阅 |
| `news_backfill` | P2 | `raw_news_media` | 快讯 + 可选 CCTV 日更回填 |

## 运行

```bash
cd backend
python main.py migrate
python main.py alpha_news_monitor --kind news_incremental
python main.py alpha_news_monitor --kind news_watchlist --symbol 600000
python main.py alpha_news_monitor --kind news_backfill --start 2026-07-22 --end 2026-07-23
python -m data_ingest.alpha_news_monitor.selfcheck
```

### 真实源接口

| kind | 接口 |
| --- | --- |
| incremental / backfill | `stock_info_global_em` |
| watchlist | `stock_news_em` |
| backfill 补充 | `news_cctv` |

## 不变量
- 幂等：`source_news_id` + `source`
- 策略只用 `publish_time`，禁止用 `ingested_at` 冒充
- 与公告表物理分离；ALPHA 失败不阻塞 CORE
