# EvoQuantAAA 前端（Arco Design）

> 方案 **B**：React 19 + Vite + **Arco Design** + TanStack Query + React Router + `lightweight-charts`  
> 只经 `api_gateway`；默认 API `http://127.0.0.1:8088`（避免本机 8080 被代理占用）

## 启动

```powershell
# 可选：仓库内便携 Node
$env:PATH = "$PWD\.tools\node;$env:PATH"
cd frontend/app
npm install
npm run dev
```

浏览器：http://127.0.0.1:5173 · **设置**页填写网关地址（默认 `http://127.0.0.1:8088`）。

配套网关：

```powershell
cd backend
python main.py gateway --host 127.0.0.1 --port 8088
```

## 路由

| 路径 | 页 | 对应后端 |
| --- | --- | --- |
| `/` | 总览（管道 + 纸面流水线） | orchestrator / ops |
| `/market/*` | 市场情报 | data_process / ALPHA 行情 |
| `/market/f10` | F10 资料 | listing/估值/基本面聚合 |
| `/strategies` | 策略注册 + 晋升 | strategy_registry |
| `/research` | 研究 run | research_lab |
| `/research/factors` | 因子管理：定义注册/改参 + 计算 + 截面 | `research_factor_def` / `research_factor_value` |
| `/research/freezes` | 证据冻结 | research_evidence_freeze |
| `/signals` | 生产信号批次 + 权重 | signal_prod |
| `/backtest` | 回测中心 | backtest |
| `/portfolio` | 组合构建 | portfolio_construct |
| `/portfolio/capital` | 资本配额 | strategy_capital_alloc |
| `/ledger` | 账本（账户/sleeve/lot/过账） | ledger |
| `/trade` | 执行 / 残差 / 过账 | execution |
| `/risk` | Kill + 决策 | risk_engine |
| `/ops` | 运维告警 | ops_monitor |
| `/ops/schedule` | 日更编排 + 活动时间线 | orchestrator |
| `/data/quality` | DQ 门禁 | data_quality |
| `/data/coverage` | 覆盖率 | ops_monitor |
| `/data/universe` | Universe 快照 | security_master |
| `/data/ingest` | 取数批次 | data_ingest |
| `/data/process` | 加工批次 | data_process |
| `/system/modules` | 模块地图 | 全模块只读聚合 |
| `/system/params` | 费用 / 风控限额 / 晋升门 | cost_params 等 |
| `/system/adapters` | 执行适配器 | execution adapters |
| `/system/audit` | API 审计 | api_audit_log |
| `/settings` | API / token / as_of / 环境 | api_gateway |

## 市场情报（`/market`）

| 区域 | 内容 |
| --- | --- |
| 左表 | 榜单 / 异动 / 新闻 / 龙虎榜 |
| 右上图 | 前复权日 K + 主图/副图指标 |
| 指标 | 预设 + 全量选择器（`/v1/market/indicators/meta`） |
| 右下 | 行情 / 指标末值 / 异动·龙虎·新闻 |

组件：`ChartPanel` · `IndicatorPicker` · `SymbolContext` · `PaperPipeline`。

## 图表

复用 `lightweight-charts`（市场 K 线已有）：

| 组件 | 用途 |
| --- | --- |
| `ChartPanel` | 市场日 K + 指标主图/副图 |
| `TimeSeriesChart` | 回测 NAV/回撤、板块收盘 |
| `CategoryBars` | 总览计数、研究分层、因子分布、成交金额 |
| `HorizontalBars` | 信号/组合排名、可卖、残差 |
| `PieChart` | 权重/状态/决策占比 |
| `Heatmap` | 数据覆盖率矩阵 |
| `lib/chartAgg` | `countBy` + 状态色板 |

页面：总览 / 回测 / 研究 / 覆盖率 / 因子 / 板块 / 组合 / 信号 / 风控 / 账本 / 交易 / Universe / DQ / 取数 / 加工 / 告警 / 编排 / 策略 / 冻结 / 适配器。

体验约定：图表区分 `loading` 与空态；`env=live` 锁定写操作（**Kill 除外**）；窄屏用顶栏汉堡打开导航抽屉。  
取数/加工/参数/适配器/资本/研究 run/冻结/DQ 为**只读**；因子页可注册模板（含 **TECH_PASS 技术指标透传**）并触发计算。  
写路径：总览纸面流水线、策略晋升、日更编排、交易页、因子注册/重算。

## 纸面流水线

总览按步：`signal` → `build` → `review drafts` → `exec approved` → `ledger post`（仅 paper）。  
缺业务日、非开市日、DQ 未 passed、Kill ON、无 PAPER 策略、或 live 锁定时按钮禁用并显示阻断原因。  
顶栏可直接改业务日（交易日历约束）；账本在 `as_of` 下展示市值/NAV。  
`env=live` 锁定写操作（Kill 除外）。Trade 页提供续撮、未过账过滤与 ledger post。

## 脚本

```powershell
cd frontend/app
npm run typecheck
npm run build
```

## 不变量

- 不直连数据库；唯一入口 `api_gateway`
- live 环境 UI 默认锁定写操作
- 静态 `frontend/console` 已移除
