# data_ingest

## 名称
量化导向的数据获取层：先保证**可回测、可成交的收益序列**，再扩展 alpha 数据源。  
外部源 → `raw_*`（经库交接）；任务维度为 `(ingest_module, ingest_kind)`。

## 生产数据与落库表

本包各子域写入对应 `raw_*` / 水位 / `ingest_batch`；明细见各子目录本节。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 批次元数据 | `ingest_batch` | 各子域任务经 ingest_common 创建/提交 |
| CORE/ALPHA 原始数据 | 各 `raw_*` | 见 `core_ref` / `core_market` / `alpha_*` |


## 设计原则（量化优先）

1. **CORE 先于 ALPHA**：没有复权收益与可成交约束，不做因子/舆情。  
2. **一个 CORE 行情域打包「价 + 权息 + 可成交」**：避免 Agent 只拉日线却忘复权/停牌。  
3. **ALPHA 可插拔**：基本面/资金/文本不影响 CORE 流水线。  
4. **点时与幂等**：所有可用于信号的字段必须可追溯发布/交易时点。  
5. **增强优先加 kind，不拆新模块**：指数成分、ST 史、两融、龙虎榜、一致预期等挂到现有域；仅流水线形态完全不同时才新开模块（如 Tick）。  
6. **本地只沉淀龙头，其余按需 API**：默认 Universe=`TOP100` / `SECTOR_LEADERS`；**禁止**对 `ALL_LISTED`（6000+）做行情/财报 bulk。非龙头用 `--symbol` 单票按需拉取。

## 本目录模块一览

| 层级 | 模块 | 路径 | 优先级 | 量化角色 | 主要 ingest_kind |
| --- | --- | --- | --- | --- | --- |
| 基建 | ingest_common | `ingest_common/` | P0 | batch / 源适配 | — |
| CORE | core_ref | `core_ref/` | P0 | Universe / 日历 / 成分 / ST 原料 | 见下 |
| CORE | core_market | `core_market/` | P0 | 复权收益与可成交性原料 | 见下 |
| ALPHA | alpha_fundamental | `alpha_fundamental/` | P1 | 财报 + 估值/股东 + 一致预期 | `statement` / `indicator` / `valuation` / `holder` / `consensus` |
| ALPHA | alpha_flow | `alpha_flow/` | P1 | 资金 + 两融/龙虎榜/大宗(P2) | 见下 |
| ALPHA | alpha_announcement | `alpha_announcement/` | P1 | 法定公告监控/回填 | `ann_incremental` / `ann_watchlist` / `ann_backfill` / `ann_by_category`(P2) |
| ALPHA | alpha_news_monitor | `alpha_news_monitor/` | P1 | 新闻/快讯/论坛情绪/政策语境 | `news_*`（见下） |

### core_ref kinds

| ingest_kind | 优先级 | 输出 | 量化用途 |
| --- | --- | --- | --- |
| `calendar` / `listing` / `industry` / `share_capital` | P0 | 见 schema | 日历、上市、行业、股本 |
| `index_member` | P1 | `raw_index_member` | 指数成分与权重 |
| `special_treat` | P1 | `raw_special_treat` | ST/*ST 等状态史 |
| `restricted_release` | P1 | `raw_restricted_release` | 限售解禁日历 |

### core_market kinds（量化心脏）

| ingest_kind | 优先级 | 输出 | 量化用途 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | `raw_equity_bar_1d` | 未复权价量 |
| `adj_factor` | P0 | `raw_adj_factor` | 正确收益 |
| `suspend` / `limit` | P0 | `raw_suspend` / `raw_limit_*` | 可成交约束 |
| `index_1d` | P0 | `raw_index_bar_1d` | 基准 |
| `corp_action` | P1 | `raw_corp_action` | 分红/送转/配股 + 复权因子变动点 |
| `market_rank` | P1 | `raw_market_rank_1d` | 涨跌幅/成交量/成交额/换手/人气排名；接口见 `core_market/README.md` |
| `abnormal_move` | P1 | `raw_abnormal_move` | 盘口异动（`stock_changes_em`） |
| `board_1d` | P1 | `raw_board_bar_1d` | 行业/概念板块日线 |
| `equity_1m` | P2 | `raw_equity_bar_1m` | 日内 |

### alpha_flow kinds

| ingest_kind | 优先级 | 输出 | 量化用途 |
| --- | --- | --- | --- |
| `northbound` / `stock_flow` | P1 | `raw_money_flow` | 资金因子 |
| `margin` | P2 | `raw_margin` | 两融（SSE+SZSE 市场与个股） |
| `dragon_tiger` | P2 | `raw_dragon_tiger` | 龙虎榜个股 |
| `dragon_tiger_seat` | P2 | `raw_dragon_tiger_seat` | 龙虎榜活跃营业部 |
| `block_trade` | P2 | `raw_block_trade` | 大宗 |

### alpha_news_monitor kinds

| ingest_kind | 优先级 | 输出 | 量化用途 |
| --- | --- | --- | --- |
| `news_incremental` / `news_watchlist` / `news_backfill` | P1 | `raw_news_media` | 东财快讯、个股资讯、可选 CCTV |
| `news_official` | P1 | `raw_news_media` | 通讯社快讯 + 财经早餐/财新（`--media`） |
| `news_forum` | P1 | `raw_news_media` | 千股千评/雪球/微博；扩展百度热搜·投票等需显式 `--media` |
| `news_policy` | P1 | `raw_news_media` | 政策语境（早餐/财新/EPU + 可选 CCTV/经济日历/财联社政策过滤）；`policy_tags`/`tone_hint` |

明细与接口映射见 `alpha_news_monitor/README.md`。法定公告仍在 `alpha_announcement`，禁止混表。

## 明确暂不新建的模块

| 数据 | 落点 | 何时才拆新模块 |
| --- | --- | --- |
| 一致预期 | `alpha_fundamental/consensus` | 源独立且与财报管线严重冲突时 → 再考虑 `alpha_consensus` |
| 宏观利率/汇率 | 暂缓 | 多资产需求明确时 → `alpha_macro` |
| Tick / L2 | 暂缓 | 日内/高频立项时 → `core_tick` |
| 研报全文 | 暂缓 | 版权与策略需求明确后再议 |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| shared | `../shared/README.md` | 全局工具 | 可引用 |
| database / schema | `../../database/schema/README.md` | raw 产消契约 | 先改库 |
| orchestrator | `../orchestrator/README.md` | 调度 | 先 CORE 再 ALPHA |
| security_master | `../security_master/README.md` | Universe | 消费 core_ref（含 ST/成分） |
| data_process | `../data_process/README.md` | 复权价、掩码、PIT | CORE 主下游 |
| data_quality | `../data_quality/README.md` | 门禁 | CORE 优先 |
| research_lab | `../research_lab/README.md` | 因子 | ALPHA + processed CORE |
| backtest | `../backtest/README.md` | 回测 | 经 process，非 raw 直连策略 |

## 边界
- 做：拉取并落 raw；轻量校验；提交后只发 `batch_id`。  
- 不做：复权价/收益、Universe 快照、DQ 放行、因子、NLP；CORE/ALPHA 内存直传；为增强数据随意新建子目录。

## 运行（量化落地阶段）

```text
阶段 A（必须）：core_ref P0 → core_market P0 → data_process P0 → data_quality
阶段 B：alpha_fundamental(statement/indicator) + alpha_announcement(ann_incremental/watchlist/backfill)
阶段 C：alpha_flow(northbound/stock_flow) + alpha_news_monitor(official/forum/policy)
阶段 D（增强 kind）：core_ref index_member / special_treat / restricted_release
阶段 E（按需）：alpha_flow margin/dragon_tiger/block_trade；fundamental consensus/valuation/holder
```

批量续跑（推荐：龙头 Universe）：

```bash
python main.py security_master --p0 --as-of 2026-07-23

# 长窗 CORE（TOP100，2023–2026）
python main.py core_ref --kind calendar --start 2020-01-01 --end 2026-07-25
python main.py core_market --p0 --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --skip-existing --min-bars 500 --chunk-size 8 --index 000300
python main.py core_market --kind index_1d --start 2023-01-01 --end 2026-07-23 \
  --index 000300 --index 000905 --index 000852
# 停牌/涨跌停：内建按月分块 + 断点续跑
python main.py core_market --kind suspend --start 2023-01-01 --end 2026-07-23 --chunk-months 1 --skip-existing
python main.py core_market --kind limit --start 2023-01-01 --end 2026-07-23 --chunk-months 1 --skip-existing

python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 \
  --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py data_quality --scope CORE --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --factor-type qfq --index 000300

# 公司行为 / 排名 / 异动 / 板块
python main.py core_market --kind corp_action --universe TOP100 --start 2020-01-01 --end 2026-07-23 --skip-existing --chunk-size 10
python main.py core_market --kind market_rank --start 2026-07-01 --end 2026-07-23 --top-n 200
python main.py core_market --kind board_1d --start 2026-07-01 --end 2026-07-23 --board-type INDUSTRY
python main.py core_market --kind abnormal_move --start 2026-07-23 --end 2026-07-23

# 基本面 / 估值 / 解禁 / 资金流
python main.py alpha_fundamental --p1 --universe TOP100 --start 2026-07-01 --skip-existing --chunk-size 10
python main.py alpha_fundamental --kind valuation --universe TOP100 --start 2026-07-01 --end 2026-07-23 --chunk-size 10
python main.py alpha_fundamental --kind holder --universe TOP100 --chunk-size 10
python main.py core_ref --kind restricted_release --start 2026-07-01 --end 2026-07-23 --universe TOP100
python main.py alpha_flow --p1 --universe SECTOR_LEADERS --start 2024-08-01 --end 2024-08-16 --chunk-size 15
python main.py alpha_flow --kind dragon_tiger --start 2026-07-01 --end 2026-07-23

# 新闻 / 论坛情绪 / 政策语境
python main.py alpha_news_monitor --kind news_official --media cls --media cjzc
python main.py alpha_news_monitor --kind news_forum --forum-top-n 50
python main.py alpha_news_monitor --kind news_policy

# 交易日增量（CORE → process → DQ；--with-alpha 含估值/龙虎榜）
python main.py daily --universe TOP100 --as-of 2026-07-23

# 非龙头：按需单票，勿 ALL_LISTED
python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600519
```

**就绪定义（量化）**：`core_ref` + `core_market` 的 **P0** kind 均 committed，且 DQ 对 CORE pass，才允许研究/回测消费该区间。P1/P2 kind 缺失不阻挡 CORE 就绪。

长窗运维：`--min-bars` + `--skip-existing`；按日 kind 用 `--chunk-months`；写库走 `shared/bulk_upsert`；HTTP 重试见 `shared/akshare_call`。

## 不变量
- 未 commit 不宣告就绪；写入幂等  
- 子模块不互相 import 内部实现；共享仅 `ingest_common`  
- `adj_factor` 与同区间 `equity_1d` 齐套前不得宣称可用  
- 公告与新闻分模块分表；ALPHA 失败不阻塞 CORE  
- CORE P0 未齐 = 不可宣称可量化回测  
- 默认 Universe=`TOP100`/`SECTOR_LEADERS`；禁止 ALL_LISTED bulk 日线/财报  


## 量化完备性检查表

| 问题 | 依赖 | 未满足时 |
| --- | --- | --- |
| 交易日是否正确？ | core_ref/calendar | 禁跑回测 |
| 股票是否曾在池内？ | core_ref/listing(+industry) | Universe 不可信 |
| 收益是否除权正确？ | core_market/adj_factor | 禁跑回测 |
| 是否可能买不到？ | core_market/suspend,limit | 回测过拟合 |
| 相对谁超额？ | core_market/index_1d | 无法评价策略 |
| 指数增强成分？ | core_ref/index_member | 增强策略延后 |
| ST 历史过滤？ | core_ref/special_treat | 风险过滤偏弱 |
| 基本面/预期？ | alpha_fundamental | 可选 |
| 资金/两融/龙虎榜？ | alpha_flow | 可选 |
| 公告/新闻/政策语境？ | alpha_announcement / alpha_news_monitor | 可选 |
