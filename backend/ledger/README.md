# ledger

## 名称
资金持仓账本：消费成交/费用事件过账；维护现金、持仓、T+1 可卖数量。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 账本分录 | `ledger_entry` | 消费成交/费用事件过账 |
| 余额/可卖 | `balance`（及可卖快照字段/表） | 过账后更新 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 账本分录表 | 上游契约 |
| execution | `../execution/README.md` | 订单成交事件 | 上游 |
| portfolio_construct | `../portfolio_construct/README.md` | 组合 | 读权益/持仓 |
| risk_engine | `../risk_engine/README.md` | 风控 | 读暴露 |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| frontend/trade | `../../frontend/trade/README.md` | UI | 经 gateway 展示 |

## 边界
- 做：事件→分录→余额；计算 T+1 可卖；费用入账。
- 不做：向柜台发单；改写历史分录而不留调整凭证。

## 输入
- 已落库成交/费用事件、`account_id`

## 输出
- 分录、余额、可卖数量快照

## 运行
- 可由编排在成交后触发，或订阅事件（仍经库/ID）

## 不变量
- 余额仅由分录推导或与分录一致
- T+1：当日买入不可卖（A 股默认）
- 对账以本账本与托管/柜台为准
