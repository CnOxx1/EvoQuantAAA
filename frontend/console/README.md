# console

## 名称
总控台 / 仪表盘：任务与风险摘要、导航入口。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API 展示；不落业务库 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 前端总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| orchestrator | `../../backend/orchestrator/README.md` | 任务状态 | 经 gateway |
| ops_monitor | `../../backend/ops_monitor/README.md` | 告警摘要 | 经 gateway |
| risk_engine | `../../backend/risk_engine/README.md` | Kill Switch 状态 | 经 gateway |
| research | `../research/README.md` | 研究页 | 同级导航 |
| trade | `../trade/README.md` | 交易页 | 同级导航 |
| ops | `../ops/README.md` | 运维页 | 同级导航 |

## 边界
- 做：概览与入口。
- 不做：完整业务表单（各专项页负责）。

## 输入
- gateway 汇总 API；`job_id` / `run_id` 等引用

## 输出
- 概览视图与跳转

## 运行
- 随 frontend 启动（待定）

## 不变量
- 只展示已持久化可查询状态
