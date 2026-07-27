# EvoQuantAAA · A 股量化系统

> **控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。**

远程仓库：[CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA)  
完整架构原则：[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)

---

## 1. 项目是什么

EvoQuantAAA 是一套面向 **A 股实盘约束** 的量化研究与生产骨架：从外部数据拉取、复权加工、质量门禁、Universe、回测，一路延伸到信号晋升、组合、风控、OMS 与账本。

当前已完成 **CORE 可回测闭环 + ALPHA 可插拔补数 + 研究/日更编排**；用真实数据源（akshare / 东财等）写入 PostgreSQL，避免 mock 污染生产库。实盘生产链路（信号晋升→组合→风控→OMS→账本）仍待建。

### 1.1 设计目标

| 目标 | 说明 |
| --- | --- |
| 真相在库 | 跨模块业务数据必须落库；下游只读已提交数据与 ID |
| CORE 先于 ALPHA | 先保证复权收益与可成交约束，再扩基本面/资金/文本 |
| 增强不拆模块 | 优先新增 `ingest_kind`，不为同类数据新建空壳模块 |
| A 股约束可回测 | 停牌/涨跌停/`can_buy`/`can_sell`、整手、费用滑点进入回测 |
| 多 Agent 可协作 | 一 Agent 一模块目录；只读对方 README 与 `database/` 契约 |

### 1.2 非目标（当前）

- 前端完整产品化 UI（`frontend/` 多为占位与规划）
- Tick / L2、宏观全量、研报全文（暂缓，见 `data_ingest/README.md`）
- 实盘柜台直连（`execution` / `ledger` 等模块尚在骨架阶段）

---

## 2. 仓库结构

```text
大a / EvoQuantAAA
├── ARCHITECTURE_PRINCIPLES.md   # 强制架构原则
├── DEVELOPMENT_PLAN.md          # 分阶段开发任务书（交接 Agent）
├── README.md                    # 本文件：总览 + 开发更新记录
├── docker-compose.yml
├── frontend/                    # UI（不直连库，经 api_gateway）
├── backend/                     # 业务模块与 CLI 入口 main.py
│   ├── data_ingest/             # CORE / ALPHA 原始数据获取
│   ├── data_process/            # raw → processed
│   ├── data_quality/            # DQ 门禁
│   ├── security_master/         # Universe 日快照
│   ├── backtest/                # A 股约束回测
│   ├── research_lab/            # 基线因子 + IC/分层
│   ├── orchestrator/            # schedule 日更编排
│   ├── ops_monitor/             # 告警 + 覆盖度
│   ├── tests/                   # pytest（不连库）
│   ├── shared/                  # DB / 配置 / Universe 解析等
│   └── …（signal_prod、risk_engine、execution 等骨架）
├── database/
│   ├── migrations/              # 001–029 SQL（权威演进）
│   ├── schema/                  # 产消契约说明
│   └── seeds/
└── scripts/                     # 辅助脚本
```

本地运行时数据目录 `data/`（pgembed、本地库文件）**不入库**，见 `.gitignore`。

---

## 3. 主链路与模块完成度

> **一句话**：数据与研究回测平台已成形；实盘信号、组合、风控、下单、账本、对外 API 还没建。  
> 任务书阶段 1–4 已收官，详见 [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md)。

```text
外部源
  → data_ingest (raw_*, batch_id)
  → data_process (processed_*)
  → data_quality (dq_gate)
  → security_master (universe_snapshot)
  → backtest / research_lab
  → strategy_registry → signal_prod          ← 已落地（FACTOR_TOP_N）
  → portfolio_construct                      ← 已落地（draft）
  → risk_engine                              ← 已落地（approved/rejected + Kill Switch）
  → execution                                ← 已落地（paper order/fill）
  → ledger                                   ← 已落地（过账 + T+1）
  → ops_monitor（告警/覆盖度已落地）

编排：orchestrator（schedule；只传 job_id / batch_id / run_id / strategy_version / portfolio_id / execution_id …）
对外：api_gateway（FastAPI /v1；已落地）
```

已串通能力链：

**取数 → 加工 → DQ → Universe → 因子/研究 → 回测 → 晋升 → 生产信号 → 组合草稿 → 风控放行 → 纸面执行 → 账本过账 → API 网关 → 日更编排与告警**

### 3.1 已完成（可 CLI 跑）

| 模块 | 做什么 |
| --- | --- |
| 契约 / 库 | 迁移 `001`–`029`，PostgreSQL（pgembed） |
| `core_ref` | 日历、上市、行业、股本、成分、ST、解禁 |
| `core_market` | 日线/复权/停牌/涨跌停/指数/公司行为/排名/异动/板块；**15m/60m 分钟 K**（短窗按需）；TOP100 长窗日线已 DQ pass |
| ALPHA ingest | `announcement` / `fundamental` / `flow` / `news` / `contract` / `relation`（财报估值股东、资金两融龙虎榜、公告、新闻/政策、合同中标、个股关系边） |
| `data_process` | 复权、`can_buy`/`can_sell`、涨跌停推导、基本面 PIT、日线技术指标（`core` 13 码 + `full` pandas-ta 全部分类 ~250+ 序列） |
| `data_quality` | CORE gate（含除权校验）+ ALPHA 报告（不进 gate） |
| `security_master` | Universe 快照（`TOP100` / `SECTOR_LEADERS` 等；全市场仅按需） |
| `backtest` | `EW_HOLD` / `EW_REBALANCE` / `FACTOR_TOP_N`（T+1、印花税、整手） |
| `research_lab` | `MOM_20` / `VAL_PE_PCT` / `FLOW_NET_5` + **TECH_RSI_14 / TECH_MACD_HIST / TECH_MA20_BIAS**；RankIC/分层；经库对接回测 |
| `strategy_registry` | 版本登记与晋升（DRAFT→BACKTESTED→PAPER→LIVE）；审计 `strategy_transition` |
| `signal_prod` | PAPER/LIVE 生成 `signal_prod_weight`（FACTOR_TOP_N，前一日因子） |
| `portfolio_construct` | 最近调仓日 **committed** 信号 → 整手目标持仓 **draft**（同日幂等；默认账本 NAV） |
| `risk_engine` | 硬规则审 draft → approved/rejected；Kill Switch；`risk_limits` |
| `execution` | paper OMS：approved → 账本**差额** `order_event`/`fill_event`；portfolio→executed |
| `ledger` | 消费 fill **原子**过账；现金/持仓/`ledger_lot` T+1 可卖 |
| `api_gateway` | FastAPI `/v1`：查询 + Kill/晋升/审核；可选 Bearer；`api_audit_log` |
| `orchestrator` | `schedule`：… → execution → ledger；交易失败 → `degraded` |
| `ops_monitor` | `ops_alert`、可选 webhook、`coverage`（含 news/tech/min） |
| 基建 | pytest、GitHub CI、`daily` 增量流水线 |

### 3.2 未做（骨架 / 范围外）

多数 `frontend/*` 专项页仍占位；**console 只读台已可用**。

本期明确不做：Tick/L2、机器学习因子、多数据源冗余、实盘柜台直连。

---

## 4. 数据与存储

- **默认库**：PostgreSQL（`pgembed` 本地嵌入式，数据在 `data/pgdata`；也可用 `ASHARE_DATABASE_URL`）
- **已弃用**：SQLite `data/ashare.db`（勿再作为生产路径）
- **批次**：`ingest_batch` / `process_batch`；回测 `backtest_run`；DQ `dq_run` / `dq_gate`
- **原则**：mock 仅调试；生产路径使用真实源；禁止把 mock 批次当正式样本

权威表与产消关系见 [`database/schema/README.md`](./database/schema/README.md) 与各模块 README。

---

## 5. 快速开始

```bash
cd backend
pip install -r requirements.txt

# 迁移
python main.py migrate

# CORE 参考 + 行情（示例）
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
# Universe：仅 TOP100 + 行业龙头（不全市场）
python main.py security_master --p0 --as-of 2026-07-23

# 长窗 CORE（推荐）：日历 + TOP100 日线/复权
python main.py core_ref --kind calendar --start 2020-01-01 --end 2026-07-25
python main.py core_market --p0 --universe TOP100 --start 2023-01-01 --end 2026-07-23 --skip-existing --min-bars 500 --chunk-size 8 --index 000300
python main.py core_market --kind index_1d --start 2023-01-01 --end 2026-07-23 --index 000300 --index 000905 --index 000852

# 市场排名（涨跌幅/量额/换手/人气；接口见 core_market README）
python main.py core_market --kind market_rank --start 2026-07-01 --end 2026-07-23 --top-n 200
python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 200 --prefer-spot

# 加工 → 门禁 → 回测（长窗）
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py data_quality --scope CORE --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py backtest --universe TOP100 --start 2023-01-01 --end 2026-07-23 --strategy EW_HOLD --factor-type qfq

# 非龙头个股：按需单票
python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600519
```

更多子命令与 kind 说明：

- [`backend/README.md`](./backend/README.md)
- [`backend/data_ingest/README.md`](./backend/data_ingest/README.md)
- [`backend/data_ingest/core_market/README.md`](./backend/data_ingest/core_market/README.md)（含 `market_rank` 接口映射）

常用 ALPHA / P1 示例：

```bash
python main.py alpha_announcement --kind ann_watchlist --symbol 600000 --start 2024-08-01 --end 2024-08-16 --source eastmoney --no-fallback
python main.py alpha_fundamental --p1 --symbol 600000 --symbol 000001
python main.py alpha_flow --p1 --start 2024-08-01 --end 2024-08-16 --symbol 600000
python main.py alpha_flow --kind margin --start 2024-07-08 --end 2024-07-12 --symbol 600000 --symbol 000001
python main.py core_market --kind corp_action --start 2020-01-01 --end 2026-07-23 --symbol 600000
python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 200 --prefer-spot --rank-type HOT
python main.py core_market --kind abnormal_move --start 2026-07-23 --end 2026-07-23
python main.py core_market --kind limit --start 2026-07-21 --end 2026-07-23
python main.py alpha_flow --kind dragon_tiger --start 2026-07-01 --end 2026-07-23
python main.py alpha_flow --kind dragon_tiger_seat --start 2026-07-01 --end 2026-07-23
python main.py alpha_flow --kind block_trade --start 2026-07-01 --end 2026-07-23
```

---

## 6. 协作约定（多 AI Agent）

- **一个 Agent 只写一个模块目录**，禁止越界改其他模块实现。
- 了解协作：只读对方 `README.md` 与 `database/` 契约。
- 跨模块：先落库，再传 `batch_id` / `job_id` / `run_id` / `strategy_version` 等引用。
- 调度只通过 `orchestrator`；对外 API 只经 `api_gateway`。
- 新增模块或表：更新本文件「开发更新记录」、相关 README，并遵守 [ARCHITECTURE_PRINCIPLES.md §6](./ARCHITECTURE_PRINCIPLES.md#6-合入前检查清单)。

---

## 7. 开发更新记录

> 维护约定：有可合并的功能/数据里程碑时，在本节**顶部**追加一条（新→旧）。  
> 格式：日期 · 标题 · 要点列表 ·（可选）影响范围。

### 2026-07-27 · 阶段 15：策略 sleeve 与回测对齐
- ledger：`ledger_sleeve_position` + `ledger_lot.strategy_version`；execution 差额仅对本策略
- CLI：每个 committed execution 立即 post；已过账禁止 `--force`
- portfolio live：非调仓日 hold；schedule：signal failed 短路
- backtest：FIFO lot T+1 + 未复权 `close` 成交；迁移 `031`
- 数据说明：031 把旧 POSITION 回填到 `strategy_version=''`；新仓用真实 version。开发账户若双 sleeve 并存，合计 NAV 可能偏高（见 `ledger/README`）

### 2026-07-27 · 阶段 14：量化正确性 Critical
- schedule：`factor_refresh` 在 `signal_live` 前重算 LIVE 因子；失败跳过交易链 → `degraded`
- execution：成交前现金投影（先卖后买 / `insufficient_cash` / `clamped_cash`）
- portfolio：`strategy_capital_alloc` 同账户配额；sizing/成交用未复权 `close`；目标腿落 `can_sell`
- risk：同账户同日合并敞口（`ACCOUNT_MAX_*`）；迁移 `030`

### 2026-07-27 · 阶段 13：编排与执行硬化补丁
- execution：order/fill/run/portfolio 状态同事务提交
- schedule：`security_master` 失败跳过交易链 → `degraded`；告警 failed=error / degraded=warning
- API：`ASHARE_API_REQUIRE_TOKEN=1`；Kill 解除后可重审

### 2026-07-27 · 阶段 12：E2E + console 只读页
- `python main.py e2e`：自备种子 register→…→ledger→API，幂等断言
- `frontend/console`：静态页拉 `/v1`；gateway CORS 放开本地静态源

### 2026-07-27 · 阶段 11：生产链路硬化
- 迁移 `029`：组合按日活跃唯一；execution/ledger `running` 唯一
- execution：账本差额成交 + T+1 可卖；portfolio：同日幂等 / 账本 NAV / committed 信号
- ledger：分录与 committed 同事务；schedule 交易失败 → `degraded`
- ingest：`shared.timeutil` + `ingest_common.parse`

### 2026-07-27 · 阶段 10：api_gateway

- 迁移 `028`：`api_audit_log`
- FastAPI `/v1`：strategies / portfolios / risk(kill|review) / executions / ledger / alerts
- 可选 `ASHARE_API_TOKEN`；CLI `gateway --port 8080`；写操作审计

### 2026-07-27 · 阶段 9：ledger（过账 + T+1）

- 迁移 `027`：`ledger_account` / `ledger_posting` / `ledger_entry` / `ledger_balance` / `ledger_lot`
- 消费 committed `fill_event`；FIFO T+1 可卖；同 execution 幂等
- CLI：`ledger ensure|post|show|sellable|list`；`schedule` 过账 unposted

### 2026-07-27 · 阶段 8：execution（paper OMS）

- 迁移 `026`：`execution_run` / `order_event` / `fill_event`
- 仅 approved + risk_decision + kill off；**账本差额**纸面成交；费用读 `cost_params`
- CLI：`execution run|list|show`；`schedule` 在 risk 后执行

### 2026-07-27 · 阶段 7：risk_engine

- 迁移 `025`：`risk_decision` / `kill_switch` / `risk_limits`
- CLI：`risk review|kill|status|list|show`；硬规则放行/否决 draft
- Kill Switch（GLOBAL/账户）；`schedule` 审当日 draft

### 2026-07-27 · 阶段 6：portfolio_construct

- 迁移 `024`：`portfolio_target` / `portfolio_target_position`
- CLI：`portfolio build|list|show`；仅 PAPER/LIVE；最近调仓日信号 → 整手 draft
- 剔 `can_buy!=1`/缺价后重归一；`schedule` 在 signal 后构建 LIVE 草稿

### 2026-07-27 · 阶段 5：strategy_registry + signal_prod

- 迁移 `023`：`strategy_version` / `strategy_transition` / `signal_batch` / `signal_prod_weight`
- CLI：`strategy register|promote|retire|list|show`；`signal run|list`
- 生产信号仅 PAPER/LIVE；FACTOR_TOP_N 前一日因子禁前视；DQ 覆盖区间
- `schedule` 增加 LIVE 信号步（非调仓日 skipped）

### 2026-07-27 · 优化补丁：日更资金 + tech 进研究

- `schedule` / `daily --with-alpha`：ALPHA 增加 `stock_flow`（分块），保鲜 `FLOW_NET_5`
- `research_lab`：`TECH_RSI_14` / `TECH_MACD_HIST` / `TECH_MA20_BIAS` 经库读 `processed_tech_indicator_1d`
- `coverage`：扩 news / tech_1d / equity_min

### 2026-07-27 · 分钟 K 15m/60m + 分钟技术指标

- 迁移 `022`：`raw_equity_bar_min` / `processed_equity_bar_min` / `processed_tech_indicator_min`
- ingest：`equity_15m` / `equity_60m`（东财 hist_min_em，回退新浪）；process 用当日 adj_factor
- `tech_indicator --freq 15m|60m`；短窗少标的，不进默认 schedule

### 2026-07-27 · 日线技术指标全部分类（data_process）

- 迁移 `020`/`021`：`processed_tech_indicator_1d` + `category`
- `suite=core`：13 兼容码（日更默认）；`suite=full`：pandas-ta 九类 ~150 函数 / ~250+ 序列
- `--list-tech-catalog` / `--category momentum`；只读 processed OHLCV，不进 ingest
- 默认 Universe（TOP100）；全量请短窗少标的，本机勿 ALL_LISTED

### 2026-07-27 · 编排与运维收尾（阶段 4）

- `schedule --once/--at`：daily → security_master → news/policy/valuation → ALPHA DQ → `ops_alert`
- 迁移 `019`：`ops_alert`；可选 `ASHARE_ALERT_WEBHOOK`
- `coverage`：核心表×月份覆盖度（只读）
- 新闻：标题去重、水位回看 24h、`--symbol-map` 简称回填

### 2026-07-25 · PIT 与数据正确性（阶段 3）

- `018`：`processed_fund_snapshot`（公告日区间 PIT；`fundamental_pit`）
- CORE DQ：`corp_action_adj_check`（除权价交叉，warn）
- Universe：成分 `member_effective_date` 审计；`as_of` 取 `trade_date<=as_of` 最近一期
- 涨跌停：`raw_limit_board` 缺失时价格推导（主板/创业板/ST）
- ALPHA DQ：估值/资金流/新闻轻量规则，不写 `dq_gate`

### 2026-07-25 · 研究闭环（阶段 2）：因子 → IC → FACTOR_TOP_N 回测

- 迁移 `017_research_lab.sql`：`research_factor_value` / `research_run`
- 因子：`MOM_20` / `VAL_PE_PCT` / `FLOW_NET_5`；`--evaluate` 为 t→t+1 RankIC / 5 分位
- 回测：`FACTOR_TOP_N --factor MOM_20 --top-n 20 --rebalance-days 20`（经库读因子，调仓用前一日值）
- 默认 `dq_gate=passed`；模块间不互相 import，只经库交接

### 2026-07-25 · 回测撮合引擎（阶段 1）+ pytest/CI

- `backtest`：通用 `run_target_weights`（T+1 / `can_sell` / 卖出印花税 / 先卖后买）；`EW_HOLD` 改挂新引擎；新增 `EW_REBALANCE --rebalance-days`
- `backend/tests/`：engine / process compute / DQ rules 纯函数单测；GitHub Actions CI
- 开发路线见根目录 `DEVELOPMENT_PLAN.md`

### 2026-07-25 · 个股关系边 + 中标双源（contract / announcement / relation）

- `alpha_relation`：`hot_relate` / `holder_team` / `board_co` → `raw_stock_relation`（迁移 `016`）
- `alpha_contract`：`win_bid` / `major_contract` → `raw_major_contract`（迁移 `015`；源 `stock_zdhtmx_em`）
- `alpha_announcement`：`category_norm` 增 `win_bid` / `major_contract`；巨潮 `searchkey`；与合同表双源交叉

### 2026-07-25 · 新闻官方快讯 + 论坛情绪 + 政策语境

- `alpha_news_monitor` 新增 kind：`news_official`（通讯社 + 财经早餐/财新）、`news_forum`（千股千评/雪球/微博 + 可选百度热搜·投票·千股千评明细）、`news_policy`（政策语境：早餐/财新/EPU + 可选 CCTV/经济日历/财联社政策过滤，带 `policy_tags`/`tone_hint`）
- 迁移 `014_news_sentiment.sql`：`raw_news_media.content_type` / `extra_json`
- CLI：`--media` 子源过滤、`--forum-top-n`、可选 `--universe`
- 法定公告仍在 `alpha_announcement`；本模块服务舆情/情绪/利好利空原料，不阻塞 CORE
- 文档：`backend/data_ingest/README.md`、`alpha_news_monitor/README.md`、`database/schema|migrations/README.md` 已同步

### 2026-07-25 · ingest 工程优化 + 四个增强 kind

- **工程**：`shared/bulk_upsert` 分块 executemany；`shared/akshare_call` 统一重试/降噪；`chunk_date_ranges` + `--chunk-months` + 按日 skip-existing（取代临时月分块脚本）
- **入口**：`python main.py daily --universe TOP100`（交易日增量 CORE→process→DQ；`--with-alpha` 含估值/龙虎榜）；`data_quality --universe`
- **新 kind**（迁移 `013_ingest_enhancements.sql`）：
  - `core_market.board_1d` → `raw_board_bar_1d`（行业/概念板块日线）
  - `alpha_fundamental.valuation` → `raw_valuation_1d`（`stock_value_em` PE/PB/市值）
  - `alpha_fundamental.holder` → `raw_holder_count`（股东户数）
  - `core_ref.restricted_release` → `raw_restricted_release`（限售解禁）
- 仍不新建空模块；接口与 CLI 见各子目录 README

### 2026-07-25 · P0 长窗 CORE：TOP100 2023–2026

- `calendar`：2020-01-01～2026-07-31（~2400 日）
- `TOP100`：`equity_1d`/`adj_factor` 约 **860 交易日/票**（2023-01～2026-07）；指数 000300/000905/000852 同窗
- CLI：`--min-bars` 配合 `--skip-existing` 做长窗增量；大包 upsert 去掉逐行 EXISTS，避免停牌长窗卡死
- `limit` 长窗（>60 日）仅拉 UP/DOWN；短窗仍含强势/炸板等扩展池
- `data_process --p0 --universe TOP100`：processed equity **~85.9k** + index 860
- `data_quality --scope CORE`：**passed**（`dq_7da7af1f279a4151b0c0bd997a35a010`）
- 停牌/涨跌停：改为**按月分块**续跑（全窗一次拉 66 万行再 upsert 会假死）

### 2026-07-25 · 异动 / 龙虎榜席位 / 涨停池扩展

- 新增 `core_market.abnormal_move` → `raw_abnormal_move`（`ak.stock_changes_em` 盘口异动；多为最近交易日快照）
- 新增 `alpha_flow.dragon_tiger_seat` → `raw_dragon_tiger_seat`（`ak.stock_lhb_hyyyb_em` 每日活跃营业部）
- 扩展 `core_market.limit`：除 UP/DOWN 外增加 `STRONG`/`ZBGC`/`PREVIOUS`/`SUB_NEW` 池
- 迁移 `012_market_microstructure.sql`
- 样本入库（`2026-07-01`–`23`）：龙虎榜约 1.8k、营业部约 4.6k、大宗约 1.7k；涨停扩展池约 1.2k；盘口异动约 **9.5k**

### 2026-07-25 · core_market 市场排名（涨跌幅/量额等）

- 新增 `ingest_kind=market_rank` → 表 `raw_market_rank_1d`（迁移 `011_market_rank.sql`）
- 榜型：`PCT_CHG_UP` / `PCT_CHG_DOWN` / `VOLUME` / `AMOUNT` / `TURNOVER` / `HOT`
- 接口：优先本地 `raw_equity_bar_1d` 截面排序；缺截面回退 `ak.stock_zh_a_spot_em()`；人气榜 `ak.stock_hot_rank_em()`（详见 [`core_market/README.md`](./backend/data_ingest/core_market/README.md)）
- CLI：`--top-n`、`--rank-type`、`--prefer-spot`；可选 `--universe` 缩小排名宇宙
- 样本入库：`2026-07-01`–`2026-07-23` 共 **16600** 行（约 17 交易日 × 量额/换手等榜 × top200；首日无昨收故无涨跌幅榜）
- 东财现货/人气接口近期偶发断连；`--prefer-spot` / `HOT` 可在交易时段重试补全
- 量化用途：动量/拥挤度筛选、异常量能、短线热度；建议在 `equity_1d` 之后跑

### 2026-07-25 · 本地只沉淀龙头，其余按需 API

- 策略调整：**不对 6000+ 全市场 bulk 落库**；默认 Universe 改为 `TOP100` + `SECTOR_LEADERS`
- `security_master --p0`：生成 Top100（股本×收盘/股本）与各行业 1 只龙头
- Ingest/文档默认改为 `--universe TOP100`；非龙头用 `--symbol` 按需拉取
- `ALL_LISTED` / `HS300` 仍可选，但不作为默认灌数范围

### 2026-07-24 · Ingest 分块续跑优化

- 新增 `shared/ingest_batching.py`：`chunk_symbols` / `resolve_symbols_from_args` / `should_chunk`
- `core_market`：单 kind（含 `corp_action`）支持分块；`--skip-existing` 对 corp_action 按 `ex_date` 跳过
- `alpha_fundamental`：`--universe` / `--chunked` / `--chunk-size` / `--skip-existing`；`run_p1_chunked`
- `alpha_flow`：`--universe` / 分块；`run_p1_chunked`（northbound + stock_flow 分块）
- 单 chunk 失败不中断后续块，便于 HS300 增量补数

### 2026-07-24 · 首推 GitHub 与主文档

- 初始化 git，推送到 [CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA)（`main`）
- 根 README 扩充为项目总览 + 本更新记录
- `.gitignore`：忽略 `data/`、`_tmp*` 等本地数据与临时文件

### 2026-07-24 · ALPHA 空表补齐与现有模块加深

- **不新建模块**：公告/公司行为/两融/大宗/基本面均在既有域用 `ingest_kind` 补齐
- `core_market.corp_action` 加深：`DIVIDEND` / `BONUS` / `RIGHTS` + 复权因子**变动点**（不再按日灌因子）
- `alpha_flow.margin` 加深：上交所 + **深交所**市场汇总与个股明细（`MARKET_SZSE`）
- 真实入库（样本）：公告约 7k 行；财报/指标；一致预期 EPS；北向资金流；两融；大宗；公司行为含分红/送转

### 2026-07-24 · HS300 CORE 闭环与回测

- 修复 `core_ref` 指数成分字段误匹配（避免全体变成指数代码）
- `core_market` / `data_process` 支持 `--universe`；行情分块 `--chunked` / `--skip-existing`
- HS300 区间日线+复权覆盖 **300/300**；`data_process` → CORE `dq_gate=passed` → `EW_HOLD` 回测
- 回测样本：策略约 +2.48% vs 沪深300 约 -4.66%；建仓覆盖 178/300（100 万等权整手约束，非缺行情）

### 2026-07-24 · 加工 / DQ / Universe / 回测模块落地

- 迁移 `007_data_process`：`processed_equity_bar_1d` / `processed_index_bar_1d` / `process_batch`
- 迁移 `008_data_quality`：`dq_run` / `dq_result` / `dq_gate`
- 迁移 `009_security_master`：`universe_snapshot` + members（`ALL_LISTED` / `HS300` / `HS300_EX_ST`）
- 迁移 `010_backtest`：`cost_params` / `backtest_run` / `backtest_nav` / `backtest_trade`；策略 `EW_HOLD`

### 2026-07-24 及前期 · CORE/ALPHA ingest 与 PG 底座

- 默认存储切换为 PostgreSQL（pgembed）；SQLite 路径弃用
- 迁移 `001`–`006`：公告、参考、行情、基本面、资金流、新闻
- `data_ingest` 域划分：`core_ref` / `core_market` / `alpha_fundamental` / `alpha_flow` / `alpha_announcement` / `alpha_news_monitor`
- CLI 统一入口：`backend/main.py`
- 清理 PG 中 mock 污染数据；坚持真实源优先

---

## 8. 文档索引

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | 强制架构、产消、合入检查 |
| [backend/README.md](./backend/README.md) | 后端模块一览与运行入口 |
| [backend/data_ingest/README.md](./backend/data_ingest/README.md) | ingest 阶段与 kind 清单 |
| [backend/data_ingest/core_market/README.md](./backend/data_ingest/core_market/README.md) | 行情 kinds 与 akshare 接口映射 |
| [database/README.md](./database/README.md) | 迁移与契约 |
| [frontend/README.md](./frontend/README.md) | 前端边界 |

---

## 9. 许可与贡献

内部/私有项目协作时：先开分支，更新「开发更新记录」与相关模块 README，再合入 `main`。  
合入前检查见架构原则 §6。
