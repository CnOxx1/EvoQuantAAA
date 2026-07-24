# A 股量化系统

> 控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。

完整原则：[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)

## 生产数据与落库表

本仓库各业务模块的落库细节见各目录 README 本节；权威表清单见 `database/schema/README.md`。

| 层级 | 典型落库 |
| --- | --- |
| database/ | 定义表结构（migrations/schema），不产生业务行数据 |
| backend/ | 各模块写入约定 `raw_*` / oltp 表（见子目录） |
| frontend/ | **不直连库**，无业务落库 |


## 本目录模块一览

| 模块/子目录 | 路径 | 主要作用 |
| --- | --- | --- |
| 架构原则 | `ARCHITECTURE_PRINCIPLES.md` | 拆分、数据流、产消与多 Agent 约定 |
| frontend | `frontend/` | UI；只经 api_gateway，不直连库 |
| backend | `backend/` | 业务模块（主数据/数据/研究生产/组合风控/执行账本等） |
| database | `database/` | 迁移、schema（含产消登记）、种子 |

## 主链路（给所有 Agent）

```text
ingest → process → DQ → research_lab → 晋升(registry)
     → signal_prod → portfolio_construct → risk_engine
     → execution → ledger → ops_monitor
（orchestrator 调度；api_gateway 对外）
```

## 协作说明（多 AI Agent）

- **一个 Agent 只写一个模块目录**，禁止越界改其他模块实现。
- 了解协作：**只读**对方 `README.md` 与 `database/schema` 契约。
- 跨模块数据：先落库，再传 `batch_id` / `job_id` / `run_id` / `strategy_version` 等引用。
- 调度只通过 `orchestrator`；对外 API 只经 `api_gateway`。
- 新增模块：更新本文件、父 README、协作索引与原则 §2。

## 合入前检查

见 [ARCHITECTURE_PRINCIPLES.md §6](./ARCHITECTURE_PRINCIPLES.md#6-合入前检查清单)。
