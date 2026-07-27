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

**状态（2026-07-27）**：阶段 **1–17** 已落地；迁移 **`001`–`033`**。纸面全链路可跑；晋升含质量门；未成交残差可续撮；**未接**真实柜台。

| 能力域 | 状态 | 说明 |
| --- | --- | --- |
| CORE 取数 / 加工 / DQ | ✅ | 日线复权、停牌涨跌停、`can_buy`/`can_sell`、CORE gate |
| ALPHA 取数 | ✅ | 可插拔；失败不挡 CORE |
| Universe | ✅ | TOP100 / SECTOR_LEADERS / 指数成分等日快照 |
| 研究因子 + IC | ✅ | MOM / VAL / FLOW / TECH_*；`research_run.meta_json.report` |
| 回测引擎 | ✅ | EW_* / FACTOR_TOP_N；FIFO lot T+1；`close` 成交 |
| 策略晋升 + 质量门 | ✅ | DRAFT→…→LIVE；IC/DD/样本窗（`032`） |
| 生产信号 / 组合 / 风控 | ✅ | PAPER/LIVE；非调仓 hold；Kill Switch；账户合并敞口 |
| 纸面 OMS + 账本 | ✅ | 差额成交；sleeve；现金约束；执行后可即时过账；**残差 pending 续撮** |
| 日更编排 / 告警 | ✅ | `schedule`；`factor_refresh`；pending resume；`ops_alert` |
| API + E2E + console | ✅ | `/v1`；`python main.py e2e`；只读台 |
| 实盘柜台 | ❌ | 仅 paper adapter |
| 冲击成本 / 行业·ADV 风控 | ⏳ | 阶段 18+ |

**开发机约束**：只做短窗冒烟（几天～约 1 个月、TOP100 或单票）。**禁止** ALL_LISTED（6000+）长窗 bulk、禁止本机长历史回填。

---

## 3. 仓库结构

```text
EvoQuantAAA
├── README.md                      # 本文件（入口手册）
├── ARCHITECTURE_PRINCIPLES.md     # 强制架构与合入清单
├── DEVELOPMENT_PLAN.md            # 分阶段任务书（现至 17）
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
│   ├── migrations/                # 001–033（新文件从 034 起）
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
  → execution            order/fill + execution_pending（残差续撮）
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
  → portfolio → risk
  → execution resume-pending   # 先续撮历史残差（hold 日也跑）
  → execution approved(+ CLI 即时 post)
  → ledger 兜底
```

- `security_master` / `factor_refresh` 失败：跳过交易链  
- `signal_live` failed：跳过 portfolio/risk/execution_paper，**仍跑 pending 续撮 + ledger**  
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
| 执行 | execution | `backend/execution/` | 纸面 OMS；sleeve 差额；现金；**pending 续撮** | [link](./backend/execution/README.md) |
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
| 迁移 | `python main.py migrate`；已发布脚本不改写；新文件从 **`034`** 起 |
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
| 纸面执行 | `python main.py execution run --portfolio pf_…`（CLI 内对有 fill 的 committed 即时 post） |
| 残差续撮 | `python main.py execution resume-pending --as-of YYYY-MM-DD` |
| 残差列表 | `python main.py execution list-pending --account paper_default` |
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
6. 新表 = 新迁移 `034+`；不得改写已发布迁移。

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

阶段 **18+**（详见 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)）：

1. 行业 / ADV / 换手等事前风控（`risk_engine`）  
2. 冲击成本、T+1 open 等成交假设（`backtest` + `execution`）  
3. console 写操作（经 `api_gateway`）  
4. 实盘柜台适配器（更后）

---

## 15. 开发更新记录

> **约定**：新→旧；有可合并里程碑时在**顶部**追加。每条尽量写清：动机、迁移、模块、行为、验收。  
> 任务原文与验收标准以 [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) 为准；表级产消以 [database/schema/README.md](./database/schema/README.md) 为准。

### 阶段 → 迁移速查

| 阶段 | 迁移 | 主题 |
| --- | --- | --- |
| 底座 / ingest | `001`–`016` | CORE/ALPHA raw、加工、DQ、Universe、backtest、新闻增强等 |
| 2–3 研究正确性 | `017`–`018` | 因子表、基本面 PIT |
| 4 编排运维 | `019`–`022` | 告警、tech 日线/分类、分钟 K |
| 5–12 生产链路 | `023`–`029` | 策略信号→组合→风控→执行→账本→API→硬化 |
| 13 补丁 | （行为向，无独立大表） | 原子执行 / SM 门禁 / 告警分级 |
| 14 | `030` | 量化正确性（配额、can_sell 等） |
| 15 | `031` | 策略 sleeve |
| 16 | `032` | 晋升质量门 |
| 17 | `033` | 未成交残差 pending |

---

### 2026-07-27 · 阶段 17：未成交残差 pending
- **动机**：涨跌停/停牌/现金不足等导致当日未对齐目标时，残差被丢弃且 hold 日无新组合可执行。
- **迁移**：`033_execution_pending.sql` → `execution_pending` / `execution_pending_event`；`execution_run.run_kind` + `strategy_version`；portfolio committed 唯一仅约束 `run_kind=portfolio`。
- **模块**：`execution`（残差计算/落库/`resume_pending`）、`orchestrator`（先续撮再 approved）、`main.py` CLI。
- **行为**：
  - portfolio 执行：意图−成交≥1 手 → open pending；同 sleeve 旧 open 先 superseded。
  - `resume-pending`：按 sleeve 当日 can_*/T+1/现金续撮；同日幂等；`run_kind=pending_resume`。
  - schedule：`execution_pending_resume` 在 `execution_paper` 前；signal failed 时仍续撮 + ledger。
  - CLI：无 fill 不强制 ledger post。
- **验收**：migrate `033`；残差 pytest；全量 pytest；文档同步。

### 2026-07-27 · 根 README 扩写为入口手册
- **动机**：根文档过简，无法作为 Agent/新人入口。
- **改动**：完成度矩阵、模块地图（链到各 README）、日更序列、不变量摘要、研究→生产与质量门、环境变量、分步快速开始、命令速查、数据债与下一优先、文档索引。
- **验收**：与阶段 16 / 迁移 `032` 描述一致。

---

### 2026-07-27 · 阶段 16：晋升质量门
- **动机**：纸面链路已通，但策略进 LIVE 缺少硬门槛（「能晋升」≠「该晋升」）。
- **迁移**：`032_promotion_gates.sql` → `promotion_gate_params`（版本化阈值，默认 `v1_default`）、`promotion_gate_result`（每次评估审计，含 skip）。
- **模块**：`strategy_registry`（`gates.py` 纯评估 + `service.promote` 拦截）；`api_gateway`（`skip_gates` / `gate_version`）；`main.py strategy promote|show`；`e2e` 种子带 IC 报告与 ≥20 日回测窗，并重置账户持仓以保证 fill。
- **行为**：
  - 晋升至 BACKTESTED / PAPER / LIVE 前读 `backtest_run`：`max_drawdown`、`total_return`、日历窗、`trade_count`。
  - LIVE 额外强制 committed `research_run.meta_json.report`（`ic_mean` / `ic_days` 等）。
  - 未通过 → 拒绝晋升，仍落 `promotion_gate_result(passed=0)`。
  - `--skip-gates` 必须带 `--reason`（`skipped=1`）；`ASHARE_PROMOTION_GATE_VERSION` 可切阈值版本。
  - `RETIRED` / `LIVE→PAPER` 不评估。
- **验收**：migrate `032`；pytest 门控用例；selfcheck；e2e exit 0；相关 README / 任务书 / 本 changelog 同步。
- **提交**：`b0d2ade`。

---

### 2026-07-27 · 根文档对齐阶段 14–15
- **动机**：阶段 14–15 合入后根 README 仍写「生产路径待建 / 迁移至 029」等过时表述。
- **改动**：对齐迁移 `031`、纸面全链路、sleeve、短窗快速开始；精简旧 changelog 条目（本轮起再展开）。
- **提交**：`da896d9`。

---

### 2026-07-27 · 阶段 15：策略 sleeve 与回测对齐
- **动机**：同账户多策略若共用账户级持仓，差额成交会互相踩仓；回测 lot T+1 与 live 口径不一致。
- **迁移**：`031_strategy_sleeve.sql` → `ledger_sleeve_position`；`ledger_lot.strategy_version` / `ledger_posting.strategy_version`；存量 POSITION 回填到 `strategy_version=''`。
- **模块**：`ledger`、`execution`、`portfolio_construct`、`orchestrator`、`backtest`、CLI（execution 后即时 post）。
- **行为**：
  - 持仓按 `strategy_version` sleeve 隔离；现金仍账户共享。
  - execution 差额只相对本策略 sleeve；`execution run` 每个 committed 后立即 `ledger post`。
  - 已有 posting 的 portfolio 禁止 `--force` 重跑。
  - live portfolio：`require_signal_as_of` — 非调仓日 hold（skipped）。
  - schedule：`signal_live` failed 短路后续交易步。
  - 回测：FIFO lot T+1（加仓不合并最早 `buy_date`）；成交价优先未复权 `close`。
- **数据债**：旧 `''` sleeve 与命名 sleeve 并存时，账户合计 NAV 可能偏高（见 [ledger README](./backend/ledger/README.md)）。
- **验收**：迁移 `031`；pytest 全绿；e2e 含 sleeve 过账。
- **提交**：含于 `226a7e7`（与阶段 14 同发）。

---

### 2026-07-27 · 阶段 14：量化正确性 Critical
- **动机**：生产日更未刷 LIVE 因子、纸面可透支、多策略 NAV 未切分、成交价与复权混淆、风控未合并同账户敞口。
- **迁移**：`030_quant_correctness.sql` → `portfolio_target_position.can_sell`；`strategy_capital_alloc`。
- **模块**：`orchestrator`（`factor_refresh`）、`execution`（现金投影）、`portfolio_construct`（资本配额 / NAV）、`risk_engine`（账户合并敞口）、sizing 口径。
- **行为**：
  1. schedule 在 `signal_live` 前按 LIVE 策略刷新 `research_factor_value`；失败跳过交易链并 `degraded`。
  2. 纸面成交：先卖后买投影现金；不足 → `insufficient_cash` / `clamped_cash`。
  3. 同账户多策略经 `strategy_capital_alloc` 切分 NAV（缺省等权）。
  4. sizing / 成交价优先未复权 `close`（缺再退 `adj_close`）。
  5. 目标腿落库 `can_sell`；风控合并同账户同日敞口。
- **验收**：迁移 `030`；pytest 含现金约束与账户合并敞口。
- **提交**：含于 `226a7e7`。

---

### 2026-07-27 · 阶段 13：编排与执行硬化补丁
- **动机**：执行非原子、SM 失败仍跑交易链、告警无分级、API 鉴权可选过松、Kill 解除后草稿无法重审。
- **模块**：`execution`（`commit_execution_atomic`）、`orchestrator`、`ops_monitor`（`notify_round` severity）、`api_gateway`（`ASHARE_API_REQUIRE_TOKEN`）、`risk_engine`。
- **行为**：
  - order/fill 与 run 状态同事务提交；失败不留脏 running。
  - `security_master` 失败 → 跳过 signal→ledger，本轮 `degraded`。
  - failed / degraded 告警分级；可选强制 Bearer。
  - Kill 关闭后可重审曾因 Kill 被否决的组合。
- **验收**：pytest 全绿；README 与行为一致。
- **提交**：含于 `a7e2f59` 链路后续硬化（与 5–12 同波交付说明见下）。

---

### 2026-07-27 · 阶段 12：E2E 回归 + 最小前端
- **动机**：缺一键短窗回归与可视只读台，人工难验证全链路。
- **模块**：`backend/e2e`（`python main.py e2e`）、`frontend/console`（静态页 + gateway CORS）。
- **行为**：自备种子跑通 register→promote→signal→portfolio→risk→execution→ledger→API TestClient；断言组合/执行/过账幂等；console 只读拉 strategies / kill / ledger。
- **约束**：不拉 ALL_LISTED；`require_dq=False` 仅回归。
- **验收**：e2e exit 0；console 可访问 gateway。
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 11：生产链路硬化
- **动机**：空仓全买叠加、组合/执行可重复插入、过账非原子、schedule 失败语义不清。
- **迁移**：`029_prod_hardening.sql` — 组合按日活跃唯一；execution/ledger `running` 唯一等。
- **行为**：
  - execution 读 ledger 持仓做**差额** + T+1 可卖，避免重复全仓买入。
  - portfolio 同日活跃幂等；默认账本 NAV；仅 committed 信号。
  - ledger 分录与 posting committed 同事务。
  - schedule 交易步骤失败 → `degraded`（非整轮静默成功）。
  - ingest `timeutil` / 解析迁入 `shared` / `ingest_common`。
- **验收**：pytest 全绿；重跑 schedule 不叠加空仓全买。
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 10：对外网关（api_gateway）
- **动机**：frontend / 外部调用不能直连库或各模块内部口。
- **迁移**：`028_api_gateway.sql` → `api_audit_log`。
- **行为**：FastAPI `/v1` 只读（strategies / portfolios / risk / executions / ledger / alerts）+ 写（promote / kill / review）；可选 `ASHARE_API_TOKEN`；写操作落审计；CLI `gateway`。
- **验收**：`/health`、`/v1/strategies` 可通；写操作有审计行。
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 9：账本过账（ledger）
- **动机**：OMS 事件 ≠ 资金持仓真相；需独立过账与 T+1 可卖。
- **迁移**：`027_ledger.sql` → `ledger_account` / `ledger_posting` / `ledger_entry` / `ledger_balance` / `ledger_lot`；种子 `paper_default`。
- **行为**：消费 committed `fill_event`；BUY 扣现金建 lot；SELL 校验 T+1 FIFO；同 execution 幂等；CLI `ledger ensure|post|show|sellable|list`；schedule 在 execution 后 `post --unposted`（后由阶段 15 改为执行后即时 post + 兜底）。
- **验收**：paper execution 可过账；同日卖出在投影单测中被拒。
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 8：纸面执行（execution）
- **动机**：风控放行后需要 OMS 事件层（尚未接真实柜台）。
- **迁移**：`026_execution.sql` → `execution_run` / `order_event` / `fill_event`。
- **行为**：仅 `approved` + 最新 risk approved + Kill off；paper 适配器即时成交；费用读 `cost_params`；成功后 portfolio→`executed`；CLI `execution run|list|show`；schedule 接在 risk 后。
- **验收**：approved 可 committed；kill on / 非 approved → blocked。
- **提交**：含于 `a7e2f59`。（后续阶段 11/14/15 将「空仓全买」演进为差额 / 现金 / sleeve。）

---

### 2026-07-27 · 阶段 7：风控关卡（risk_engine）
- **动机**：执行前必须有硬否决与 Kill Switch。
- **迁移**：`025_risk_engine.sql` → `risk_decision` / `kill_switch` / `risk_limits`（种子 `v1_default`）。
- **行为**：硬规则（Kill、单票权重、只数、敞口、can_buy、整手）；通过 → portfolio `approved`，否则 `rejected`；CLI `risk review|kill|status|list|show`；schedule 审当日 draft。
- **验收**：draft 可放行；Kill on 必否决。（阶段 14 起增加账户合并敞口。）
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 6：组合草稿（portfolio_construct）
- **动机**：生产权重需落地为整手目标持仓草稿，供风控/执行消费。
- **迁移**：`024_portfolio_construct.sql` → `portfolio_target` / `portfolio_target_position`。
- **行为**：仅 PAPER/LIVE；读 as_of 及之前最近调仓日信号；剔 `can_buy!=1`/缺价后重归一；按 `lot_size` 整手下取；`status=draft`；CLI `portfolio build|list|show`；schedule 在 signal 后跑 LIVE。
- **验收**：对已有 LIVE 信号可出草稿。（后续：幂等、账本 NAV、非调仓 hold、资本配额、can_sell。）
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 5：研究→生产隔离（strategy_registry + signal_prod）
- **动机**：实验信号不得直接进执行；需版本状态机与生产权重表。
- **迁移**：`023_strategy_signal.sql` → `strategy_version` / `strategy_transition` / `signal_batch` / `signal_prod_weight`。
- **行为**：
  - registry：`register|promote|retire|list|show`；DRAFT→BACKTESTED→PAPER→LIVE（可 RETIRED）；BACKTESTED 须 committed `backtest_run`；同 code 至多一 LIVE（CAS 晋升）。
  - signal_prod：仅 PAPER/LIVE；FACTOR_TOP_N 用**前一交易日**因子（禁前视）；写权重批次；默认要求 DQ 区间 passed；schedule 日更 LIVE（非调仓日 skipped）。
- **验收**：register→promote→`signal run` 落库；pytest 含前视防护。（阶段 16 起晋升加质量门。）
- **提交**：含于 `a7e2f59`。

---

### 2026-07-27 · 阶段 4：编排、运维与数据层收尾
- **动机**：无人值守日更、失败可观测、覆盖度可查；技术指标与分钟线支撑研究。
- **迁移**：`019` `ops_alert`；`020`–`021` 日线 tech + category；`022` 分钟 K + 分钟 tech。
- **行为**：
  - `python main.py schedule --once/--at`：daily → SM → ALPHA →（其后阶段再接交易链）。
  - `ops_alert` + 可选 webhook；`coverage` 覆盖度矩阵。
  - 新闻去重 / 水位回看；`data_process --kind tech_indicator`；TECH_* 研究因子。
- **相关前期数据增强（同波或紧前）**：估值/板块/解禁/股东（`013`）、新闻情绪官方/论坛/政策（`014`）、重大合同（`015`）、个股关系（`016`）。
- **验收**：schedule 可跑一轮；告警可写库；tech/分钟链路可冒烟。
- **提交**：`a76043e`（及前后 ingest 增强提交）。

---

### 2026-07-25 · 阶段 3：PIT 与数据正确性
- **动机**：基本面/成分/涨跌停若点时错误，研究与掩码不可信。
- **迁移**：`018_phase3_pit_correctness.sql` → `processed_fund_snapshot`（`valid_from`/`valid_to` 区间）。
- **行为**：
  - 基本面 PIT：按 `publish_date <= trade_date` 取最新报告期。
  - 除权交叉校验 DQ 规则；成分历史按快照 as-of 回放。
  - 涨跌停价格推导回退，补齐近年可买可卖掩码。
  - ALPHA DQ 质量报告（不挡 CORE）。
- **验收**：PIT/成分/掩码相关 pytest 或 selfcheck 通过。
- **提交**：含于 `85ba0a7`。

---

### 2026-07-25 · 阶段 2：最小研究闭环（research_lab）
- **动机**：有行情无因子/无评估/无因子策略回测，无法形成研究闭环。
- **迁移**：`017_research_lab.sql` → `research_run` / `research_factor_value`。
- **行为**：
  - 基线因子落库：`MOM_20`、`VAL_PE_PCT`、`FLOW_NET_5`（后续加 TECH_*）。
  - IC / ICIR / 胜率 / 分层与多空（写入 `research_run.meta_json.report`）。
  - 回测新增 `FACTOR_TOP_N`：调仓日用前一日因子 top N 等权。
- **验收**：数据→因子→IC→FACTOR_TOP_N 回测可短窗跑通。
- **提交**：含于 `85ba0a7`。

---

### 2026-07-25 · 阶段 1：回测正确性 + 测试基建
- **动机**：早期 EW 引擎未真正用 T+1/`can_sell`/印花税，回测不可信。
- **迁移**：沿用 `010_backtest.sql`（`cost_params` / `backtest_run` / `nav` / `trade`）。
- **行为**：
  - 通用撮合 `run_target_weights`：先卖后买、T+1、整手、涨跌停掩码、印花税（仅卖）、滑点、现金不足缩量。
  - `EW_HOLD` / `EW_REBALANCE` 基于新引擎；CLI `--rebalance-days`。
  - `backend/tests/` pytest；CI + `.gitignore` 排除 `data/pgdata` 等。
- **验收**：engine/compute/rules 单测绿；CI 绿。
- **提交**：含于 `85ba0a7`。

---

### 2026-07-24 及前期 · 底座与 CORE/ALPHA 骨架
- **动机**：建立 PG 契约、可插拔取数、加工/DQ/Universe、最小回测入口，并推送 GitHub。
- **迁移**：`001`–`010`（公告、core_ref/market、fundamental、flow、news、process、DQ、security_master、backtest）；其后 `011`–`012` 市场排名与微观结构等。
- **行为**：
  - PostgreSQL（pgembed）+ `shared/db`；禁止 SQLite 主路径。
  - CORE / ALPHA ingest（多 kind）；bulk UPSERT、日期分块、可恢复；`daily` 增量 runner。
  - `data_process` 复权 / `ret_1d` / `can_buy`/`can_sell`；`data_quality` CORE gate；`security_master` Universe 快照。
  - 初版 `EW_HOLD` 回测与模块 README 协作约定；根 README changelog 机制。
- **代表提交**：`5842d35`（初版）、`d53095d`（文档与 changelog）、`318da6f` / `0e2c69c` / `b0e24a0`（universe 分块、ingest 硬化、新闻情绪等）。

---

合入新功能时：在本节**顶部**追加同结构条目（动机 / 迁移 / 模块 / 行为 / 验收），并更新上方「阶段 → 迁移速查」表。

---

## 16. 文档索引

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | 强制架构、不变量、合入清单 |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | 分阶段任务书（现至阶段 17） |
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
