# migrations

## 名称
数据库结构变更的有序迁移脚本。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务行 | — | 仅执行 DDL/结构变更；例如 `001_alpha_announcement.sql` 创建 `raw_announcement` 等表 |


## 本目录模块一览

命名：`NNN_<feature>.sql`（零填充）。当前：`001`–`018`。

| 文件 | 要点 |
| --- | --- |
| `001`–`010` | 公告、core_ref、core_market、fundamental、flow、news、process、DQ、security_master、backtest |
| `011_market_rank.sql` | `raw_market_rank_1d` |
| `012_market_microstructure.sql` | `raw_abnormal_move`、`raw_dragon_tiger_seat` |
| `013_ingest_enhancements.sql` | `raw_valuation_1d`、`raw_board_bar_1d`、`raw_restricted_release`、`raw_holder_count` |
| `014_news_sentiment.sql` | `raw_news_media.content_type` / `extra_json`（官方快讯/论坛情绪/政策语境） |
| `015_alpha_contract.sql` | `raw_major_contract`（重大合同 / 中标） |
| `016_alpha_relation.sql` | `raw_stock_relation`（个股关系边 / 图谱） |
| `017_research_lab.sql` | `research_run`、`research_factor_value`（基线因子） |
| `018_phase3_pit_correctness.sql` | `processed_fund_snapshot`（基本面 PIT 区间） |

应用：`cd backend && python main.py migrate`（幂等记入 `schema_migrations`）。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| database（父） | `../README.md` | 总览 | 父目录 |
| schema | `../schema/README.md` | 产消与表说明 | 同级，须同步 |
| seeds | `../seeds/README.md` | 种子 | 依赖已迁移结构 |
| backend | `../../backend/README.md` | 实现 | 迁移合并后再改代码 |

## 边界
- 做：schema 变更脚本。
- 不做：业务计算；全量行情转储。

## 输入
- 评审通过的结构变更

## 输出
- 有序迁移文件

## 运行
- 统一迁移命令；禁止生产手工改表不补迁移

## 不变量
- 不改写已发布迁移；修正用新迁移
- 同步更新 `schema/` 产消登记
