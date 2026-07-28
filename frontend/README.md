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
| **app（F1 SPA）** | `app/` | React+Vite 运维控制台（主实现） |
| console | `console/` | F0 静态运维台（并行保留） |
| design-mocks | `design-mocks/` | UI 效果图 |
| research | `research/` | 域 README 契约（F2） |
| backtest_view | `backtest_view/` | 域 README 契约（F2） |
| portfolio | `portfolio/` | 域 README 契约（实现并入 app） |
| trade | `trade/` | 域 README 契约（F2） |
| ops | `ops/` | 域 README 契约（F2） |

## 设计方案
完整方案见 [`FRONTEND_DESIGN.md`](./FRONTEND_DESIGN.md)。

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
- 不做：直连 DB；实现撮合/因子；绕过 gateway 打内部模块；UI 暴露 live 真实下单。

## 输入
- api_gateway 响应；用户操作

## 输出
- UI；经 gateway 的命令（只含引用与标量）

## 运行

```bash
# 终端 1：网关
cd backend && python main.py gateway --port 8080

# 终端 2：F1 SPA（推荐）
cd frontend/app && npm install && npm run dev
# http://127.0.0.1:5173

# 或 F0 静态 console
cd frontend/console && python -m http.server 8081
```

- 禁止配置业务库连接串
- 网关已对本地静态源与 Vite `:5173` 放开 CORS

## 不变量
- 业务真相以 API/库为准，不以前端缓存为准
- skip 质量门必须填原因；`live` 环境徽章仅提示，不开放真实下单
