# alpha_announcement

## 名称
量化 ALPHA · 上市公司公告 / 监管披露获取与监控（事件驱动主原料；与 `alpha_news_monitor` **分表、分模块**）。

## 生产数据与落库表

本模块（已实现）生产法定公告/监管披露原始数据，经库交接后供 process / research / risk 消费。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 公告元数据（标题、分类、点时、链接等） | `raw_announcement` | `ann_incremental` / `ann_watchlist` / `ann_backfill` / `ann_by_category` 拉取成功并 upsert |
| 增量/订阅水位线 | `ingest_announcement_watermark` | 仅 `ann_incremental`、`ann_watchlist` 在有更新时推进（不回退） |
| 任务批次 | `ingest_batch` | 经 `ingest_common`：created → committed/failed |

**不写入**：`raw_news_media`（媒体新闻）、财报数值表（`raw_fund_*`，归 alpha_fundamental）。

主要字段（`raw_announcement`）：`source_ann_id`, `symbol`, `title`, `publish_time`, `category_raw`, `category_norm`, `url`, `content_uri`, `content_hash`, `channel`, `source`, `batch_id`, `ingested_at`。

迁移脚本：`database/migrations/001_alpha_announcement.sql`。


## 本目录模块一览
无子模块；按 `ingest_kind` 拉数（语义对齐新闻监控模块）。

| ingest_kind | 优先级 | 输出表 | 说明 |
| --- | --- | --- | --- |
| `ann_incremental` | P1 | `raw_announcement` | 水位线增量监控（盘中/定时主路径） |
| `ann_watchlist` | P1 | `raw_announcement` | 标的池/持仓相关公告订阅监控 |
| `ann_backfill` | P1 | `raw_announcement` | 历史回填（事件研究样本） |
| `ann_by_category` | P2 | `raw_announcement` | 按高价值分类拉取（减持/立案/回购等） |

已废弃 kind 名（勿再用）：`announcement`、`announcement_incremental`。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | 总览 | 父目录 |
| ingest_common | `../ingest_common/README.md` | batch / 限流 | 可引用 |
| alpha_news_monitor | `../alpha_news_monitor/README.md` | 媒体新闻监控 | 同级；**禁止混表** |
| alpha_fundamental | `../alpha_fundamental/README.md` | 财报数值 | 同级；预告事件在此，报表数字在彼 |
| core_market | `../core_market/README.md` | 价量 CORE | 不阻塞、不依赖 |
| orchestrator | `../../orchestrator/README.md` | 调度 | 触发增量/订阅/回填 |
| ops_monitor | `../../ops_monitor/README.md` | 告警 | 可订阅新公告 batch（只传 ID） |
| data_process | `../../data_process/README.md` | 去重、分类映射、标的对齐 | 下游 |
| research_lab | `../../research_lab/README.md` | 事件因子 | 下游 |
| risk_engine | `../../risk_engine/README.md` | 风险过滤 | 可消费立案/处罚类事件（经库） |
| database/schema | `../../../database/schema/README.md` | 契约 | 上游 |

## 边界
- 做：拉取公告元数据与可选正文/附件 URI；水位线增量；按池/分类过滤；落库后发就绪事件（仅 `batch_id`）。
- 不做：NLP/情感；写入 `raw_news_media`；在本模块解析财报科目数值（归 `alpha_fundamental`）；阻塞 CORE；跨模块直传正文全文。

## 与 fundamental 的交接
- **本模块**：业绩预告/快报/修正等**披露事件**（标题、分类、时间、链接）。
- **alpha_fundamental**：报表/指标**数值**（`announce_date` + `report_period`）。
- 禁止在公告表里塞完整三大报表宽表；禁止 fundamental 用「最新公告标题」代替点时披露。

## 监控语义
- **增量 (`ann_incremental`)**：自水位线拉取新公告；水位写入 `ingest_announcement_watermark`，可恢复。
- **订阅 (`ann_watchlist`)**：仅监控配置标的池（或与持仓引用 ID 对应的池快照，池本身经库）。
- **回填 (`ann_backfill`)**：按历史区间补样本；不抢占盘中增量配额。
- **分类 (`ann_by_category`)**：按配置的高价值类别拉取；类别列表见下，实现为过滤条件而非新子模块。

## 输入
- 源配置、日期区间或水位线、标的池、分类过滤、轮询间隔
- `job_id` + `ingest_kind`

## 输出
- `raw_announcement` + `ingest_batch`
- `ingest_announcement_watermark`（增量/订阅任务更新）

## `raw_announcement` 必填/约定字段（契约级）

| 字段 | 要求 | 说明 |
| --- | --- | --- |
| `source_ann_id` | 必填（或等价源主键） | 幂等主键组成部分 |
| `symbol` | 有则必填 | 无标的的监管类可用空+`channel` |
| `title` | 必填 | 标题 |
| `publish_time` | 必填 | **点时**；策略/回测只用此时点 |
| `category_raw` | 必填 | 源侧原始分类/栏目 |
| `category_norm` | 可选 | 规范化类别（可由 process 回填，ingest 能映射则写） |
| `url` | 建议必填 | 公告页链接 |
| `content_uri` | 可选 | 正文/PDF 对象存储 URI |
| `content_hash` | 有正文时必填 | 校验与去重 |
| `channel` | 必填 | 如 `cninfo` / `sse` / `szse` / `regulator` |
| `source` | 必填 | 数据源标识 |
| `ingested_at` | 必填 | 入库时间（**不得**当 publish_time 用） |

## 量化高价值类别（`ann_by_category` / 过滤配置）

| category_norm（建议） | 用途 |
| --- | --- |
| `earnings_preview` / `earnings_flash` / `earnings_revision` | 盈余事件 |
| `share_increase` / `share_decrease` / `buyback` / `equity_incentive` | 供给与治理 |
| `investigation` / `penalty` / `inquiry` | 风险剔除 |
| `restructure` / `halt_related` | 重大资产/停复牌相关 |
| `dividend_plan` | 与 `core_market/corp_action` 交叉校验 |

不为每个类别新建子模块；用配置 + `category_raw`/`category_norm` 过滤。

## 运行

```bash
cd backend
pip install -r requirements.txt
python main.py migrate
# 默认 --source eastmoney（真实）
python main.py alpha_announcement --kind ann_incremental
python main.py alpha_announcement --kind ann_watchlist --symbol 600000
python main.py alpha_announcement --kind ann_backfill --symbol 600000 --start 2026-07-01 --end 2026-07-23
python main.py alpha_announcement --kind ann_by_category --category share_decrease --start 2026-07-23 --end 2026-07-23
# 备选巨潮 / 离线夹具
python main.py alpha_announcement --kind ann_watchlist --source cninfo --symbol 600000
python main.py alpha_announcement --kind ann_incremental --source mock
```

### 真实源接口映射

| source | 接口 | 适用 kind |
| --- | --- | --- |
| `eastmoney`（默认） | `stock_notice_report`（全市场按日） | `ann_incremental` / `ann_by_category` |
| `eastmoney` | `stock_individual_notice_report`（个股区间） | `ann_watchlist` / `ann_backfill` |
| `cninfo` | 巨潮 `hisAnnouncement/query` HTTP | 全 kind（网络不稳时易失败） |
| `mock` | 本地夹具 | 离线自检 |

调度建议：
```text
交易时段：ann_incremental ∥ ann_watchlist
夜间/周末：ann_backfill；按需 ann_by_category
与 alpha_news_monitor 并行，互不替代
```

实现入口：`service.AnnouncementIngestService`；后端总入口：`backend/main.py`。
默认 SQLite：`data/ashare.db`（可用环境变量 `ASHARE_DATABASE_URL` 覆盖）。

自检（不依赖外网）：
```bash
cd backend
python -m data_ingest.alpha_announcement.selfcheck
```

说明：默认 `eastmoney`；巨潮不稳时勿依赖 `cninfo`。`--no-fallback` 在主源失败时会 `failed` 而不落 mock。

## 不变量
- 幂等：`source_ann_id` + `source`（或文档化的业务键）
- 信号/回测只用 `publish_time`，禁止用 `ingested_at` 冒充
- 公告与 `raw_news_media` 物理分离
- ALPHA 失败不得阻塞 CORE
- 正文大字段优先对象存储，库内保留 URI + hash
