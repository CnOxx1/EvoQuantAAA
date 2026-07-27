# EvoQuantAAA · A 股量化系统

> **控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。**

远程：[CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA) · 架构原则：[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) · 任务书：[DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)

---

## 1. 项目是什么

面向 **A 股实盘约束** 的量化研究 + 纸面生产骨架：取数 → 加工 → DQ → Universe → 因子/回测 → 策略晋升 → 生产信号 → 组合 → 风控 → 纸面 OMS → 账本 → API / 日更编排。

**当前状态（2026-07-27）**：阶段 **1–15** 已落地（迁移至 `031`）。纸面全链路可跑；**未接**真实券商柜台。开发机只做短窗冒烟（TOP100 / 单票），禁止 ALL_LISTED 长窗 bulk。

| 目标 | 说明 |
| --- | --- |
| 真相在库 | 跨模块业务数据落库；下游只读已提交数据与 ID |
| CORE 先于 ALPHA | 先复权收益与可成交约束，再扩基本面/资金/文本 |
| A 股约束可回测 / 可纸面成交 | T+1、整手、涨跌停掩码、印花税、未复权成交价、策略 sleeve |
| 多 Agent 可协作 | 一 Agent 一模块；只读对方 README 与 `database/` 契约 |

**非目标（当前）**：Tick/L2、宏观全量、ML 因子框架、实盘柜台直连、前端完整产品化（仅 `console` 只读台可用）。

---

## 2. 仓库结构

```text
EvoQuantAAA
├── README.md                    # 本文件
├── ARCHITECTURE_PRINCIPLES.md   # 强制架构原则
├── DEVELOPMENT_PLAN.md          # 分阶段任务书
├── docker-compose.yml
├── backend/                     # 业务 + CLI：python main.py …
│   ├── data_ingest/ … data_process/ data_quality/ security_master/
│   ├── research_lab/ strategy_registry/ signal_prod/ backtest/
│   ├── portfolio_construct/ risk_engine/ execution/ ledger/
│   ├── orchestrator/ ops_monitor/ api_gateway/ e2e/ tests/ shared/
├── database/                    # 迁移 001–031 · schema 产消 · seeds
├── frontend/                    # 经 api_gateway；console 只读台
└── scripts/
```

本地 `data/`（pgembed）**不入库**（见 `.gitignore`）。

---

## 3. 主链路

```text
外部源
  → data_ingest (raw_*) → data_process (processed_*) → data_quality (dq_gate)
  → security_master (universe)
  → research_lab → strategy_registry → signal_prod
  → portfolio_construct (draft) → risk_engine (approved)
  → execution (paper fills / sleeve 差额) → ledger (过账 + T+1 lot)
  → api_gateway / ops_monitor

编排 schedule：daily → security_master → ALPHA → factor_refresh
            → signal → portfolio → risk → execution(+即时 post) → ledger 兜底
```

已串通：**取数 → 加工 → DQ → Universe → 研究/回测 → 晋升 → 信号 → 组合 → 风控 → 纸面执行 → 账本 → API → 日更告警**。

### 3.1 模块一览（均可 CLI）

| 域 | 模块 | 要点 |
| --- | --- | --- |
| 契约 | `database/` | 迁移 **`001`–`031`**；PG（pgembed / `ASHARE_DATABASE_URL`） |
| CORE 数据 | `core_ref` / `core_market` | 日历上市行业；日线复权停牌涨跌停指数；分钟 K 按需 |
| ALPHA | announcement / fundamental / flow / news / contract / relation | 可插拔；失败不挡 CORE |
| 加工/质量 | `data_process` / `data_quality` | 复权、`can_buy`/`can_sell`、tech；CORE gate |
| Universe | `security_master` | TOP100 / SECTOR_LEADERS 等日快照 |
| 研究 | `research_lab` / `backtest` | 基线+TECH 因子；EW_* / FACTOR_TOP_N（lot T+1、`close` 成交） |
| 生产 | registry → signal → portfolio → risk → execution → ledger | 纸面；sleeve 隔离；现金约束；非调仓 hold |
| 编排/运维 | `orchestrator` / `ops_monitor` / `api_gateway` / `e2e` | schedule、告警、`/v1`、短窗 E2E |

### 3.2 下一优先（阶段 16+）

晋升质量门（IC/DD）、未成交残差 pending、行业/ADV/换手风控、冲击成本 / T+1 open 成交假设、console 写操作、实盘柜台适配器。

---

## 4. 数据与存储

- **库**：PostgreSQL（默认 pgembed → `data/pgdata`）
- **禁止**：SQLite 生产路径
- **批次**：`ingest_batch` / `process_batch` / `backtest_run` / `dq_gate` / `signal_batch` / `execution_run` / `ledger_posting`
- **账本**：现金账户共享；持仓按 `strategy_version` sleeve；031 回填旧仓为 `strategy_version=''`（见 [`backend/ledger/README.md`](./backend/ledger/README.md)）

权威产消表：[`database/schema/README.md`](./database/schema/README.md)。

---

## 5. 快速开始

```bash
cd backend
pip install -r requirements.txt
python main.py migrate

# 回归（推荐）
python -m pytest tests/ -q
python main.py e2e

# 短窗冒烟示例（勿在本机跑 ALL_LISTED）
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
python main.py security_master --p0 --as-of 2026-07-23
python main.py core_market --p0 --universe TOP100 --start 2026-07-21 --end 2026-07-23 --chunk-size 8
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 --start 2026-07-21 --end 2026-07-23
python main.py data_quality --scope CORE --start 2026-07-21 --end 2026-07-23 --factor-type qfq

# 日更（非开市日会 skipped）
python main.py schedule --once --as-of 2026-07-26

# 只读台
python main.py gateway --port 8080
# 另开终端：cd frontend/console && python -m http.server 8081
```

更多 CLI / kind：[`backend/README.md`](./backend/README.md)、[`backend/data_ingest/README.md`](./backend/data_ingest/README.md)。

---

## 6. 协作约定（多 AI Agent）

1. **一 Agent 一模块目录**，禁止越界改其他模块实现。
2. 协作只读对方 `README.md` 与 `database/` 契约。
3. 跨模块先落库，再传 `batch_id` / `job_id` / `run_id` / `strategy_version` / `portfolio_id` / `execution_id`。
4. 调度只经 `orchestrator`；对外只经 `api_gateway`。
5. 合入前：更新本文件 changelog + 相关模块 README；遵守 [架构原则 §6](./ARCHITECTURE_PRINCIPLES.md#6-合入前检查清单)。

---

## 7. 开发更新记录

> 新→旧；有可合并里程碑时在**顶部**追加。

### 2026-07-27 · 根文档对齐阶段 15
- 根 README 重写：完成度、主链路、快速开始与「下一优先」与代码一致（迁移 `031`、纸面全链路、非柜台）

### 2026-07-27 · 阶段 15：策略 sleeve 与回测对齐
- ledger：`ledger_sleeve_position` + `ledger_lot.strategy_version`；execution 差额仅对本策略
- CLI：每个 committed execution 立即 post；已过账禁止 `--force`
- portfolio live：非调仓日 hold；schedule：signal failed 短路
- backtest：FIFO lot T+1 + 未复权 `close`；迁移 `031`
- 数据：031 回填旧仓到 `strategy_version=''`；开发账户双 sleeve 并存时合计 NAV 可能偏高（见 `ledger/README`）

### 2026-07-27 · 阶段 14：量化正确性 Critical
- schedule `factor_refresh`；纸面现金投影；`strategy_capital_alloc`；sizing/成交用 `close`；目标腿 `can_sell`；账户合并敞口；迁移 `030`

### 2026-07-27 · 阶段 13：编排与执行硬化
- execution 原子提交；`security_master` 失败跳过交易链；告警分级；`ASHARE_API_REQUIRE_TOKEN`；Kill 解除可重审

### 2026-07-27 · 阶段 12–5（摘要）
- 12：`e2e` + `frontend/console` 只读台
- 11–5：生产硬化 → api_gateway → ledger → execution → risk → portfolio → strategy/signal（迁移 `023`–`029`）

### 2026-07-27 · 阶段 4 及数据增强（摘要）
- schedule / ops_alert / coverage；tech 指标与分钟 K；ALPHA 增强 kind；新闻情绪/合同/关系

### 2026-07-25 · 阶段 1–3
- 回测撮合（T+1/印花税）+ pytest/CI；研究因子 IC + FACTOR_TOP_N；PIT / 除权 DQ / 成分点时

### 2026-07-24 及前期
- PG 底座与 CORE/ALPHA ingest；加工 / DQ / Universe / EW_HOLD；首推 GitHub

（更细条目见 git 历史与各模块 README。）

---

## 8. 文档索引

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | 强制架构与合入清单 |
| [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md) | 分阶段任务书（现至阶段 15） |
| [backend/README.md](./backend/README.md) | 后端模块与 CLI |
| [database/README.md](./database/README.md) | 迁移与契约 |
| [frontend/README.md](./frontend/README.md) | 前端边界与 console |
| [backend/ledger/README.md](./backend/ledger/README.md) | sleeve / 历史回填说明 |

---

## 9. 许可与贡献

内部协作：开分支 → 更新 changelog 与相关 README → 合入 `main`。合入前检查见架构原则 §6。
