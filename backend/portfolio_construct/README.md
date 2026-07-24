# portfolio_construct

## 名称
组合构建：将生产信号转为目标持仓草稿（权重/数量），不负责硬风控放行。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 目标持仓草稿 | `portfolio_target` | 组合构建完成；status=draft |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 目标持仓表 | 上游契约 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 上游 |
| security_master | `../security_master/README.md` | Universe | 过滤 |
| ledger | `../ledger/README.md` | 账户权益/持仓 | 读约束输入 |
| risk_engine | `../risk_engine/README.md` | 硬风控 | 下游（必须经过） |
| frontend/portfolio | `../../frontend/portfolio/README.md` | UI | 下游展示 |

## 边界
- 做：sizing/优化，写目标持仓**草稿**（`status=draft`）。
- 不做：最终放行；下单；绕过 signal_prod 读实验信号做 live。

## 输入
- `signal_batch_id`、`strategy_version`、账户权益、约束配置

## 输出
- 目标持仓草稿（`portfolio_id`）

## 运行
- orchestrator 触发

## 不变量
- live 路径只消费 signal_prod
- 草稿未经 risk_engine 不得被 execution 消费
