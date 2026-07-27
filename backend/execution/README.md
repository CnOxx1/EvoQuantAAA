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
| ledger | `../ledger/README.md` | 账本过账 | 下游（读 fill；已落地） |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 跑 approved |
| frontend/trade | `../../frontend/trade/README.md` | 交易 UI | 下游 |

## 边界
- 做：门禁（approved + risk_decision + kill off）→ 纸面意图 → `order_event`/`fill_event`；成功后 `portfolio_target.status=executed`。
- 不做：直接改现金/持仓余额（属 ledger）；实盘柜台；绕过 risk。

## 输入
- `portfolio_id`（status=approved）
- 最新 `risk_decision=approved`
- `kill_switch` off
- `cost_params`、目标持仓腿

## 输出
- `execution_run` / `order_event` / `fill_event`
- portfolio → `executed`

## 纸面口径
- 读 `ledger_balance` 当前持仓，按目标股数做**差额** BUY/SELL（`assumption=ledger_delta_to_target`）
- SELL 受 `ledger_lot` T+1 可卖上限约束（超量压缩或 reject）
- 买价 `mid*(1+slippage)`，卖价 `mid*(1-slippage)`；印花税仅 SELL
- 佣金 `max(amount*rate, min_commission)`
- 同 portfolio 已有 `running` 则 blocked（`--force` 标记失败后可重跑）

## 运行

```bash
cd backend
python main.py execution run --portfolio pf_xxx
python main.py execution run --approved --as-of 2026-07-23
python main.py execution list
python main.py execution show --execution ex_xxx
python -m execution.selfcheck
```

## 不变量
- 每次执行前检查 approved + risk_decision + kill switch
- 只写事件，不直接过账
- 模块间不 import 业务内部实现；经库交接
