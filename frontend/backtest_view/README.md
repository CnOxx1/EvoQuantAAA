# backtest_view

## 名称
回测报告查看与对比。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API 展示回测结果 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| backtest | `../../backend/backtest/README.md` | 回测引擎 | 上游领域 |
| strategy_registry | `../../backend/strategy_registry/README.md` | 版本 | 对照 |
| research | `../research/README.md` | 研究页 | 同级 |

## 边界
- 做：按 `run_id` 展示报告；触发回测任务请求。
- 不做：前端重跑撮合或篡改落库结果。

## 输入
- gateway：`run_id` / `strategy_version`

## 输出
- 报告视图；回测触发请求

## 运行
- 随 frontend 启动（待定）

## 不变量
- 以落库报告为准
