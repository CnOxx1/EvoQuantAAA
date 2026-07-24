# ops_monitor

## 名称
运维监控、对账与告警；受控重跑只传引用 ID。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 告警 | 告警表（如 `ops_alert`，待建） | 监控触发时 |
| 对账报告 | 对账表（如 `reconcile_report`，待建） | 对账任务完成时 |
| （读）批次/订单/账本 | `ingest_batch` 等 | 只读已落库状态 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 告警/对账表 | 上游契约 |
| orchestrator | `../orchestrator/README.md` | 调度 | 请求重跑 |
| data_quality | `../data_quality/README.md` | DQ 失败 | 告警来源 |
| execution | `../execution/README.md` | 成交事件 | 对账对象 |
| ledger | `../ledger/README.md` | 账本 | 对账对象 |
| risk_engine | `../risk_engine/README.md` | Kill Switch | 可联动告警 |
| frontend/ops | `../../frontend/ops/README.md` | 运维 UI | 下游 |
| frontend/console | `../../frontend/console/README.md` | 总控 | 下游摘要 |

## 边界
- 做：健康度、延迟、失败告警；持仓/资金/成交对账；触发重跑（ID）。
- 不做：替代领域模块写核心算法；无审计修数。

## 输入
- 任务状态、DQ 结果、订单事件、账本余额

## 输出
- 告警、对账报告；重跑请求（`job_id`/`batch_id`）

## 运行
- 定时对账 + 事件驱动告警（待定）

## 不变量
- 重跑/修复可审计
- 不搬运业务大数据包跨模块
