# orchestrator

## 名称
流水线编排：DAG/定时任务；只传引用 ID，不搬运业务载荷。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 任务状态 | `job_status` | 创建/更新/完成/失败任务时 |


## 本目录模块一览
无子模块；本目录即单一模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../api_gateway/README.md` | 外部触发入口 | 上游（人工/API 触发） |
| data_ingest | `../data_ingest/README.md` | 获取 | 下游任务 |
| data_process | `../data_process/README.md` | 加工 | 下游任务 |
| data_quality | `../data_quality/README.md` | DQ | 下游任务 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 下游任务 |
| portfolio_construct | `../portfolio_construct/README.md` | 组合 | 下游任务 |
| risk_engine | `../risk_engine/README.md` | 风控 | 下游任务 |
| execution | `../execution/README.md` | 执行 | 下游任务 |
| ops_monitor | `../ops_monitor/README.md` | 监控重跑 | 可请求重跑（传 ID） |

## 边界
- 做：定义并执行任务图；记录 `job_id` 状态；按依赖触发下游（载荷仅 ID）。
- 不做：实现各域算法；读写业务大表做计算；被业务模块反向依赖来「顺便调度」。

## 输入
- 调度配置 / API 触发参数
- 库中任务状态与上游完成标记

## 输出
- `job_*` 状态表
- 对各模块任务入口的引用调用

## 运行
- 待定：调度进程 / worker

## 不变量
- 消息与调用只含引用 ID 与标量参数
- 业务模块禁止私建平行调度器绕过本模块（主链路）
