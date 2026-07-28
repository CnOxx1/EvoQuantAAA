# migrations

## 名称
数据库结构变更的有序迁移脚本。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务行 | — | 仅执行 DDL/结构变更；例如 `001_alpha_announcement.sql` 创建 `raw_announcement` 等表 |


## 本目录模块一览

命名：`NNN_<feature>.sql`（零填充）。当前：`001`–`035`。

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
| `019_ops_schedule.sql` | `ops_alert`（编排告警） |
| `020_tech_indicator.sql` | `processed_tech_indicator_1d`（日线技术指标长表） |
| `021_tech_indicator_category.sql` | `processed_tech_indicator_1d.category`（pandas-ta 分类） |
| `022_equity_bar_min.sql` | `raw/processed_equity_bar_min` + `processed_tech_indicator_min`（15m/60m） |
| `023_strategy_signal.sql` | `strategy_version` / `strategy_transition` / `signal_batch` / `signal_prod_weight` |
| `024_portfolio_construct.sql` | `portfolio_target` / `portfolio_target_position`（草稿） |
| `025_risk_engine.sql` | `risk_decision` / `kill_switch` / `risk_limits` |
| `026_execution.sql` | `execution_run` / `order_event` / `fill_event` |
| `027_ledger.sql` | `ledger_account` / `ledger_posting` / `ledger_entry` / `ledger_balance` / `ledger_lot` |
| `028_api_gateway.sql` | `api_audit_log`（网关写操作审计） |
| `029_prod_hardening.sql` | 组合按日活跃唯一；execution/ledger `running` 唯一 |
| `030_quant_correctness.sql` | `portfolio_target_position.can_sell`；`strategy_capital_alloc` |
| `031_strategy_sleeve.sql` | `ledger_sleeve_position`；`ledger_lot.strategy_version` |
| `032_promotion_gates.sql` | `promotion_gate_params` / `promotion_gate_result`（晋升质量门） |
| `033_execution_pending.sql` | `execution_pending` / `execution_pending_event`；`execution_run.run_kind` |
| `034_risk_adv_industry.sql` | `risk_limits` 行业/ADV 列 + 种子 `v2_adv_industry` |
| `035_impact_cost.sql` | `cost_params` 冲击列 + 种子 `v2_sqrt_impact` |

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
