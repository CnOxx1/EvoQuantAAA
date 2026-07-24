# research_lab

## 名称
研究实验区：因子/信号试算与实验记录；产出默认不可直接实盘。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 实验因子/信号/元数据 | `research_*` | 实验任务完成时；不可直接进实盘 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 实验表契约 | 上游契约 |
| data_quality | `../data_quality/README.md` | DQ | 上游门禁 |
| data_process | `../data_process/README.md` | 加工数据 | 上游（经库） |
| security_master | `../security_master/README.md` | Universe | 过滤标的 |
| strategy_registry | `../strategy_registry/README.md` | 晋升 | 下游（登记实验版本） |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 不得直连；须经晋升 |
| backtest | `../backtest/README.md` | 回测 | 可消费实验信号做研究 |
| frontend/research | `../../frontend/research/README.md` | 研究 UI | 下游展示 |

## 边界
- 做：实验计算、写 `research_*` 结果与元数据；申请晋升。
- 不做：直接写生产信号表；调用 execution；绕过 DQ。

## 输入
- DQ=pass 的 `processed_*`、`universe_snapshot_id`、实验参数

## 输出
- 实验因子/信号表、实验 `run_id`
- 向 registry 提交的晋升申请（引用）

## 运行
- 研究任务经 api_gateway / orchestrator；环境偏 `research`

## 不变量
- 禁止未来函数（PIT）
- 实验产出不得被 execution 直接消费
