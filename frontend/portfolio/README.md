# portfolio

## 名称
目标持仓与风控决策视图；支持人工确认（经 gateway）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 确认类操作经 API，由 backend 落库 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| portfolio_construct | `../../backend/portfolio_construct/README.md` | 组合草稿 | 上游领域 |
| risk_engine | `../../backend/risk_engine/README.md` | 放行/否决 | 上游领域 |
| trade | `../trade/README.md` | 交易页 | 同级 |

## 边界
- 做：展示草稿/已批准持仓与风控原因；提交确认类请求。
- 不做：前端求解优化；直接改账本。

## 输入
- gateway：`portfolio_id` / `strategy_version`

## 输出
- 组合视图；确认/调整请求

## 运行
- 随 frontend 启动（待定）

## 不变量
- 以 risk 决策与落库持仓为准
