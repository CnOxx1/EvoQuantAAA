# ops

## 名称
监控、对账、告警与受控重跑操作界面。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 告警确认/重跑经 API，由 ops/orchestrator 落库 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| ops_monitor | `../../backend/ops_monitor/README.md` | 监控对账 | 上游领域 |
| orchestrator | `../../backend/orchestrator/README.md` | 重跑 | 经 gateway |
| data_quality | `../../backend/data_quality/README.md` | DQ 失败 | 展示 |
| console | `../console/README.md` | 总控 | 同级 |

## 边界
- 做：告警确认、对账差异展示、触发重跑（只传 ID）。
- 不做：前端修库或回填行情。

## 输入
- gateway：`job_id` / `alert_id` / `reconcile_id`

## 输出
- 运维视图；重跑/确认请求

## 运行
- 随 frontend 启动（待定）

## 不变量
- 不绕过 gateway 访问存储
