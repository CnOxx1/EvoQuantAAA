# execution

## 名称
交易执行（OMS）：消费**已风控放行**的目标持仓；纸面适配器即时成交；只写订单/成交**事件**（不过账）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 执行批次 | `execution_run` | `execution run`；同 portfolio 至多一 `committed` |
| 委托事件 | `order_event` | NEW / STATUS（FILLED/REJECTED） |
| 成交事件 | `fill_event` | 纸面即时成交；含佣金/印花税/滑点 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 订单事件表 | 上游契约 |
| risk_engine | `../risk_engine/README.md` | 放行/Kill Switch | 上游硬依赖（经库） |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓 | 间接上游 |
| ledger | `../ledger/README.md` | 账本过账 | 下游；CLI 每单立即 post |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 跑 approved |
| frontend/trade | `../../frontend/trade/README.md` | 交易 UI | 下游 |

## 边界
- 做：门禁（approved + risk_decision + kill off）→ 纸面意图 → `order_event`/`fill_event`；成功后 `portfolio_target.status=executed`。
- 不做：直接改现金/持仓余额（属 ledger）；实盘柜台；绕过 risk。

## 纸面口径
- 读 **本策略 sleeve**（`ledger_sleeve_position` / `ledger_lot.strategy_version`）做差额 BUY/SELL
- 现金仍为账户级；先卖后买；不足则 `insufficient_cash` / `clamped_cash`
- SELL 受本策略 T+1 lot + `can_sell` 约束
- 成交价优先未复权 `close`
- **CLI**：每个 `committed` execution 后立即调用 ledger post（防同日多组合抢同一未过账快照）
- 已有 committed posting 的 portfolio **禁止 `--force` 重跑**

## 运行

```bash
cd backend
python main.py execution run --portfolio pf_xxx
python main.py execution run --approved --as-of 2026-07-23
python main.py execution list
python -m execution.selfcheck
```

## 不变量
- 差额只对本 `strategy_version` sleeve，不得卖他策略持仓
- 每次执行前检查 approved + risk_decision + kill switch
- 只写事件；过账由 ledger（CLI 串联）
