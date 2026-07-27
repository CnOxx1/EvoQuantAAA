# EvoQuantAAA · A 股量化系统

> **控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。**

| | |
| --- | --- |
| 远程 | [CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA) |
| 架构原则（强制） | [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) |
| 分阶段任务书 | [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) |
| 表产消契约 | [database/schema/README.md](./database/schema/README.md) |
| 后端 CLI | [backend/README.md](./backend/README.md) |

**CLI 一律在 `backend/` 下执行**：`cd backend && python main.py <cmd>`。

---

## 目录

1. [项目是什么](#1-项目是什么)
2. [当前完成度](#2-当前完成度)
3. [仓库结构](#3-仓库结构)
4. [主链路与日更](#4-主链路与日更)
5. [模块地图](#5-模块地图)
6. [量化不变量（必守）](#6-量化不变量必守)
7. [研究 → 生产生命周期](#7-研究--生产生命周期)
8. [数据与存储](#8-数据与存储)
9. [环境与配置](#9-环境与配置)
10. [快速开始](#10-快速开始)
11. [常用命令速查](#11-常用命令速查)
12. [协作约定（多 AI Agent）](#12-协作约定多-ai-agent)
13. [已知限制与数据债](#13-已知限制与数据债)
14. [下一优先](#14-下一优先)
15. [开发更新记录](#15-开发更新记录)
16. [文档索引](#16-文档索引)

---

## 1. 项目是什么

面向 **A 股实盘约束** 的量化研究 + **纸面生产** 系统：从外部取数，经加工与质量门，进入 Universe / 因子 / 回测；策略经注册与质量门晋升后，日更生成生产信号 → 组合草稿 → 风控 → 纸面 OMS → 账本过账；对外经 API，运维经编排与告警。

| 目标 | 说明 |
| --- | --- |
| 真相在库 | 跨模块业务数据落库；下游只读已提交数据与 ID，禁止传大对象 |
| CORE 先于 ALPHA | 先复权收益与可成交约束，再扩基本面 / 资金 / 文本；ALPHA 失败不挡 CORE |
| A 股可回测 / 可纸面成交 | T+1、整手、涨跌停掩码、印花税、未复权成交价、策略 sleeve |
| 研究与生产隔离 | 实验不可直连执行；须 `strategy_registry` 晋升 + 质量门 |
| 多 Agent 可协作 | 一 Agent 一模块；只读对方 README 与 `database/` 契约 |

**非目标（当前）**：Tick/L2、宏观全量、ML 因子框架、真实券商柜台直连、前端完整产品化（仅 [`frontend/console`](./frontend/console/README.md) 只读台）。

---

## 2. 当前完成度

**状态（2026-07-27）**：阶段 **1–16** 已落地；迁移 **`001`–`032`**。纸面全链路可跑；晋升含质量门；**未接**真实柜台。

| 能力域 | 状态 | 说明 |
| --- | --- | --- |
| CORE 取数 / 加工 / DQ | ✅ | 日线复权、停牌涨跌停、`can_buy`/`can_sell`、CORE gate |
| ALPHA 取数 | ✅ | 可插拔；失败不挡 CORE |
| Universe | ✅ | TOP100 / SECTOR_LEADERS / 指数成分等日快照 |
| 研究因子 + IC | ✅ | MOM / VAL / FLOW / TECH_*；`research_run.meta_json.report` |
| 回测引擎 | ✅ | EW_* / FACTOR_TOP_N；FIFO lot T+1；`close` 成交 |
| 策略晋升 + 质量门 | ✅ | DRAFT→…→LIVE；IC/DD/样本窗（`032`） |
| 生产信号 / 组合 / 风控 | ✅ | PAPER/LIVE；非调仓 hold；Kill Switch；账户合并敞口 |
| 纸面 OMS + 账本 | ✅ | 差额成交；sleeve；现金约束；执行后可即时过账 |
| 日更编排 / 告警 | ✅ | `schedule`；`factor_refresh`；`ops_alert` |
| API + E2E + console | ✅ | `/v1`；`python main.py e2e`；只读台 |
| 实盘柜台 | ❌ | 仅 paper adapter |
| 残差 pending / 冲击成本 / 行业·ADV 风控 | ⏳ | 阶段 17+ |

**开发机约束**：只做短窗冒烟（几天～约 1 个月、TOP100 或单票）。**禁止** ALL_LISTED（6000+）长窗 bulk、禁止本机长历史回填。

---

## 3. 仓库结构

```text
EvoQuantAAA
├── README.md                      # 本文件（入口手册）
├── ARCHITECTURE_PRINCIPLES.md     # 强制架构与合入清单
├── DEVELOPMENT_PLAN.md            # 分阶段任务书（现至 16）
├── docker-compose.yml
├── backend/                       # 业务实现 + 统一 CLI
│   ├── main.py                    # python main.py …
│   ├── shared/                    # DB / UPSERT / akshare / universe 解析
│   ├── data_ingest/               # CORE + ALPHA 取数
│   ├── data_process/ data_quality/ security_master/
│   ├── research_lab/ backtest/
│   ├── strategy_registry/ signal_prod/
│   ├── portfolio_construct/ risk_engine/ execution/ ledger/
│   ├── orchestrator/ ops_monitor/ api_gateway/
│   ├── e2e/ tests/
├── database/
│   ├── migrations/                # 001–032（新文件从 033 起）
│   ├── schema/                    # 产消登记（权威）
│   └── seeds/
├── frontend/
│   └── console/                   # 只读运维台（经 api_gateway）
└── scripts/
```

本地 `data/`（含 pgembed `data/pgdata`）**不入库**（见 `.gitignore`）。

每个业务模块固定形态：`models.py` / `service.py` / `repository.py` / `selfcheck.py` / `README.md`。

---

## 4. 主链路与日更

### 4.1 数据与生产主链

```text
外部源 (akshare 等)
  → data_ingest          raw_* + ingest_batch
  → data_process         processed_*（复权 / can_buy|can_sell / tech）
  → data_quality         dq_gate（CORE 未 pass 不得进研究/回测默认路径）
  → security_master      universe_snapshot
  → research_lab         research_factor_value + research_run（含 IC 报告）
  → backtest             backtest_run / nav / trade
  → strategy_registry    登记 / 晋升（质量门）→ strategy_version
  → signal_prod          signal_prod_weight（仅 PAPER/LIVE）
  → portfolio_construct  portfolio_target（draft；非调仓日 hold）
  → risk_engine          risk_decision / kill_switch
  → execution            order_event / fill_event（paper；sleeve 差额）
  → ledger               ledger_posting + lot + sleeve_position
  → api_gateway / ops_monitor
```

跨模块交接只传 ID：`batch_id` / `run_id` / `strategy_version` / `portfolio_id` / `execution_id` / `posting_id` 等。

### 4.2 日更编排（`schedule`）

```text
daily(CORE±ALPHA)
  → security_master 日快照
  → ALPHA 增量（失败可 degraded，不挡 CORE）
  → factor_refresh          # LIVE 策略因子日刷；失败则跳过交易链
  → signal_live
  → portfolio → risk → execution(+ CLI 即时 ledger post) → ledger 兜底
```

- `security_master` 失败：跳过后续交易链  
- `signal_live` failed：短路后续交易步  
- 非开市日：`schedule --once` 整体可 `skipped`  
- 告警：`ops_alert`（可选 webhook）

---

## 5. 模块地图

| 域 | 模块 | 路径 | 要点 | README |
| --- | --- | --- | --- | --- |
| 契约 | database | `database/` | 迁移 001–032；产消表 | [link](./database/README.md) |
| 共享 | shared | `backend/shared/` | `get_conn`、UPSERT、akshare、universe | [link](./backend/shared/README.md) |
| CORE | core_ref / core_market | `backend/data_ingest/core_*` | 日历上市行业；日线/复权/停牌/涨跌停/指数；分钟 K | [ingest](./backend/data_ingest/README.md) |
| ALPHA | announcement…relation | `backend/data_ingest/alpha_*` | 财报估值资金公告新闻合同关系 | 同上 |
| 加工 | data_process | `backend/data_process/` | 复权、收益、可买可卖、tech | [link](./backend/data_process/README.md) |
| 质量 | data_quality | `backend/data_quality/` | CORE/ALPHA 规则 + gate | [link](./backend/data_quality/README.md) |
| 证券池 | security_master | `backend/security_master/` | Universe 日快照 | [link](./backend/security_master/README.md) |
| 研究 | research_lab | `backend/research_lab/` | 基线+TECH 因子；IC/分层 | [link](./backend/research_lab/README.md) |
| 回测 | backtest | `backend/backtest/` | A 股撮合；EW_* / FACTOR_TOP_N | [link](./backend/backtest/README.md) |
| 注册 | strategy_registry | `backend/strategy_registry/` | 状态机 + 晋升质量门 | [link](./backend/strategy_registry/README.md) |
| 信号 | signal_prod | `backend/signal_prod/` | 生产权重（防未来函数） | [link](./backend/signal_prod/README.md) |
| 组合 | portfolio_construct | `backend/portfolio_construct/` | 目标持仓草稿；资本配额 | [link](./backend/portfolio_construct/README.md) |
| 风控 | risk_engine | `backend/risk_engine/` | 硬限额、Kill、账户合并敞口 | [link](./backend/risk_engine/README.md) |
| 执行 | execution | `backend/execution/` | 纸面 OMS；sleeve 差额；现金投影 | [link](./backend/execution/README.md) |
| 账本 | ledger | `backend/ledger/` | 过账、T+1 lot、sleeve | [link](./backend/ledger/README.md) |
| 编排 | orchestrator | `backend/orchestrator/` | schedule / daily | [link](./backend/orchestrator/README.md) |
| 运维 | ops_monitor | `backend/ops_monitor/` | 告警、coverage | [link](./backend/ops_monitor/README.md) |
| API | api_gateway | `backend/api_gateway/` | `/v1` BFF | [link](./backend/api_gateway/README.md) |
| 回归 | e2e / tests | `backend/e2e/` `backend/tests/` | 短窗 E2E；pytest | [e2e](./backend/e2e/README.md) |
| 前端 | console | `frontend/console/` | 只读台 | [frontend](./frontend/README.md) |

废弃目录名（勿用）：`research_factor`、`portfolio_risk`。

---

## 6. 量化不变量（必守）

完整条文见 [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) 与任务书 §0.3。摘要：

1. **CORE 先于 ALPHA**；ALPHA 失败不得阻塞 CORE  
2. **点时**：只用 `publish_time` / 公告日 / 生效日 / `trade_date`；禁止用 `ingested_at` 当可知时刻  
3. **幂等**：唯一键 + UPSERT；可重跑不造重复真相  
4. **DQ 门禁**：默认研究/回测消费前 CORE gate 须 pass  
5. **研究/生产隔离**：实验不得进 `execution`；须晋升；BACKTESTED/PAPER/LIVE 过质量门（或显式 `--skip-gates` + reason）  
6. **A 股规则**：T+1、整手 100、涨停不可买 / 跌停停牌不可卖、印花税仅卖出  
7. **OMS ≠ 账本**：execution 写事件；ledger 过账与可卖  
8. **多策略同账户**：现金共享，持仓按 `strategy_version` sleeve 隔离  
9. **成交价**：纸面 sizing/fill 与回测优先未复权 `close`；复权价用于收益/因子  
10. **模块边界**：禁止业务模块互相 import 内部实现；共享只经 `shared/` / `ingest_common/`

---

## 7. 研究 → 生产生命周期

```text
research 计算/评估
  → backtest（committed backtest_run）
  → strategy register（DRAFT，建议带 research_run_id）
  → promote BACKTESTED（须 --backtest-run）
  → promote PAPER
  → promote LIVE          # 默认要求：样本窗≥20 日、DD 上限、research IC 报告
  → signal / schedule 日更
```

状态机：`DRAFT → BACKTESTED → PAPER → LIVE`；任意非终态 → `RETIRED`；`LIVE → PAPER` 可降级。同 `strategy_code` 至多一个 LIVE（晋升默认自动 retire 旧 LIVE）。

**质量门（迁移 `032`，默认 `v1_default`）**

| 目标状态 | 主要检查 |
| --- | --- |
| BACKTESTED | committed 回测；DD/收益/窗宽松 |
| PAPER | 略严；不强制 IC |
| LIVE | 日历窗 ≥20；`max_drawdown≤0.40`；须 `research_run.meta_json.report`（ic_mean / ic_days 等） |

未通过 → 拒绝晋升，写入 `promotion_gate_result`。应急：`--skip-gates --reason …`（审计 `skipped=1`）。  
阈值版本：表 `promotion_gate_params` 或环境变量 `ASHARE_PROMOTION_GATE_VERSION`。  
细节：[backend/strategy_registry/README.md](./backend/strategy_registry/README.md)。

当前策略 kind：`FACTOR_TOP_N`（`factor_code` / `top_n` / `rebalance_days` / `universe_code`）。

---

## 8. 数据与存储

| 项 | 说明 |
| --- | --- |
| 引擎 | **仅 PostgreSQL**（默认 pgembed → `data/pgdata`；或 `ASHARE_DATABASE_URL`） |
| 禁止 | SQLite 作为生产/开发主路径 |
| 迁移 | `python main.py migrate`；已发布脚本不改写；新文件从 **`033`** 起 |
| 批次/运行 | `ingest_batch`、`process_batch`、`dq_gate`、`research_run`、`backtest_run`、`signal_batch`、`execution_run`、`ledger_posting` |
| 费用 | 统一 `cost_params`（默认 `v1_ashare_default`）；回测与执行/账本同口径 |
| 账本 | 现金账户共享；持仓 sleeve；lot 带 `strategy_version` |

权威产消表：[database/schema/README.md](./database/schema/README.md)。迁移说明：[database/migrations/README.md](./database/migrations/README.md)。

---

## 9. 环境与配置

| 变量 | 作用 |
| --- | --- |
| `ASHARE_DATABASE_URL` | 可选；不设则用 pgembed |
| `ASHARE_API_TOKEN` | API Bearer（可选） |
| `ASHARE_API_REQUIRE_TOKEN` | 设为真则强制鉴权 |
| `ASHARE_PROMOTION_GATE_VERSION` | 晋升门参数版本（默认 `v1_default`） |
| 告警 webhook | 见 `ops_monitor` README |

推荐：Python 3.13，Windows / PowerShell 或同等环境。依赖：`cd backend && pip install -r requirements.txt`。

---

## 10. 快速开始

```bash
cd backend
pip install -r requirements.txt
python main.py migrate

# 回归（推荐每次合入前）
python -m pytest tests/ -q
python main.py e2e
python -m strategy_registry.selfcheck   # 示例；各模块均有 selfcheck
```

### 10.1 短窗数据冒烟（勿 ALL_LISTED）

```bash
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
python main.py security_master --p0 --as-of 2026-07-23
python main.py core_market --p0 --universe TOP100 --start 2026-07-21 --end 2026-07-23 --chunk-size 8
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 --start 2026-07-21 --end 2026-07-23
python main.py data_quality --scope CORE --start 2026-07-21 --end 2026-07-23 --factor-type qfq
```

### 10.2 研究 → 回测 → 晋升（示意）

```bash
# 因子 + IC（窗口按本机数据调整）
python main.py research --factor MOM_20 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py backtest --strategy FACTOR_TOP_N --factor MOM_20 --top-n 20 \
  --universe TOP100 --start 2026-06-01 --end 2026-07-23 --rebalance-days 20

python main.py strategy register --code FTN_MOM20 --kind FACTOR_TOP_N \
  --factor MOM_20 --top-n 20 --rebalance-days 20 --universe TOP100 \
  --research-run <rr_id>
python main.py strategy promote --version <sv_id> --to BACKTESTED --backtest-run <bt_id>
python main.py strategy promote --version <sv_id> --to PAPER
python main.py strategy promote --version <sv_id> --to LIVE
python main.py strategy show --version <sv_id>
```

### 10.3 日更与只读台

```bash
python main.py schedule --once --as-of 2026-07-26   # 非开市日会 skipped
python main.py gateway --port 8080
# 另开终端：
cd frontend/console && python -m http.server 8081
```

更多 kind / 子命令：[backend/README.md](./backend/README.md)、[backend/data_ingest/README.md](./backend/data_ingest/README.md)。

---

## 11. 常用命令速查

| 场景 | 命令 |
| --- | --- |
| 迁移 | `python main.py migrate` |
| 单测 | `python -m pytest tests/ -q` |
| E2E | `python main.py e2e` |
| 日更一轮 | `python main.py schedule --once --as-of YYYY-MM-DD` |
| 覆盖度 | `python main.py coverage` |
| 策略列表 | `python main.py strategy list --status LIVE` |
| 生产信号 | `python main.py signal run --live --as-of YYYY-MM-DD` |
| 组合草稿 | `python main.py portfolio build --version sv_… --as-of … --account paper_default` |
| 风控审核 | `python main.py risk review --portfolio pf_…` |
| 纸面执行 | `python main.py execution run --portfolio pf_…`（CLI 内会对 committed 即时 post） |
| 账本 | `python main.py ledger post --execution ex_…` / `ledger show --account …` |
| Kill | `python main.py risk kill --on/--off` |
| 网关 | `python main.py gateway --port 8080` |

---

## 12. 协作约定（多 AI Agent）

1. **一 Agent 一模块目录**，禁止越界改其他模块实现。  
2. 协作只读对方 `README.md` 与 `database/` 契约；先改迁移/产消登记再改代码。  
3. 跨模块经库交接，只传 ID。  
4. 调度只经 `orchestrator`；对外只经 `api_gateway`。  
5. 合入前：本文件 changelog **顶部**追加；更新相关模块 README；勾选 [架构原则 §6](./ARCHITECTURE_PRINCIPLES.md#6-合入前检查清单)。  
6. 新表 = 新迁移 `033+`；不得改写已发布迁移。

---

## 13. 已知限制与数据债

| 项 | 说明 |
| --- | --- |
| 柜台 | 仅 paper；无真实券商适配器 |
| Sharpe 等 | 回测主表无 Sharpe 列；晋升门暂用 DD/收益/窗/IC |
| sleeve 回填 | 迁移 `031` 将旧仓写入 `strategy_version=''`；与命名 sleeve 并存时账户合计 NAV 可能偏高（见 [ledger README](./backend/ledger/README.md)） |
| 开发机数据 | 短窗 / TOP100；覆盖度与实盘研究不可等同 |
| console | 只读；写操作（晋升审批等）待做 |

---

## 14. 下一优先

阶段 **17+**（详见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)）：

1. 未成交残差 → pending，下日续撮（`execution`）  
2. 行业 / ADV / 换手等事前风控（`risk_engine`）  
3. 冲击成本、T+1 open 等成交假设（`backtest` + `execution`）  
4. console 写操作（经 `api_gateway`）  
5. 实盘柜台适配器（更后）

---

## 15. 开发更新记录

> 新→旧；里程碑在**顶部**追加。

### 2026-07-27 · 根 README 扩写为入口手册
- 补齐完成度矩阵、模块地图、日更、不变量、晋升门、环境变量、命令速查与数据债

### 2026-07-27 · 阶段 16：晋升质量门
- `promotion_gate_params` / `promotion_gate_result`（迁移 `032`）
- BACKTESTED/PAPER/LIVE 评估回撤/收益/样本窗；LIVE 强制 research IC
- 拒绝可审计；`--skip-gates` 须 reason；API/CLI/e2e/pytest 同步

### 2026-07-27 · 根文档对齐阶段 15
- 完成度、主链路、快速开始与代码对齐（迁移 `031`、纸面全链路）

### 2026-07-27 · 阶段 15：策略 sleeve 与回测对齐
- `ledger_sleeve_position`；execution 差额仅对本策略；执行后即时 post
- 非调仓 hold；signal failed 短路；回测 FIFO lot + `close`；迁移 `031`

### 2026-07-27 · 阶段 14：量化正确性 Critical
- `factor_refresh`；现金投影；`strategy_capital_alloc`；`close` 成交；`can_sell`；账户合并敞口；`030`

### 2026-07-27 · 阶段 13：编排与执行硬化
- execution 原子提交；SM 失败跳过交易链；告警分级；API token；Kill 解除可重审

### 2026-07-27 · 阶段 12–5（摘要）
- E2E + console；生产硬化 → gateway → ledger → execution → risk → portfolio → strategy/signal（`023`–`029`）

### 2026-07-27 · 阶段 4 及数据增强（摘要）
- schedule / ops_alert / coverage；tech 与分钟 K；ALPHA 增强 kind

### 2026-07-25 · 阶段 1–3
- 回测撮合 + pytest/CI；研究 IC + FACTOR_TOP_N；PIT / 除权 DQ / 成分点时

### 2026-07-24 及前期
- PG 底座与 CORE/ALPHA ingest；加工 / DQ / Universe / EW_HOLD；首推 GitHub

更细条目见 git 历史与各模块 README。

---

## 16. 文档索引

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | 强制架构、不变量、合入清单 |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | 分阶段任务书（现至阶段 16） |
| [backend/README.md](./backend/README.md) | 后端模块总览与 CLI |
| [database/README.md](./database/README.md) | 迁移与契约入口 |
| [database/schema/README.md](./database/schema/README.md) | 表产消登记（权威） |
| [database/migrations/README.md](./database/migrations/README.md) | 迁移文件一览 |
| [frontend/README.md](./frontend/README.md) | 前端边界 |
| [backend/strategy_registry/README.md](./backend/strategy_registry/README.md) | 晋升与质量门 |
| [backend/ledger/README.md](./backend/ledger/README.md) | sleeve / 回填说明 |
| [backend/orchestrator/README.md](./backend/orchestrator/README.md) | 日更编排 |
| [backend/e2e/README.md](./backend/e2e/README.md) | 短窗 E2E |

---

## 许可与贡献

内部协作：开分支 → 更新本 changelog 与相关 README → 合入 `main`。合入前检查见架构原则 §6。
