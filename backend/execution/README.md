# execution

## 名称
交易执行（OMS）：消费**已风控放行**的目标持仓；管理委托状态；对接柜台；写订单/成交**事件**。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 委托/成交事件 | `order_event` / `fill_event` | 下单与回报时（不过账） |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 订单事件表 | 上游契约 |
| risk_engine | `../risk_engine/README.md` | 放行/Kill Switch | 上游硬依赖 |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓 | 间接上游 |
| ledger | `../ledger/README.md` | 账本过账 | 下游（消费本模块事件） |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| frontend/trade | `../../frontend/trade/README.md` | 交易 UI | 下游 |

## 边界
- 做：下单/改撤、状态机、成交回报落为事件、仿真/纸交易适配器。
- 不做：直接修改现金/持仓余额（属 ledger）；组合优化；绕过 risk 放行。

## 输入
- `portfolio_id`（approved）、账户、柜台回报、cost 参数、kill switch

## 输出
- 委托/成交事件表；执行状态 API（经 gateway）

## 运行
- 服务进程；`paper`/`live` 适配器隔离

## 不变量
- 每次下单前检查 risk_engine 放行与 kill switch
- 只写事件，不直接过账
