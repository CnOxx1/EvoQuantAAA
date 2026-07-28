# A 股量化系统 · 架构原则（优化版）

> 一句话：**控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。**

配套评审见 Cursor Canvas：`ashare-arch-review.canvas.tsx`。

---

## 1. 三层顶层目录（强制）

| 目录 | 角色 | 职责 |
| --- | --- | --- |
| `frontend/` | 交互与展示（**Arco Design SPA**：`frontend/app`） | 页面、图表、人工干预、配置 UI；**不直连业务库** |
| `backend/` | 业务能力 | 按模块拆分的服务/任务；读写库；对外经 `api_gateway` |
| `database/` | 数据契约 | 迁移、schema、种子；**唯一事实源定义**（可物理分库） |

补充：

- 根目录可有总览 README、本原则、CI/脚本。
- 前端只调 `api_gateway`（或经其转发的 API），不持有库连接。
- 环境分层：`research` / `paper` / `live`（同一套代码，账户与柜台适配器隔离）。

---

## 2. 后端模块（强制）

模块之间 **禁止** 互相 import 内部实现；只经 **数据库已提交数据** + **ID 编排** 协作。  
`shared/` 只放无业务编排语义的工具，**不得**依赖业务模块，**不得**变相调度流水线。

| 模块 | 路径 | 主要作用 |
| --- | --- | --- |
| shared | `backend/shared/` | 公共类型、日志、DB 辅助（无业务编排） |
| api_gateway | `backend/api_gateway/` | 对外 API/BFF：鉴权、聚合查询、统一错误码 |
| orchestrator | `backend/orchestrator/` | 任务 DAG/定时；只传 `job_id`/`batch_id`/`run_id` |
| security_master | `backend/security_master/` | 证券主数据、Universe、可交易状态快照 |
| data_ingest | `backend/data_ingest/` | 外部数据拉取 → 原始表 |
| data_process | `backend/data_process/` | 清洗、复权、对齐 → 加工表 |
| data_quality | `backend/data_quality/` | DQ 门禁；未通过禁止进研究/生产信号 |
| research_lab | `backend/research_lab/` | 实验因子/信号（可脏、不直接实盘） |
| signal_prod | `backend/signal_prod/` | 已晋升的生产信号（带版本） |
| strategy_registry | `backend/strategy_registry/` | 策略/因子版本、晋升状态与质量门 |
| backtest | `backend/backtest/` | A 股约束回测与报告 |
| portfolio_construct | `backend/portfolio_construct/` | 组合构建 → 目标持仓（草稿） |
| risk_engine | `backend/risk_engine/` | 事前/硬风控、Kill Switch；可否决执行 |
| execution | `backend/execution/` | OMS：委托/成交事件（`paper` / `broker_stub` / `live_gated`；真实 SDK 待接） |
| ledger | `backend/ledger/` | 资金持仓过账；T+1 lot；**策略 sleeve 隔离持仓** |
| ops_monitor | `backend/ops_monitor/` | 监控、对账、告警、受控重跑 |
| e2e | `backend/e2e/` | 生产链路短窗回归（自备种子） |

已废弃目录名（勿再使用）：`research_factor`、`portfolio_risk`。

---

## 3. 数据流原则（核心）

### 3.1 强制

1. **库是事实源**：跨模块业务数据必须落库；下游只读已提交数据。  
2. **编排只传引用**：`orchestrator` 或事件载荷仅含 ID，不含行情/因子全量。  
3. **契约先于代码**：先改 `database/`，再改读写模块与双方 README。  
4. **DQ 门禁**：`data_quality` 未通过的批次，不得被 `research_lab` / `signal_prod` 消费。  
5. **研究/生产隔离**：实验产出不得直接进 `execution`；须经 `strategy_registry` 晋升后由 `signal_prod` 生成；晋升 BACKTESTED/PAPER/LIVE 须过质量门（或显式 skip 审计）。  
6. **风控硬否决**：`risk_engine` 未放行或 Kill Switch 开启时，`execution` 不得新开仓。  
7. **OMS ≠ 账本**：`execution` 写订单/成交事件；`ledger` 负责过账与可卖数量。  
8. **多策略同账户**：现金共享，持仓按 `strategy_version` sleeve 隔离；差额成交不得动他策略仓。  
9. **成交价口径**：纸面 sizing/fill 优先未复权 `close`（与回测引擎对齐）；复权价用于收益/因子。

### 3.2 允许

| 可以不落库 | 必须落库 |
| --- | --- |
| 模块内临时变量 | 原始/加工批次、Universe 快照 |
| 前端本地 UI 状态 | 生产信号、目标持仓、风控快照 |
| 热缓存（库仍是真相） | 委托、成交、账本分录、策略版本 |
| 展示用瞬时行情帧 | 回测报告、对账与告警 |

### 3.3 标准主链路

```text
外部源 → data_ingest(raw, batch_id)
      → data_process(processed)
      → data_quality(gate)
      → research_lab(实验) → strategy_registry(晋升)
      → [schedule] factor_refresh（LIVE 因子日刷）
      → signal_prod(生产信号, strategy_version)
      → portfolio_construct(目标持仓草稿；非调仓日 hold)
      → risk_engine(放行/否决/kill switch / 账户合并敞口)
      → [可选人工确认] → execution(订单事件；sleeve 差额；现金约束)
      → ledger(过账；可与 execution CLI 串联即时 post) → ops_monitor(对账)

全程由 orchestrator 调度（只传 ID）；
对外查询/操作经 api_gateway；
费用/滑点参数读 database 中统一 cost 参数表。
```

### 3.4 幂等与重跑

- 批次与任务具备稳定键；重复执行不产生脏数据。  
- 下游仅凭库内状态可重跑；重跑由 `orchestrator` / `ops_monitor` 触发（传 ID）。

### 3.5 存储分层（逻辑强制，物理可分）

| 域 | 用途 | 说明 |
| --- | --- | --- |
| market_data | 行情/基本面时序 | 可独立库或对象存储 + 清单表 |
| oltp | 订单、账本、任务、风控状态 | 强一致、可事务 |
| ref_data | 证券主数据、日历、费率 | 版本化快照 |

原则仍是「经契约交接」，不要求全部挤进同一个物理库。

---

## 4. README 规范（每个文件夹强制）

文件名统一：`README.md`。

多 AI Agent：**一 Agent 一模块**；了解协作时只读对方 README 与 `database/` 契约。

最小结构：

```markdown
# <目录名>

## 名称
## 生产数据与落库表
## 本目录模块一览
## 协作模块索引（供 AI Agent）
## 边界
## 输入
## 输出
## 运行
## 不变量
```

新增/删改模块时：同步更新父目录一览、相关协作索引、本原则 §2，以及各 README 的「生产数据与落库表」。

**生产数据与落库表（强制字段）** — 每个 README 必须包含：

```markdown
## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| … | `table_name` | … |
```

- 无落库的模块写明「不落库」及原因。
- 表名以 `database/schema` 产消登记为准；先改契约再改代码。

---

## 5. 目录骨架

```text
大a/
├── README.md
├── ARCHITECTURE_PRINCIPLES.md
├── DEVELOPMENT_PLAN.md
├── frontend/
│   └── app/              # React + Arco Design 运维 SPA（唯一前端）
├── backend/
│   ├── shared/ api_gateway/ orchestrator/ security_master/
│   ├── data_ingest/ data_process/ data_quality/
│   ├── research_lab/ signal_prod/ strategy_registry/ backtest/
│   ├── portfolio_construct/ risk_engine/ execution/ ledger/
│   ├── ops_monitor/ e2e/ tests/
└── database/
    ├── migrations/       # 001–038
    ├── schema/           # 产消登记
    └── seeds/
```

---

## 6. 合入前检查清单

- [ ] 新增跨模块数据是否已有表/迁移，并登记生产者/消费者？  
- [ ] 下游是否只按 ID 读库？  
- [ ] 是否绕过 `data_quality` 或 `risk_engine`？  
- [ ] 实验信号是否绕过晋升直接进执行？  
- [ ] `execution` 是否直接改账本余额（应为事件 → ledger 过账）？  
- [ ] 业务模块是否互相 import 或私自调度下游？  
- [ ] 前端是否绕过 `api_gateway` 直连库或其他后端内部口？  
- [ ] 相关 README 是否同步？  

---

## 7. 最终表述

系统分 `frontend`、`backend`、`database` 三部分；后端按交易真相模块拆分；跨模块数据经库交接、编排只传引用；研究与生产隔离；账本与 OMS 分离（纸面执行 + 策略 sleeve）；风控可否决执行；每一文件夹维护统一 README 供多 Agent 协作。
