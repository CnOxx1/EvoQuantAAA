# trade

## 名称
委托、成交与账本余额/可卖视图。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 下单请求经 API；订单/账本由 execution/ledger 落库 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| execution | `../../backend/execution/README.md` | OMS | 上游领域 |
| ledger | `../../backend/ledger/README.md` | 账本 | 上游领域 |
| risk_engine | `../../backend/risk_engine/README.md` | Kill Switch | 展示/请求 |
| portfolio | `../portfolio/README.md` | 组合页 | 同级 |

## 边界
- 做：展示订单与账本；经 gateway 下单/撤单请求。
- 不做：直连柜台；前端实现 OMS/过账。

## 输入
- gateway：`order_id` / `account_id` / `portfolio_id`

## 输出
- 交易与账本视图；交易命令请求

## 运行
- 随 frontend 启动（待定）

## 不变量
- 状态以 API 为准；乐观更新可被校正
