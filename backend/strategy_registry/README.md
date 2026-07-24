# strategy_registry

## 名称
策略/因子注册表：代码/参数版本、依赖数据版本、晋升状态（research→paper→live）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 策略/因子版本与晋升状态 | `strategy_version` | 登记、审批、晋升、停用时 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 注册表契约 | 上游契约 |
| research_lab | `../research_lab/README.md` | 实验 | 上游申请方 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 下游消费者 |
| backtest | `../backtest/README.md` | 回测 | 晋升前常要求回测引用 |
| risk_engine | `../risk_engine/README.md` | 风控 | 可约束可晋升条件 |
| api_gateway | `../api_gateway/README.md` | API | 晋升审批入口 |

## 边界
- 做：登记版本、参数、哈希、状态机（草稿/已回测/paper/live/停用）。
- 不做：计算因子；执行下单。

## 输入
- 实验 `run_id`、回测 `run_id`、参数与制品引用、审批动作

## 输出
- `strategy_version` 记录与状态
- 可供 signal_prod 查询的「当前 live 版本」

## 运行
- 经 api_gateway 的审批/查询 API；状态变更落库

## 不变量
- 无 registry 版本则不得标为 live 生产信号
- 状态变更可审计
