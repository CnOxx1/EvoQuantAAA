# EvoQuantAAA 前端设计方案

> 状态：**F1 已落地**（2026-07-28）· 实现目录 [`app/`](./app/)  
> 约束：只经 `api_gateway`；不直连库；paper 默认可写，live 路径 UI 必须 fail-closed  
> 效果图：[`design-mocks/`](./design-mocks/)

---

## 1. 产品定位

**一句话**：面向量化运维与研究员的 **纸面生产控制台**，把「研究 → 晋升 → 日更 → 风控 → 执行 → 账本」做成可审计的人机界面，而不是零售交易 App，也不是营销落地页。

| 做 | 不做 |
| --- | --- |
| 日更健康度、告警、Kill、晋升审批 | 浏览器内算因子 / 跑回测引擎 |
| 组合 / 风控决策 / 订单成交 / sleeve 账本 | 直连券商或暴露密钥 |
| 证据包与冻结产物只读浏览 | ALL_LISTED 长窗 bulk 触发 |
| 写操作经 gateway 审计 | 绕过质量门无原因；假装 live 已成交 |

**环境徽章（全局常驻）**：`research` / `paper` / `live`。`live` 仅在 `ASHARE_ALLOW_LIVE` 武装且适配器允许时显示可操作态；默认灰显并提示 fail-closed。

---

## 2. 用户与场景

| 角色 | 主任务 | 关键页面 |
| --- | --- | --- |
| 运维 | 日更是否绿、Kill、告警确认 | Overview / Ops / Risk |
| 研究员 | 看 IC/证据/回测、申请晋升 | Research / Strategies |
| 组合/风控 | 审 draft、看拒绝原因、确认放行 | Portfolio / Risk |
| 交易复核 | 看 intent→fill→ledger、pending 残差 | Trade / Ledger |

---

## 3. 信息架构（单一 App，六域路由）

现有 `frontend/{console,research,backtest_view,portfolio,trade,ops}` 保留为**业务域 README 契约**，实现上合并为一个 SPA，避免 6 套静态页分叉。

```text
/                     Overview（今日管道）
/research             因子运行 / 证据包 / freeze
/research/backtests   回测报告（原 backtest_view）
/strategies           策略版本状态机 + 晋升
/portfolio            目标持仓 / draft→approved
/risk                 Kill + decisions + 审核
/trade                执行 runs / orders / fills / pending
/ledger               账户现金 / sleeve / lots / 可卖
/ops                  告警 / coverage / schedule 状态
/settings             API base、token、账户默认、环境
```

**全局壳**：顶栏品牌 + 环境徽章 + Kill 灯 + as-of 日期；侧栏六域；主区一页一事。

---

## 4. 技术选型

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 框架 | **React 19 + Vite + TypeScript** | 与仓库 Python 解耦；组件化适合审批流与表格；后续可接 React Compiler |
| 路由 | React Router | 与域 README 一一对应 |
| 数据 | TanStack Query | 服务端状态；轮询 Kill/alerts；写后 invalidate |
| 图表 | Lightweight Charts 或 uPlot | 净值/IC 曲线够用；避免重型 BI |
| 样式 | CSS Modules + 设计 token（见 §6） | 不引入庞大 UI 库；保持运维密度 |
| 包管理 | 独立 `frontend/app/package.json` | 与 backend 依赖隔离 |
| 部署 | 静态构建 → 可由 gateway 同域托管或 nginx | CORS 仍保留本地开发 |

**明确不选**：Next.js SSR（无 SEO 需求）、直连 PG、Electron、多仓微前端（现阶段过重）。

**迁移路径**：Phase F0 保留现有 `console/` 静态页可用；Phase F1 起新 App 并行，功能对齐后 deprecate 静态 console。

---

## 5. 页面规格（摘要）

### 5.1 Overview（今日管道）

- **一屏一件事**：今日 as-of 的管道灯带（ingest → process → DQ → signal → portfolio → risk → exec → ledger）。
- 每段：状态 pill（ok / degraded / failed / skipped）+ 最新 `job_id` / `run_id` 链接。
- 右侧：Kill 状态、未确认告警数、open pending 数。
- **禁止**：首屏堆统计卡片墙、营销文案、装饰插画。

### 5.2 Research

- 列表：`research_run`（kind、因子、窗、结论 soft/hard）。
- 详情：IC 摘要表 + OOS 窗；证据 pack JSON 折叠；`freeze` 记录只读。
- 动作：仅「打开关联回测」「申请晋升（跳到 Strategies 预填）」。

### 5.3 Strategies

- 状态机泳道：DRAFT → BACKTESTED → PAPER → LIVE / RETIRED。
- 晋升抽屉：目标态、关联 `backtest_run`、质量门结果（failing 列表）、强制 skip 须原因（与 CLI 一致）。
- LIVE 行高亮但标注「生产信号源，不直接下单」。

### 5.4 Portfolio

- draft / approved / executed 过滤；持仓表（symbol、目标股数、价格口径、can_buy/sell）。
- 一键「提交风控审核」；失败展示 hard rule 明细。

### 5.5 Risk

- Kill 大按钮（危险样式，二次确认）。
- decisions 时间线：approved / rejected + 原因。
- ADV/行业违规可视化（占比条，非装饰）。

### 5.6 Trade

- execution 列表；点进看 orders/fills；adapter 列（paper / stub / live_gated）。
- pending 残差表 + 「说明：续撮由 schedule/CLI，UI 默认只读；可选触发须新 API」。
- **live_gated 行**：一律显示拒单原因，禁止伪装成已成交。

### 5.7 Ledger

- 账户现金、sleeve 持仓、lot/T+1 可卖（`as_of`）。
- 与目标持仓 diff（目标 − 实际）便于发现 pending。

### 5.8 Ops

- alerts 表（severity、确认）；coverage 热力（symbol×kind 有无）。
- schedule 最近一轮摘要（只读，触发重跑 Phase F3）。

---

## 6. 视觉与设计系统

面向 **专业运维密度**，不是 SaaS 营销站。

| Token | 方向 |
| --- | --- |
| 品牌 | 顶栏固定字标 **EvoQuantAAA**（中等权重），页面标题不得压过品牌 |
| 字体 | UI：`IBM Plex Sans`；数字/代码：`IBM Plex Mono`（避免 Inter/Roboto/系统默认堆） |
| 底色 | 浅冷灰纸面 `#E8EDF2` + 细网格或极淡噪声；主面 `#F7F9FB`；**避免**紫渐变、奶油衬线、纯黑炫光 |
| 强调 | 单色强调：石油蓝 `#1F4E79`；危险：锈红 `#9B2C2C`；成功：苍松 `#2F6F4E` |
| 布局 | 顶栏 56px + 侧栏 220px + 主区；表格优先，卡片仅用于「可操作单元」 |
| 动效 | 管道灯状态切换 150ms；Kill 开启轻微脉冲；列表刷新淡入——最多 2–3 处 |
| 密度 | 默认紧凑行高；关键写操作加大点击热区 |

现有 `console` 的 Fraunces 展示风可保留在登录/空态点缀，**业务页改为上述运维气质**。

---

## 7. API 契约缺口（前端阻塞项）

当前 gateway 已有：strategies / promote / portfolios / kill / review / decisions / execution / ledger / alerts。

| 缺口 | 用途 | 建议阶段 |
| --- | --- | --- |
| `GET /v1/ops/pipeline?as-of=` | Overview 灯带 | F1 |
| `GET /v1/research/runs` + freeze list | Research | F1 |
| `GET /v1/backtests/{id}` | 回测报告 | F1 |
| `GET /v1/executions`（列表）+ pending | Trade | F1 |
| `GET /v1/ops/coverage` | Ops 热力 | F2 |
| `POST /v1/ops/schedule/once`（受控） | 触发一轮 | F3 |
| `POST /v1/execution/run`（仅 paper） | 可选人工执行 | F3（默认关闭） |

写接口一律：Bearer、审计、错误体带 `detail` + `meta.failing`。

---

## 8. 分期落地

| 阶段 | 目标 | 验收 |
| --- | --- | --- |
| **F0** | 文档定稿；console 保持可用；补齐本方案 | ✅ |
| **F1** | Vite App 壳 + Overview/Strategies/Risk/Portfolio 读+现有写 | ✅ `frontend/app` |
| **F2** | Research/Backtest/Trade/Ledger/Ops 只读深化 | 待做 |
| **F3** | 受控写：schedule once、paper execution；live UI 锁死 | 待做 |
| **F4** | （可选）gateway 托管静态资源；简易 RBAC | 待做 |

### F1 已拍板默认

1. 技术栈：**React + Vite + TS**（`frontend/app`）  
2. Overview 灯带：前端拼装现有 endpoints（暂不强制 `pipeline` API）  
3. 执行：**UI 默认只读**，执行留给 schedule/CLI

---

## 9. 目录建议

```text
frontend/
├── README.md                 # 总览（链到本方案）
├── FRONTEND_DESIGN.md        # 本文件
├── console/                  # F0 遗留静态运维台（并行期保留）
├── research|backtest_view|portfolio|trade|ops/  # 域 README 契约（可无实现）
└── app/                      # F1+ SPA
    ├── package.json
    ├── index.html
    ├── src/
    │   ├── main.tsx
    │   ├── routes/
    │   ├── pages/
    │   ├── components/       # Shell, StatusPill, KillBanner, DataTable
    │   ├── api/              # gateway client
    │   └── styles/tokens.css
    └── dist/
```

---

## 10. 不变量（前端合入清单）

1. 零数据库连接串；只打 `api_gateway`。  
2. 写操作必须可展示审计结果；skip 质量门必须填原因。  
3. UI 不得把 `broker_stub` / `live_gated` 显示为成交成功。  
4. 默认账户 `paper_default`；切换 live 账户需二次确认。  
5. 不在 UI 提供 ALL_LISTED / 长窗 bulk 入口。  
6. 业务真相以 API 为准；本地缓存可丢。

---

## 11. 开放决策（实现前需你确认）

> F1 已按推荐默认落地。以下仅影响 F2/F3。

1. Overview 是否补后端 `GET /v1/ops/pipeline`（替代前端拼装）。  
2. F3 是否允许 UI「纸面执行」按钮。  
3. Research/Trade 列表 API 字段形状（与 CLI 对齐）。
