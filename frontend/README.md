# frontend

## 名称
前端应用层：只经 `api_gateway` 访问后端；不直连库。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 前端**不直连数据库**；展示与操作经 api_gateway |


## 本目录模块一览

| 模块/子目录 | 路径 | 主要作用 |
| --- | --- | --- |
| console | `console/` | 总控台 / 仪表盘 |
| research | `research/` | 研究实验可视化 |
| backtest_view | `backtest_view/` | 回测报告 |
| portfolio | `portfolio/` | 目标持仓与风控结果 |
| trade | `trade/` | 委托成交与账本视图 |
| ops | `ops/` | 监控对账告警 |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| api_gateway | `../backend/api_gateway/README.md` | 唯一对外 API | 上游 |
| backend | `../backend/README.md` | 业务总览 | 间接 |
| database | `../database/README.md` | 契约 | 不直连 |
| orchestrator | `../backend/orchestrator/README.md` | 任务 | 经 gateway 触发 |
| risk_engine | `../backend/risk_engine/README.md` | Kill Switch/放行 | 经 gateway 展示与操作 |

## 边界
- 做：展示与人工确认/审批类操作（晋升、杀开关、确认目标持仓）。
- 不做：直连 DB；实现撮合/因子；绕过 gateway 打内部模块。

## 输入
- api_gateway 响应；用户操作

## 输出
- UI；经 gateway 的命令（只含引用与标量）

## 运行

```bash
# 终端 1：网关
cd backend && python main.py gateway --port 8080
# 终端 2：console 静态页
cd frontend/console && python -m http.server 8081
# 浏览器打开 http://127.0.0.1:8081
```

- 禁止配置业务库连接串
- 网关已对本地静态源放开 CORS（含 `file://` 的 `null` origin）

## 不变量
- 业务真相以 API/库为准，不以前端缓存为准
