# schema

## 名称
可读数据契约与**生产者/消费者登记**（多 Agent 必读）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务行 | — | 本目录为契约文档；实际建表见 `migrations/`，写入方见下表「产消登记」 |


## 本目录模块一览
无子模块；本目录存放表说明与产消清单（随迁移更新）。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| database（父） | `../README.md` | 契约总览 | 父目录 |
| migrations | `../migrations/README.md` | 变更脚本 | 同级，须一致 |
| backend | `../../backend/README.md` | 实现方 | 按本登记读写 |

## 边界
- 做：描述表用途、主键、提交语义、生产者模块、消费者模块。
- 不做：替代 migrations；描述未迁移的口头表。

## 输入
- 与已应用迁移一致的结构

## 输出
- 表文档 + 产消登记表（见下，随实现填充）

## 运行
- 每次加表：先迁移，再更新本登记

## 不变量
- 无生产者/消费者登记的跨模块表不得合入

## 产消登记（模板，实施时填实）

| 表/对象 | 域 | 生产者 | 消费者 | 稳定键 | 提交语义 |
| --- | --- | --- | --- | --- | --- |
| ingest_batch | oltp | data_ingest/ingest_common | orchestrator, ops_monitor, 各下游 | batch_id | module/kind；可标 CORE/ALPHA；created→committed/failed |
| raw_trade_calendar | ref_data | data_ingest/core_ref (calendar) | data_process, security_master, backtest | (exchange, trade_date) + batch_id | CORE |
| raw_security_listing | ref_data | data_ingest/core_ref (listing) | security_master | 业务幂等键 + batch_id | CORE |
| raw_industry_class | ref_data | data_ingest/core_ref (industry) | security_master, research_lab | (symbol, effective_date, standard, source) | CORE；行业中性 |
| raw_share_capital | ref_data | data_ingest/core_ref (share_capital) | data_process, research_lab | (symbol, effective_date, source) | CORE；市值/换手 |
| raw_index_member | ref_data | data_ingest/core_ref (index_member) | security_master, research_lab, portfolio_construct | (index_symbol, symbol, trade_date, source) | P1；成分与权重 |
| raw_special_treat | ref_data | data_ingest/core_ref (special_treat) | security_master, risk_engine, research_lab | (symbol, effective_date, treat_type, source) | P1；ST 等状态史 |
| raw_equity_bar_1d | market_data | data_ingest/core_market (equity_1d) | data_process | (symbol, trade_date, source) | CORE |
| raw_adj_factor | market_data | data_ingest/core_market (adj_factor) | data_process | (symbol, trade_date, factor_type, source) | CORE；与日线同级 |
| raw_suspend / raw_limit_board | market_data | data_ingest/core_market (suspend/limit) | data_process, backtest | (symbol, trade_date, event_type, source) | CORE |
| raw_index_bar_1d | market_data | data_ingest/core_market (index_1d) | data_process, backtest | (index_symbol, trade_date, source) | CORE；基准 |
| raw_corp_action | ref_data | data_ingest/core_market (corp_action) | data_process | 事件幂等键 + batch_id | P1 |
| raw_market_rank_1d | market_data | data_ingest/core_market (market_rank) | research_lab / 选股筛选 | (trade_date, rank_type, symbol, source) | P1 |
| raw_abnormal_move | market_data | data_ingest/core_market (abnormal_move) | research_lab / 短线事件 | (trade_date, change_type, symbol, source_event_id, source) | P1 |
| raw_board_bar_1d | market_data | data_ingest/core_market (board_1d) | research_lab / 行业轮动 | (board_type, board_name, trade_date, source) | P1 |
| raw_valuation_1d | market_data | data_ingest/alpha_fundamental (valuation) | research_lab / 估值因子 | (symbol, trade_date, source) | P1 |
| raw_holder_count | market_data | data_ingest/alpha_fundamental (holder) | research_lab / 筹码 | (symbol, asof_date, source) | P2 |
| raw_restricted_release | ref_data | data_ingest/core_ref (restricted_release) | risk_engine / research_lab | (symbol, release_date, source_event_id, source) | P1 |
| raw_dragon_tiger | market_data | data_ingest/alpha_flow (dragon_tiger) | research_lab / 情绪 | (symbol, trade_date, source_event_id, source) | P2 |
| raw_dragon_tiger_seat | market_data | data_ingest/alpha_flow (dragon_tiger_seat) | research_lab / 席位追踪 | (trade_date, seat_name, source_event_id, source) | P2 |
| raw_block_trade | market_data | data_ingest/alpha_flow (block_trade) | research_lab / 折溢价 | (symbol, trade_date, source_event_id, source) | P2 |
| raw_equity_bar_1m | market_data | data_ingest/core_market (equity_1m) | data_process | (symbol, bar_time, source) | P2 |
| raw_fund_statement / raw_fund_indicator | market_data | data_ingest/alpha_fundamental (statement/indicator) | data_process, research_lab | 披露幂等键 + batch_id | ALPHA P1 |
| raw_consensus_estimate | market_data | data_ingest/alpha_fundamental (consensus) | data_process, research_lab | (symbol, asof_date, metric, period_year, source, version) | ALPHA P2；须 PIT |
| raw_money_flow / raw_margin / raw_dragon_tiger / raw_block_trade | market_data | data_ingest/alpha_flow | research_lab | 见各表 UNIQUE | ALPHA P1/P2 |
| raw_money_flow | market_data | data_ingest/alpha_flow (northbound/stock_flow) | data_process, research_lab | 业务幂等键 + batch_id | ALPHA P1 |
| raw_margin | market_data | data_ingest/alpha_flow (margin) | data_process, research_lab | (symbol, trade_date, source) | ALPHA P2 |
| raw_dragon_tiger | market_data | data_ingest/alpha_flow (dragon_tiger) | data_process, research_lab | 源事件 ID + trade_date | ALPHA P2 |
| raw_block_trade | market_data | data_ingest/alpha_flow (block_trade) | data_process, research_lab | 源事件 ID + trade_date | ALPHA P2 |
| raw_announcement | market_data | data_ingest/alpha_announcement | data_process, research_lab, risk_engine | source_ann_id+source；必含 publish_time、category_raw、channel | ALPHA；点时=publish_time；正文用 content_uri |
| ingest_announcement_watermark | oltp | data_ingest/alpha_announcement | alpha_announcement, ops_monitor | (source, channel, watch_key?) | 公告增量/订阅水位线 |
| raw_news_media | market_data | data_ingest/alpha_news_monitor | data_process, research_lab, ops_monitor | 源 ID/哈希 + batch_id | ALPHA；与公告分表；channel=official/forum/policy；`content_type`（含 policy/policy_index）与 `extra_json`（情绪分、`policy_tags`/`tone_hint`/EPU） |
| ingest_news_watermark | oltp | data_ingest/alpha_news_monitor | alpha_news_monitor, ops_monitor | (source, channel) | 新闻监控水位线 |
| raw_major_contract | market_data | data_ingest/alpha_contract | research_lab, data_process | (symbol, announce_date, source_event_id, source) | ALPHA；重大合同/中标；点时=`announce_date`；`is_win_bid` 标中标类 |
| raw_stock_relation | market_data | data_ingest/alpha_relation | research_lab, api_gateway/frontend | (src, dst, relation_type, as_of_date, source_event_id, source) | ALPHA；个股关系边；`HOT_RELATE`/`HOLDER_TEAM`/`CONCEPT_CO`/`INDUSTRY_CO` |
| raw_*（统称） | market_data | data_ingest | data_process | batch_id | 提交后可见 |
| process_batch | oltp | data_process | data_quality, ops_monitor | process_batch_id | created→committed/failed |
| processed_equity_bar_1d | market_data | data_process (equity_1d) | data_quality, research_lab, backtest | (symbol, trade_date, factor_type) | 复权价/ret_1d/can_buy|sell；缺板时 limit_derived |
| processed_index_bar_1d | market_data | data_process (index_1d) | data_quality, research_lab, backtest | (index_symbol, trade_date) | 指数收益 |
| processed_fund_snapshot | market_data | data_process (fundamental_pit) | research_lab | (symbol, valid_from) | 基本面 PIT 区间；`publish_date`=`announce_date`；`valid_to` 可空 |
| processed_*（统称） | market_data | data_process | data_quality, research_lab, backtest | process_batch_id | 提交后可见 |
| dq_run | oltp | data_quality | ops_monitor, orchestrator | dq_run_id | created→passed/failed |
| dq_result | oltp | data_quality | orchestrator, research_lab, signal_prod, ops_monitor | (dq_run_id, rule_code) | 单规则 pass/fail |
| dq_gate | oltp | data_quality | research_lab, backtest, signal_prod, orchestrator | (scope, start, end, factor_type) | 区间最新闸门 |
| universe_snapshot | ref_data | security_master | research_lab, signal_prod, portfolio_construct, backtest | (as_of_date, universe_code) / universe_snapshot_id | 日快照头；committed 后可见 |
| universe_snapshot_member | ref_data | security_master | research_lab, signal_prod, portfolio_construct, backtest | (universe_snapshot_id, symbol) | 快照成员（含 ST/行业/权重） |
| research_run | oltp | research_lab | strategy_registry, ops_monitor | run_id | 计算/评估元数据；`meta_json` 含 IC 报告 |
| research_factor_value | oltp | research_lab | backtest, strategy_registry | (factor_code, symbol, trade_date, universe_code) | 基线因子值；点时=trade_date；幂等 UPSERT |
| research_* | oltp | research_lab | strategy_registry, backtest | run_id | 非 live |
| strategy_version | oltp | strategy_registry | signal_prod, backtest | strategy_version | 状态机 |
| signal_prod_* | oltp | signal_prod | portfolio_construct, backtest | signal_batch_id | 仅已晋升版本 |
| portfolio_target | oltp | portfolio_construct | risk_engine | portfolio_id | draft→… |
| risk_decision | oltp | risk_engine | execution | portfolio_id | approved/rejected |
| kill_switch | oltp | risk_engine | execution | account/global | 下单前必读 |
| order_event / fill_event | oltp | execution | ledger, ops_monitor | order_id / fill_id | 事件追加 |
| ledger_entry / balance | oltp | ledger | portfolio_construct, risk_engine, ops_monitor | account_id | 分录过账 |
| cost_params | ref_data | migrations 种子 | backtest, execution, ledger | version | 统一费用口径 |
| backtest_run | oltp | backtest | frontend/backtest_view, research_lab, ops_monitor | run_id | running→committed/failed |
| backtest_nav | oltp | backtest | frontend/backtest_view | (run_id, trade_date) | 日净值与基准 |
| backtest_trade | oltp | backtest | frontend/backtest_view | run_id | 成交假设 |
| job_status | oltp | orchestrator | ops_monitor, api_gateway | job_id | 状态机 |

## 费用模型

统一 `cost_params`（佣金、印花税、滑点假设等）；`backtest` 与 `execution`/`ledger` 必须读同一套版本化参数，禁止模块内写死不一致费率。
