# portfolio_construct

## 名称
组合构建：将生产信号转为目标持仓草稿（权重/整手数量），不负责硬风控放行。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 目标持仓头 | `portfolio_target` | `portfolio build`；成功时 `status=draft` |
| 目标持仓腿 | `portfolio_target_position` | 整手股数 + 目标市值 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 目标持仓表 | 上游契约 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 上游（只读权重） |
| strategy_registry | `../strategy_registry/README.md` | 版本状态 | 仅 PAPER/LIVE |
| security_master | `../security_master/README.md` | Universe | 间接（信号已绑定） |
| data_process | `../data_process/README.md` | 价格/`can_buy` | 经库读 processed 日线 |
| ledger | `../ledger/README.md` | 账户权益 | 默认按账本估算 NAV（`--fixed-nav` 可固定） |
| risk_engine | `../risk_engine/README.md` | 硬风控 | 下游（`risk review`） |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 跑 LIVE 草稿 |
| frontend/portfolio | `../../frontend/portfolio/README.md` | UI | 下游展示 |

## 边界
- 做：读 **committed** `signal_batch` 权重 → 剔不可买/缺价 → 权重归一 → 整手 sizing → 写 **draft**；同日同账户幂等（已有活跃组合则 skipped）。
- 不做：最终放行；下单；绕过 signal_prod 读 research 实验信号；import 其他业务模块内部实现。

## 输入
- PAPER/LIVE `strategy_version`
- `signal_prod_weight` + `signal_batch.status=committed`
- `processed_equity_bar_1d`（价 + `can_buy`，回看 60 日）
- `cost_params.lot_size`；默认账本权益，或 `--fixed-nav --nav`

## 输出
- `portfolio_target` / `portfolio_target_position`（`status=draft`）

## 运行

```bash
cd backend
python main.py portfolio build --version sv_xxx --as-of 2026-07-23 --nav 1000000
python main.py portfolio build --live --as-of 2026-07-23
python main.py portfolio build --live --as-of 2026-07-23 --fixed-nav --nav 1000000
python main.py portfolio show --portfolio pf_xxx
python main.py portfolio list
python -m portfolio_construct.selfcheck
```

## 不变量
- live 路径只消费 committed `signal_prod`（经库）
- 草稿未经 `risk_engine` 不得被 `execution` 消费
- 股数按 `lot_size` 向下取整；现金残差写入头表
- `(strategy_version, as_of_date, account_id)` 活跃态唯一（迁移 `029`）
