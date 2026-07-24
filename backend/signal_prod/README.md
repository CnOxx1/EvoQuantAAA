# signal_prod

## 名称
生产信号：仅运行 `strategy_registry` 中已晋升版本，写入带版本的生产信号表。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 生产信号 | `signal_prod_*` | 仅已晋升 `strategy_version` 运行后写入 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 生产信号表 | 上游契约 |
| strategy_registry | `../strategy_registry/README.md` | 版本与晋升 | 上游（唯一允许运行的定义） |
| data_quality | `../data_quality/README.md` | DQ | 上游门禁 |
| security_master | `../security_master/README.md` | Universe | 绑定快照 |
| portfolio_construct | `../portfolio_construct/README.md` | 组合 | 下游 |
| backtest | `../backtest/README.md` | 回测 | 可对生产版本做回归 |
| research_lab | `../research_lab/README.md` | 实验 | 非直接上游 |

## 边界
- 做：按 `strategy_version` 生成生产信号并落库。
- 不做：运行未晋升实验代码；在本模块改账本/下单。

## 输入
- 已晋升 `strategy_version`、DQ=pass 批次、`universe_snapshot_id`

## 输出
- `signal_prod_*`（含 `strategy_version` / `signal_batch_id`）

## 运行
- orchestrator 在晋升级策略的日更/周更任务中触发

## 不变量
- 每条生产信号必须可追溯到 registry 版本与数据/Universe 快照
- 禁止读取未晋升的 research 表作为实盘输入
