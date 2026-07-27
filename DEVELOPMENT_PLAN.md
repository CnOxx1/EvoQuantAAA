# EvoQuantAAA 开发方案（交接给开发 Agent）

> 本文档是一份**可直接执行的开发任务书**。按阶段顺序开发；每个任务给出：背景、涉及文件、当前行为、目标行为、验收标准。
> 执行前请先通读「0. 项目约定」，违反不变量的实现一律返工。

---

## 0. 项目约定（必读，所有任务共同遵守）

### 0.1 环境

- Windows / PowerShell，Python 3.13，仓库根 `C:\Users\guocongli\Desktop\jy\大a`
- 所有 CLI 从 `backend/` 目录运行：`cd backend && python main.py <cmd>`
- 数据库：PostgreSQL（pgembed 嵌入式，自动启动，数据在 `data/pgdata`）；连接统一走 `shared/db.py::get_conn()`（SQL 用 `?` 占位符，内部转 psycopg）。**禁止** SQLite
- 本机是**开发机**：只跑短窗冒烟（几天~1 个月、TOP100 或单票），**禁止**长窗历史回填、禁止 ALL_LISTED（6000+ 股票）bulk

### 0.2 代码结构约定

- 每个模块目录固定形态：`models.py`（dataclass + Literal kind）/ `service.py` / `repository.py` / `selfcheck.py` / `README.md`；参考 `backend/data_process/`
- 写库用 `shared/bulk_upsert.py`；批次经 `data_ingest/ingest_common/batch.py::BatchManager`（ingest 侧）或各自 batch 表
- 外部 HTTP（akshare）统一经 `shared/akshare_call.py::call_with_retry`
- Universe 解析用 `shared/universe_resolve.py`（CLI 传 `--universe TOP100`）
- 新表 = 新迁移：`database/migrations/NNN_<feature>.sql`，当前已到 `031`（strategy_sleeve），**新迁移从 `032` 开始**；不得改已发布迁移；同步更新 `database/migrations/README.md` 与 `database/schema/README.md` 产消表
- 每个模块提供 `python -m <包路径>.selfcheck`：用 mock 数据走通全链路并 assert

### 0.3 量化不变量（违反即返工）

1. **CORE 先于 ALPHA**：ALPHA 失败不得阻塞 CORE 流水线
2. **点时**：策略/因子只能用 `publish_time` / 公告日 / 生效日；**禁止**用 `ingested_at`
3. **幂等**：所有写入可重跑不产生重复行（唯一键 + UPSERT）
4. **回测正确性**：无复权因子/停牌/涨跌停数据的区间不得宣称可回测；DQ gate 未 pass 不得供研究消费
5. **A 股规则**：T+1（当日买入不可卖）、整手 100 股、涨停不可买/跌停不可卖、印花税只收卖出方
6. 模块间**禁止** import 对方内部实现；共享只经 `shared/` 与 `ingest_common/`
7. 完成任务后同步更新对应 README（根 README 的 changelog 顶部追加一条）

### 0.4 已有能力（不要重复造）

| 能力 | 位置 |
| --- | --- |
| 数据获取 40+ kind（行情/复权/停牌/涨跌停/财报/估值/资金/公告/新闻/政策） | `backend/data_ingest/*` |
| 复权 + ret_1d + can_buy/can_sell 掩码 | `backend/data_process/` |
| 9 条 CORE DQ 规则 + dq_gate | `backend/data_quality/` |
| Universe 快照（TOP100 / SECTOR_LEADERS / HS300 等） | `backend/security_master/` |
| EW_HOLD / EW_REBALANCE 回测（T+1/印花税/再平衡） | `backend/backtest/` |
| pytest（engine/compute/rules/research） | `backend/tests/` |
| 基线因子 MOM_20 / VAL_PE_PCT / FLOW_NET_5 + IC 评估 | `backend/research_lab/` |
| 交易日增量流水线 `python main.py daily` | `backend/main.py::cmd_daily` |
| 日更编排 `python main.py schedule --once/--at` | `backend/orchestrator/scheduler.py` |
| 失败告警 `ops_alert` + 可选 webhook | `backend/ops_monitor/notify.py` |
| 覆盖度矩阵 `python main.py coverage` | `backend/ops_monitor/coverage.py` |
| 日线技术指标 `data_process --kind tech_indicator` | `backend/data_process/tech_indicator.py` |
| 分钟 K 15m/60m | `core_market` + `data_process` + `processed_tech_indicator_min` |
| tech 派生研究因子 TECH_* | `backend/research_lab/`（经库读 tech 表） |
| 日更 ALPHA含 stock_flow | `orchestrator/scheduler.py` / `cmd_daily --with-alpha` |
| 策略注册 + 生产信号 | `strategy_registry` / `signal_prod`（迁移 `023`） |
| 目标持仓草稿 | `portfolio_construct`（迁移 `024`） |
| 风控放行/Kill Switch | `risk_engine`（迁移 `025`） |
| 纸面 OMS 事件 | `execution`（迁移 `026`） |
| 账本过账 + T+1 | `ledger`（迁移 `027`） |
| 对外 API 网关 | `api_gateway`（迁移 `028`） |
| 生产硬化 | 差额成交 / 按日幂等 / 账本原子过账（迁移 `029`） |
| 量化正确性 | LIVE 因子日刷 / 现金约束 / 资本配额 / 未复权成交价（迁移 `030`） |
| 策略 sleeve | 同账户持仓按 strategy_version 隔离；执行后即过账；非调仓 hold；回测 lot T+1（迁移 `031`） |
| E2E + console | `python main.py e2e`；`frontend/console` 只读台 |

> **阶段 15（2026-07-27）**：策略 sleeve 持仓；execution 后立即 ledger post；非调仓日 portfolio hold；signal 失败短路；回测 FIFO lot + close 成交；force 有 posting 则禁止。下一优先：晋升质量门 / 残差 pending / 冲击成本。
>
> **阶段 14（2026-07-27）**：量化正确性 Critical：schedule 前刷 LIVE 因子；纸面成交现金约束；同账户资本配额；sizing/成交用未复权 `close`；目标腿 `can_sell`；风控账户合并敞口（迁移 `030`）。
>
> **阶段 13（2026-07-27）**：execution 事件原子提交；security_master 失败跳过交易链；degraded 告警分级；API REQUIRE_TOKEN；Kill 解除可重审。

---

## 阶段 1 · 回测正确性 + 测试基建（最高优先级）

### 任务 1.1 通用撮合引擎（T+1 / can_sell / 印花税 / 再平衡）

**背景**：现引擎 `backend/backtest/engine.py::run_ew_hold` 只有首日买入建仓；`buy_dates`（第 54 行起）记录后从未参与判断，`can_sell` 从未读取，`CostParams.stamp_tax_rate`（`backend/backtest/models.py` 第 14 行）从未计入。

**涉及文件**：`backend/backtest/engine.py`、`models.py`、`service.py`、`selfcheck.py`、`backend/main.py`（backtest 子命令）

**目标行为**：

1. 新增通用日频撮合函数（建议 `run_target_weights`）：
   - 输入：`bars`（processed 日线，含 `can_buy`/`can_sell`/`adj_close`）、逐日目标权重 `dict[date, dict[symbol, weight]]`、`CostParams`、`initial_cash`
   - 每个调仓日：目标权重 → 目标市值 → 与当前持仓差额 → 订单
   - **卖出**：`can_sell==1` 且 `buy_date < 当日`（T+1）才可卖；成本 = 佣金 + **印花税**（`amount * stamp_tax_rate`，仅卖出）+ 滑点（卖出价 `adj_close * (1 - slippage_rate)`）
   - **买入**：`can_buy==1`；整手（`lot_size`）向下取整；成本 = 佣金 + 滑点（买入价 `* (1 + slippage_rate)`）
   - 先卖后买（卖出回笼资金再买入）；现金不足时按比例缩量，不允许透支
   - 持仓逐笔记录 `buy_date`（同一 symbol 分批买入的，卖出按最早批次判定 T+1 即可，无需完整 FIFO 分层）
2. `EW_HOLD` 改为基于新引擎的特例（首日等权、之后不动），输出与现有 `EngineOutput` 兼容
3. 新增 `StrategyCode`：`"EW_REBALANCE"`（等权 + `--rebalance-days N` 定期再平衡），作为新引擎的验证策略
4. `main.py backtest` 增加 `--rebalance-days`（默认 0=不再平衡）

**验收标准**：

- 构造用例：某标的持仓期间某日 `can_sell=0`（跌停/停牌），当日卖单必须不成交并顺延
- 构造用例：调仓日买入的标的当日不得卖出
- 卖出成交明细 `cost` 字段 = 佣金 + 印花税，且印花税只出现在 SELL
- `python main.py backtest --strategy EW_REBALANCE --rebalance-days 20 --universe TOP100 --start 2026-06-01 --end 2026-07-23 --factor-type qfq` 跑通，NAV 连续无跳变
- `python -m backtest.selfcheck` 通过（mock 数据覆盖上述用例）

### 任务 1.2 pytest 测试基建

**背景**：全仓库无 `tests/`，复权/掩码/撮合是"算错不报错"的逻辑，必须有单测。

**涉及文件**：新建 `backend/tests/`（`test_backtest_engine.py`、`test_process_compute.py`、`test_dq_rules.py`、`conftest.py`）；`backend/requirements.txt` 加 `pytest`

**要求**：

- 纯函数直测，**不连数据库**（`build_equity_processed_rows`、`run_target_weights`、`run_core_rules` 都是纯函数，直接喂 dict/list）
- 必测用例（最少）：
  - compute：复权乘法正确；ret_1d 首日为 None；停牌日 `can_buy=can_sell=0`；涨停日 `can_buy=0, can_sell=1`；跌停日反之；缺因子跳过并计数
  - engine：T+1 卖出拦截；跌停日卖出拦截；印花税只收卖方；整手取整；现金不透支；再平衡后权重接近目标
  - dq：9 条规则各构造一组 pass 和一组 fail
- `cd backend && python -m pytest tests/ -q` 全绿，用时 < 60s

### 任务 1.3 GitHub Actions CI

**涉及文件**：新建 `.github/workflows/ci.yml`

**要求**：push/PR 触发；Python 3.13；`pip install -r backend/requirements.txt`；跑 `pytest backend/tests/ -q`。不需要数据库服务（1.2 已保证不连库）。**注意**：`data/pgdata/` 不能进 CI 上下文，顺手在 `.gitignore` 里补 `data/pgdata/`（如果尚未忽略，先 `git rm -r --cached data/pgdata`）。

---

## 阶段 2 · 最小研究闭环（research_lab）

> 目标：让已采集的数据第一次产生研究价值。**不要做通用因子框架**，先跑通 3 个基线因子。

### 任务 2.1 因子计算 + 落库

**背景**：`backend/research_lab/` 只有 README。数据源：`processed_equity_bar_1d`（复权价）、`raw_valuation_1d`（PE/PB）、`raw_money_flow`（资金流）。

**涉及文件**：新建 `backend/research_lab/{models,repository,factors,service,selfcheck}.py`；迁移 `database/migrations/017_research_lab.sql`；`main.py` 加 `research` 子命令

**表设计（017 迁移）**：

```sql
CREATE TABLE IF NOT EXISTS research_factor_value (
  factor_code   TEXT NOT NULL,          -- MOM_20 / VAL_PE_PCT / FLOW_NET_5
  symbol        TEXT NOT NULL,
  trade_date    DATE NOT NULL,
  value         DOUBLE PRECISION,
  universe_code TEXT NOT NULL,
  run_id        TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (factor_code, symbol, trade_date, universe_code)
);
CREATE TABLE IF NOT EXISTS research_run (
  run_id TEXT PRIMARY KEY, factor_code TEXT, universe_code TEXT,
  start_date DATE, end_date DATE, status TEXT, meta_json TEXT, created_at TIMESTAMPTZ
);
```

**三个基线因子**：

| factor_code | 定义 | 数据 |
| --- | --- | --- |
| `MOM_20` | 20 日动量：`adj_close_t / adj_close_{t-20} - 1` | processed 日线 |
| `VAL_PE_PCT` | PE-TTM 截面分位（当日 Universe 内 percent rank，PE≤0 归最差档） | `raw_valuation_1d` |
| `FLOW_NET_5` | 近 5 日主力净流入之和 / 近 5 日成交额之和 | `raw_money_flow` + 日线 |

**CLI**：`python main.py research --factor MOM_20 --universe TOP100 --start 2026-01-01 --end 2026-07-23`

**验收**：三个因子在本地已有数据区间（TOP100，2023 起有日线；估值/资金流按实际覆盖）落库成功；重复跑幂等；`python -m research_lab.selfcheck` 用 mock 行情通过。

### 任务 2.2 因子评估（IC / 分层）

**涉及文件**：`backend/research_lab/evaluate.py`；`main.py research --evaluate`

**要求**：

- 对指定 factor_code：逐日截面 Spearman RankIC（因子值 vs 次日 `ret_1d`，**用 t 日因子对 t+1 日收益**，严禁同日）；输出 IC 均值 / ICIR / 胜率
- 5 分位分层：逐日按因子排序分 5 组，等权组合次日收益累积成净值；输出各层年化收益与多空（Q5-Q1）收益
- 结果写 `research_run.meta_json`，同时控制台打印摘要表
- **前置**：评估区间必须 `dq_gate=passed`（复用 `data_quality` 的 gate 查询），否则 exit 2

**验收**：`python main.py research --factor MOM_20 --evaluate --universe TOP100 --start 2023-01-01 --end 2026-07-23` 输出 IC/分层报告（本机已有该区间 processed 数据）。

### 任务 2.3 因子 → 回测对接

**要求**：`main.py backtest` 新增 `--strategy FACTOR_TOP_N --factor MOM_20 --top-n 20 --rebalance-days 20`：每个调仓日取因子值 top N 等权为目标权重，走任务 1.1 的通用引擎。因子值取**调仓日前一交易日**的值（避免用当日收盘信息当日交易）。

**验收**：跑通 TOP100 / 2023–2026 区间；输出与 EW_HOLD 相同结构的 NAV/成交记录；换仓日成交明细可见卖出与印花税。

---

## 阶段 3 · PIT 与数据正确性

### 任务 3.1 基本面 PIT 可见性

**背景**：`raw_fund_statement` / `raw_fund_indicator` 有公告日字段，但加工端没有"某日可见的最新报告期"视图，直接 join 报告期会引入前视偏差。

**要求**：在 `data_process` 新增 kind `fundamental_pit`（迁移 `018`）：生成 `processed_fund_snapshot(symbol, trade_date, report_period, publish_date, 核心科目...)`——对每个交易日取 `publish_date <= trade_date` 的最新报告期。逐日全展开数据量大，可按「发布事件区间」存（`valid_from = publish_date`, `valid_to = 下一次发布前一日`），研究端按区间 join。

**验收**：单测覆盖「公告日前不可见、公告日起可见、更正报告覆盖旧值」三个用例；selfcheck 通过。

### 任务 3.2 除权交叉校验（新增 DQ 规则）

**要求**：`data_quality/rules.py` 新增 warn 级规则 `corp_action_adj_check`：对 `raw_corp_action` 中每个除权除息日，校验 `processed_equity_bar_1d` 当日未复权 close 跳空与分红送转推算的理论除权价偏差 ≤ 2%（数据缺失则 skip 不 fail）。纳入 `run_core_rules` 输出。

**验收**：单测：构造 10 送 10 案例通过、错误因子案例告警；对本地 TOP100 真实数据跑一次 `python main.py data_quality --scope CORE --universe TOP100 --start 2024-01-01 --end 2026-07-23` 查看告警明细合理。

### 任务 3.3 指数成分历史回放

**背景**：`security_master` 的 HS300 快照取"最近成分日"，历史日期的快照会用今天的成分。

**要求**：`raw_index_member` 已按 (index, effective_date) 落库多期成分。修改 `SecurityMasterRepository`：`as_of` 日取 `effective_date <= as_of` 的**最近一期**成分（而非全表最新）。若本地只有一期成分数据，功能仍正确（回退该期），但在快照 meta 里记录 `member_effective_date` 以便审计。

**验收**：单测：两期成分数据下，`as_of` 落在两期之间时取旧一期。

### 任务 3.4 历史涨跌停标志从价格推导

**背景**：东财涨跌停池接口（`stock_zt_pool_*_em`）只能取最近约 30 个交易日；本地 `raw_limit_board` 仅覆盖 2026-07 起，而 `raw_suspend` 已有 2023 至今全量。因此 2023–2025 的 `can_buy`/`can_sell` 掩码缺涨跌停信息，无法靠回填解决。

**要求**：在 `data_process` 的掩码构建阶段（`compute.py::build_equity_processed_rows` 上游，`service.py` 组装 `limit_up`/`limit_down` 集合处）增加**价格推导回退**：当 (symbol, trade_date) 不在 `raw_limit_board` 时，用未复权 close 与前收比较判断——主板 ±10%、创业板/科创板（30/68 开头）±20%、ST ±5%，涨跌幅达到阈值（容差 0.2%）即标记 limit_up/limit_down。推导来源写入行内新字段或沿用现有字段但在 `source` 标注 `derived`。ST 状态用 `raw_special_treat` 点时判断。

**验收**：单测覆盖主板/创业板/ST 三种阈值与非涨停日；对 2024 年任一月重跑 `data_process --p0`，抽查已知涨停样本（如触及 +10% 的日线）`can_buy=0`。

### 任务 3.5 ALPHA 数据 DQ（轻量）

**要求**：`data_quality` 新增 `--scope ALPHA`（不进 dq_gate，仅出报告）：对 `raw_valuation_1d` / `raw_money_flow` / `raw_news_media` 各 2–3 条规则——空值率阈值、(symbol, date) 重复、日期断档、新闻 `publish_time` 不得晚于 `ingested_at`。

**验收**：`python main.py data_quality --scope ALPHA --start 2026-07-01 --end 2026-07-23` 输出报告；不影响 CORE gate。

---

## 阶段 4 · 编排、运维与数据层收尾

### 任务 4.1 orchestrator 最小实现

**要求**：不引 Airflow。`backend/orchestrator/scheduler.py` + `main.py schedule` 命令：内置任务序列 = `daily`（已存在）→ `security_master 快照日更` → ALPHA 增量（news/policy/valuation）→ ALPHA DQ 报告。支持 `--once`（跑一轮退出，供外部 cron/计划任务调用）与 `--at HH:MM`（进程内定时，用 stdlib，勿加重依赖）。任务间只传 ID，失败记录并继续下一任务（CORE 失败除外，CORE 失败中止本轮）。

**验收**：`python main.py schedule --once` 在开市日完整跑一轮；非开市日快速跳过；exit code 正确。

### 任务 4.2 失败告警（ops_monitor 最小实现）

**要求**：`backend/ops_monitor/notify.py`：汇总当轮 `ingest_batch`/`process_batch`/`dq_run` 的 failed 记录，写 `ops_alert` 表（迁移与 4.1 合并为 `019`）并打印醒目摘要；预留 webhook 环境变量 `ASHARE_ALERT_WEBHOOK`（有值则 POST JSON，无值只落库）。接入 4.1 每轮末尾。

### 任务 4.3 数据覆盖度命令

**要求**：`main.py coverage --universe TOP100 --start 2023-01-01 --end 2026-07-23`：输出矩阵——每个核心表（equity_1d/adj_factor/suspend/limit/index_1d/valuation/money_flow）× 月份的行数与缺口月；用于回答「哪些区间可研究」。只读查询，不写库。

### 任务 4.4 新闻去重 + 水位回看

**要求**：
1. `alpha_news_monitor` 入库前对同批次 + 近 24h 已入库记录做标题规范化去重（去空白/标点后前 40 字 hash 相同 → 视为重复，保留最早 `publish_time`，重复源记入 `extra_json.dup_sources`）
2. 水位线读取时回看 24h（`since = watermark - 24h`），配合幂等 UPSERT 吸收源端补发
3. `news_*` 增加可选 `--symbol-map`：标题中包含股票简称时回填 `symbol`（简称表来自 `raw_security_listing`）

**验收**：selfcheck 构造重复标题用例；真实 `news_official` 连跑两次第二次 `inserted≈0`。

---

## 执行顺序与提交约定

- 严格按 1.1 → 1.2 → 1.3 → 2.1 → … 顺序；每个任务一个 commit（格式与现有历史一致：英文祈使句一行）
- 每个任务完成 = 代码 + 单测/selfcheck + README 同步 + 冒烟命令截图/输出贴 PR 或回复
- 不确定的设计决策：优先选择**最简单且不违反 0.3 不变量**的方案，并在代码注释与回复中说明
- **明确不做**（阶段 10 仍范围外）：实盘柜台 / 完整 frontend UI、Tick 数据、机器学习因子、多数据源冗余

---

## 阶段 5 · 研究→生产隔离（strategy_registry + signal_prod）

### 任务 5.1 strategy_registry

**要求**：迁移 `023` 建 `strategy_version` / `strategy_transition`；CLI `strategy register|promote|retire|list|show`；状态机 DRAFT→BACKTESTED→PAPER→LIVE（可 RETIRED）；晋升 BACKTESTED 需 committed `backtest_run`；同 code 至多一 LIVE。

### 任务 5.2 signal_prod

**要求**：仅 PAPER/LIVE；读库内 `research_factor_value` 生成 FACTOR_TOP_N 目标权重（前一日因子，禁前视）；写 `signal_batch` / `signal_prod_weight`；DQ 覆盖区间 passed；`schedule` 日更跑 LIVE（非调仓日 skipped）。

**验收**：register→promote→`signal run` 落库；selfcheck + pytest；README/schema 同步。

---

## 阶段 6 · 组合草稿（portfolio_construct）

### 任务 6.1 portfolio_construct

**要求**：迁移 `024` 建 `portfolio_target` / `portfolio_target_position`；仅 PAPER/LIVE；读 `signal_prod_weight`（as_of 及之前最近调仓日）；剔 `can_buy!=1`/缺价后重归一；按 `cost_params.lot_size` 整手下取；写 `status=draft`；CLI `portfolio build|list|show`；`schedule` 在 signal 后跑 LIVE。

**验收**：对已有 LIVE 信号 `portfolio build --as-of` 出草稿；selfcheck/pytest；文档同步。

---

## 阶段 7 · 风控关卡（risk_engine）

### 任务 7.1 risk_engine

**要求**：迁移 `025` 建 `risk_decision` / `kill_switch` / `risk_limits`；硬规则（Kill Switch、单票权重、只数、敞口、can_buy、整手）；CLI `risk review|kill|status|list|show`；通过则 `portfolio_target.status=approved`，否则 `rejected`；`schedule` 在 portfolio 后审当日 draft。

**验收**：draft 可放行；Kill Switch on 必否决；selfcheck/pytest；文档同步。

---

## 阶段 8 · 纸面执行（execution）

### 任务 8.1 execution

**要求**：迁移 `026` 建 `execution_run` / `order_event` / `fill_event`；仅 `approved` + 最新 `risk_decision=approved` + kill off；paper 适配器按空仓→目标生成 BUY 并即时成交；费用读 `cost_params`；成功后 portfolio→`executed`；CLI `execution run|list|show`；`schedule` 在 risk 后跑 approved。

**验收**：approved 组合可 committed；kill on / 非 approved → blocked；selfcheck/pytest；文档同步。

---

## 阶段 9 · 账本过账（ledger）

### 任务 9.1 ledger

**要求**：迁移 `027` 建账户/过账/分录/余额/批次表；消费 committed `fill_event`；BUY 扣现金建 lot，SELL 校验 T+1 FIFO；同一 execution 幂等；CLI `ledger ensure|post|show|sellable|list`；`schedule` 在 execution 后 `post --unposted`。

**验收**：对已有 paper execution 过账成功；同日卖出在投影单测中被拒；文档同步。

---

## 阶段 10 · 对外网关（api_gateway）

### 任务 10.1 api_gateway

**要求**：迁移 `028` 建 `api_audit_log`；FastAPI `/v1` 查询（strategies/portfolios/risk/executions/ledger/alerts）+ 写（promote / kill / review）；可选 `ASHARE_API_TOKEN`；CLI `gateway`；selfcheck/pytest；README 同步。

**验收**：`/health` 与 `/v1/strategies` 可通；写操作落审计；文档同步。

---

## 阶段 11 · 生产链路硬化

### 任务 11.1 幂等 / 差额 / 原子过账

**要求**：迁移 `029`；execution 读 ledger 持仓做差额+T+1 可卖；portfolio 同日活跃幂等 + 默认账本 NAV + 仅 committed 信号；ledger 分录与 committed 同事务；schedule 交易步骤失败 → `degraded`；ingest `timeutil`/`_parse` 迁 `shared` / `ingest_common`。

**验收**：pytest 全绿；重跑 schedule 不叠加空仓全买；文档同步。

---

## 阶段 12 · E2E 回归 + 最小前端

### 任务 12.1 e2e + console

**要求**：`python main.py e2e` 自备种子跑通 register→…→ledger→API，并断言组合/执行/过账幂等；`frontend/console` 静态只读页对接 gateway（CORS）；文档同步。

**验收**：`e2e` exit 0；console 可拉 `/v1/strategies` 与 kill/ledger。

---

## 阶段 13 · 编排与执行硬化补丁

### 任务 13.1 atomic exec + sm gate + alerts

**要求**：execution `commit_execution_atomic`；`security_master` 失败跳过 signal→ledger 并 `degraded`；`notify_round` 对 failed/degraded 分 severity；`ASHARE_API_REQUIRE_TOKEN`；Kill 解除后可重审曾被 Kill 否决的组合；文档同步。

**验收**：pytest 全绿；README 说明与行为一致。

---

## 阶段 14 · 量化正确性 Critical

### 任务 14.1 factor refresh / cash / capital / close / can_sell

**要求**：
1. `schedule` 在 `signal_live` 前按 LIVE 策略刷新 `research_factor_value`；失败则跳过交易链并 `degraded`
2. 纸面成交投影现金：先卖后买，不足则 `insufficient_cash` / `clamped_cash`
3. 同账户多策略经 `strategy_capital_alloc` 切分 NAV（缺省等权）
4. sizing / 成交价优先未复权 `close`（缺再退 `adj_close`）
5. `portfolio_target_position.can_sell` 落库；风控合并同账户同日敞口

**验收**：迁移 `030` 已应用；pytest 含现金约束与账户合并敞口；相关 README / 任务书同步。

---

## 阶段 15 · 策略 sleeve 与回测对齐

### 任务 15.1 sleeve / post-after-exec / hold / lot T+1

**要求**：
1. `ledger_sleeve_position` + `ledger_lot.strategy_version`；execution 差额仅对本策略 sleeve
2. `execution run` 每个 committed 后立即 `ledger post`（同日多组合不再共享未过账快照）
3. live `portfolio build`：`require_signal_as_of` — 非调仓日 hold skipped
4. schedule：`signal_live` failed 短路后续交易步
5. 回测：FIFO lot T+1（加仓不合并 buy_date）；成交价优先 `close`
6. 已有 posting 的 portfolio 禁止 `--force` 重跑

**验收**：迁移 `031`；pytest 全绿；README 同步。

## 汇总清单

| 阶段 | 任务 | 产出 |
| --- | --- | --- |
| 1 | 1.1 通用撮合（T+1/can_sell/印花税/再平衡） | 可信回测引擎 |
| 1 | 1.2 pytest（engine/compute/rules） | `backend/tests/` 全绿 |
| 1 | 1.3 CI + .gitignore 修复 | Actions 绿 |
| 2 | 2.1 三个基线因子落库 | `research_factor_value` |
| 2 | 2.2 IC/分层评估 | 因子报告 |
| 2 | 2.3 FACTOR_TOP_N 策略回测 | 数据→因子→回测闭环 |
| 3 | 3.1 基本面 PIT | `processed_fund_snapshot` |
| 3 | 3.2 除权交叉校验 | DQ 新规则 |
| 3 | 3.3 成分历史回放 | 快照点时正确 |
| 3 | 3.4 涨跌停价格推导回退 | 2023–2025 掩码完整 |
| 3 | 3.5 ALPHA DQ | 质量报告 |
| 4 | 4.1 schedule 命令 | 无人值守日更 |
| 4 | 4.2 失败告警 | `ops_alert` |
| 4 | 4.3 coverage 命令 | 覆盖度矩阵 |
| 4 | 4.4 新闻去重/水位回看 | 舆情数据可用性 |
| 5 | 5.1 strategy_registry | 版本状态机 |
| 5 | 5.2 signal_prod | 生产权重 + schedule LIVE |
| 6 | 6.1 portfolio_construct | 目标持仓 draft + schedule LIVE |
| 7 | 7.1 risk_engine | 硬规则放行 + Kill Switch |
| 8 | 8.1 execution | 纸面 order/fill 事件 |
| 9 | 9.1 ledger | fill 过账 + T+1 可卖 |
| 10 | 10.1 api_gateway | FastAPI 查询/Kill/晋升 |
| 11 | 11.1 prod hardening | 差额成交 / 幂等 / 原子过账 / degraded |
| 12 | 12.1 e2e + console | 短窗 E2E + 只读台 |
| 13 | 13.1 exec/sm/alerts patch | 原子执行 / SM 门禁 / 告警分级 |
| 14 | 14.1 quant correctness | 因子日刷 / 现金 / 配额 / close / 账户敞口 |
| 15 | 15.1 sleeve + hold + lot T+1 | 策略持仓隔离 / 即过账 / 非调仓 hold / 回测对齐 |
